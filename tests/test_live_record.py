"""The containment property: a published record holds no third-party content.

This is the load-bearing test of the non-retainable-evidence design. Everything
else in that design is an argument; this is the part that can be checked.

The shape of the test follows the 2026-08-20 publication-boundary incident. That
failure was not a wrong rule — it was a correct constraint that nothing read. So
"the audit record cannot contain restricted content" is not left as an intention
here: a fake source is seeded with content of exactly the kinds the licence
forbids retaining, the recorder is driven for real, and the bytes on disk are
searched for every one of those strings.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from geosteward.live.base import (
    CITED_ONLY,
    NOT_RETAINED,
    RE_DERIVABLE,
    THIRD_PARTY_RESTRICTED,
    LiveRequest,
    LiveUnavailable,
    describe,
    response_digest,
)
from geosteward.live.fake import POISON_STRINGS, FakeGroundedSource, FakeLiveSource
from geosteward.live.record import (
    RECORDED_KEYS,
    LiveEvidenceRecorder,
    RecordShapeError,
    build_payload,
    compare_digests,
)

CELL = "8929a1b2c3dffff"


def request(**overrides) -> LiveRequest:
    parameters = {
        "h3_cell": CELL,
        "radius_m": 1200,
        "included_types": ["hospital", "school", "fire_station"],
        "fields": ["id", "displayName", "location", "primaryType"],
    }
    parameters.update(overrides)
    return LiveRequest(api="places.searchNearby", parameters=parameters)


class TestContainment(unittest.TestCase):
    """The property the design stands on."""

    def test_no_poison_string_reaches_the_written_record(self) -> None:
        source = FakeLiveSource()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_evidence.jsonl"
            recorder = LiveEvidenceRecorder(path)
            result = source.lookup(request())
            recorder.record(source, request(), result)

            written = path.read_text(encoding="utf-8")
            # The content was genuinely handed to the recorder — otherwise this
            # test would pass by never exercising the risk.
            self.assertIn("Poisonstring", json.dumps(result.display_payload))
            for poison in POISON_STRINGS:
                with self.subTest(poison=poison):
                    self.assertNotIn(poison, written)

    def test_record_carries_only_approved_keys(self) -> None:
        source = FakeLiveSource()
        payload = build_payload(source, request(), source.lookup(request()))
        self.assertEqual(set(payload), set(RECORDED_KEYS))

    def test_place_ids_are_absent_from_the_record(self) -> None:
        # The owner's 2026-08-20 ruling on §11.2: the terms permit storing place
        # IDs indefinitely, which is not obviously permission to redistribute
        # them in a public artifact. They stay available to the caller for the
        # project's own joins.
        source = FakeLiveSource()
        result = source.lookup(request())
        self.assertTrue(result.reference_ids)
        written = json.dumps(build_payload(source, request(), result))
        for reference_id in result.reference_ids:
            with self.subTest(reference_id=reference_id):
                self.assertNotIn(reference_id, written)

    def test_the_attestation_survives_the_omissions(self) -> None:
        # Containment is only interesting if what remains is still checkable.
        source = FakeLiveSource()
        payload = build_payload(source, request(), source.lookup(request()))
        self.assertEqual(payload["request"]["h3_cell"], CELL)
        self.assertEqual(payload["n_results"], 3)
        self.assertEqual(len(payload["response_sha256"]), 64)
        self.assertEqual(payload["license"], THIRD_PARTY_RESTRICTED)
        self.assertEqual(payload["verifiability"], RE_DERIVABLE)
        self.assertEqual(payload["retention"], NOT_RETAINED)
        self.assertEqual(payload["attribution"], "Fake Maps Provider")


class TestRecordShape(unittest.TestCase):
    def test_request_without_a_tile_is_refused_rather_than_recorded(self) -> None:
        source = FakeLiveSource()
        pointwise = LiveRequest(
            api="places.searchNearby",
            parameters={"latitude": 34.1897, "longitude": -118.1312, "radius_m": 1200},
        )
        with self.assertRaises(RecordShapeError) as ctx:
            build_payload(source, pointwise, source.lookup(request()))
        self.assertIn("h3_cell", str(ctx.exception))

    def test_nothing_is_written_when_the_shape_is_refused(self) -> None:
        source = FakeLiveSource()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_evidence.jsonl"
            recorder = LiveEvidenceRecorder(path)
            with self.assertRaises(RecordShapeError):
                recorder.record(
                    source,
                    LiveRequest(api="places.searchNearby", parameters={"radius_m": 1200}),
                    source.lookup(request()),
                )
            self.assertFalse(path.exists())

    def test_actor_names_the_live_source(self) -> None:
        source = FakeLiveSource()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_evidence.jsonl"
            row = LiveEvidenceRecorder(path).record(
                source, request(), source.lookup(request())
            )
        self.assertEqual(row["actor"], "live.places")
        self.assertEqual(row["action"], "live_lookup")
        self.assertTrue(row["run_id"])

    def test_records_append_rather_than_replace(self) -> None:
        source = FakeLiveSource()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_evidence.jsonl"
            recorder = LiveEvidenceRecorder(path)
            for cell in ("8929a1b2c3dffff", "8929a1b2c47ffff"):
                recorder.record(source, request(h3_cell=cell), source.lookup(request()))
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["payload"]["request"]["h3_cell"] for r in rows],
                         ["8929a1b2c3dffff", "8929a1b2c47ffff"])


class TestReDerivation(unittest.TestCase):
    def test_same_request_yields_the_same_digest(self) -> None:
        source = FakeLiveSource()
        first = source.lookup(request())
        second = source.lookup(request())
        self.assertEqual(first.response_sha256, second.response_sha256)
        verdict = compare_digests(first.response_sha256, second.response_sha256)
        self.assertTrue(verdict["matched"])
        self.assertEqual(verdict["verdict"], "re-derived")

    def test_changed_response_is_reported_as_drift_not_error(self) -> None:
        recorded = FakeLiveSource().lookup(request())
        moved = dict(FakeLiveSource().payload)
        moved["places"] = moved["places"][:2]  # a facility closed
        replayed = FakeLiveSource(payload=moved).lookup(request())

        verdict = compare_digests(recorded.response_sha256, replayed.response_sha256)
        self.assertFalse(verdict["matched"])
        self.assertEqual(verdict["verdict"], "drift")
        self.assertIn("signal about the world", verdict["note"])

    def test_digest_ignores_key_order(self) -> None:
        # Canonical JSON, so a provider reordering its keys does not read as a
        # content change. Otherwise every replay would report drift, which is
        # the same as reporting nothing.
        self.assertEqual(
            response_digest({"a": 1, "b": [2, 3]}),
            response_digest({"b": [2, 3], "a": 1}),
        )


class TestDeclaredUnavailability(unittest.TestCase):
    def test_missing_key_raises_rather_than_substituting_a_fake(self) -> None:
        source = FakeLiveSource(unavailable=True)
        with self.assertRaises(LiveUnavailable):
            source.lookup(request())


class TestGroundedRegime(unittest.TestCase):
    def test_grounded_source_declares_itself_cited_only(self) -> None:
        declarations = describe(FakeGroundedSource())
        self.assertEqual(declarations["verifiability"], CITED_ONLY)
        self.assertEqual(declarations["license"], THIRD_PARTY_RESTRICTED)
        self.assertEqual(declarations["retention"], NOT_RETAINED)

    def test_grounded_prose_is_not_reproducible(self) -> None:
        # Stated as a test so nobody later "fixes" it by hashing the text: a
        # digest over non-reproducible prose looks like an anchor and holds
        # nothing. The citations are what survive.
        source = FakeGroundedSource()
        first = source.ask("What facilities are near here?", {"h3_cell": CELL})
        second = source.ask("What facilities are near here?", {"h3_cell": CELL})
        self.assertNotEqual(first.text, second.text)
        self.assertEqual(first.citations, second.citations)
        self.assertFalse(hasattr(first, "response_sha256"))


if __name__ == "__main__":
    unittest.main()
