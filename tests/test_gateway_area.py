import json
import tempfile
import unittest
from pathlib import Path

from geosteward.gateway.context import EvidenceStore, boxes_intersect, normalise_bbox

from tests.test_gateway_live import LiveGatewayTestCase
from tests.test_gateway_steward import GRID_ID, IN_AOI, GatewayTestCase, MockLLM

EVENTS = Path(__file__).resolve().parents[1] / "events"

# Eaton's AOI, comfortably inside it. Verified against
# events/eaton-2025/dossier/event_record.json's aoi_bbox_wgs84.
EATON_BOX = {"min_lat": 34.15, "min_lon": -118.16, "max_lat": 34.23, "max_lon": -118.06}
# Open ocean south-west of the Galapagos: intersects nothing.
NOWHERE = {"min_lat": -10.0, "min_lon": -120.0, "max_lat": -9.0, "max_lon": -119.0}


class BoxesIntersectTests(unittest.TestCase):
    def test_overlapping_boxes_intersect(self):
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 2, "max_lon": 2}
        b = {"min_lat": 1, "min_lon": 1, "max_lat": 3, "max_lon": 3}
        self.assertTrue(boxes_intersect(a, b))

    def test_disjoint_boxes_do_not_intersect(self):
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 1, "max_lon": 1}
        b = {"min_lat": 5, "min_lon": 5, "max_lat": 6, "max_lon": 6}
        self.assertFalse(boxes_intersect(a, b))

    def test_touching_edges_intersect(self):
        # A selection dragged flush to an AOI edge is a real selection, not a miss.
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 1, "max_lon": 1}
        b = {"min_lat": 1, "min_lon": 1, "max_lat": 2, "max_lon": 2}
        self.assertTrue(boxes_intersect(a, b))


class NormaliseBboxTests(unittest.TestCase):
    def test_fully_inverted_box_normalises_to_the_correct_box(self):
        correct = {"min_lat": 34.15, "min_lon": -118.16, "max_lat": 34.23, "max_lon": -118.06}
        inverted = {"min_lat": 34.23, "min_lon": -118.06, "max_lat": 34.15, "max_lon": -118.16}
        self.assertEqual(normalise_bbox(inverted), correct)

    def test_single_axis_inverted_box_normalises_to_the_correct_box(self):
        # Only latitude swapped -- the common case of dragging a rectangle
        # upward on a map while longitude stays left-to-right.
        correct = {"min_lat": 0.0, "min_lon": 0.0, "max_lat": 1.0, "max_lon": 1.0}
        lat_inverted = {"min_lat": 1.0, "min_lon": 0.0, "max_lat": 0.0, "max_lon": 1.0}
        self.assertEqual(normalise_bbox(lat_inverted), correct)

    def test_already_correct_box_is_unchanged(self):
        correct = {"min_lat": 0.0, "min_lon": 0.0, "max_lat": 1.0, "max_lon": 1.0}
        self.assertEqual(normalise_bbox(correct), correct)


class AreaEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(EVENTS)

    def test_selection_outside_every_aoi_is_not_in_aoi(self):
        ev = self.store.evidence_for_area(NOWHERE)
        self.assertFalse(ev.in_aoi)
        self.assertEqual(ev.cells, [])
        self.assertEqual(ev.event_ids, [])

    def test_selection_inside_eaton_matches_cells_and_cites_artifacts(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        self.assertTrue(ev.in_aoi)
        self.assertEqual(ev.event_ids, ["eaton-2025"])
        self.assertTrue(ev.cells, "expected the selection to match committed cells")
        self.assertTrue(ev.facts)
        # Unhashed data never becomes citable evidence.
        self.assertTrue(all(f.artifact_id for f in ev.facts))

    def test_returned_cells_are_a_subset_of_the_committed_grids(self):
        # The structural bound that makes a size cap unnecessary: a selection
        # cannot match more cells than exist. Pins spec section 3.2.
        ev = self.store.evidence_for_area(EATON_BOX)
        committed = set()
        for index in self.store._grids("eaton-2025").values():
            committed |= set(index)
        self.assertTrue(set(ev.cells) <= committed)

    def test_coverage_is_declared_not_merged(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        coverage = [f.text for f in ev.facts if "selection" in f.text]
        self.assertTrue(coverage, "expected a declared coverage fact")
        self.assertTrue(any("eaton-2025" in t for t in coverage))

    def test_inverted_box_behaves_identically_to_the_box_written_correctly(self):
        # A rectangle dragged on a map can have its corners in either order.
        # Before normalise_bbox, this exact swap made locate_area report
        # in_aoi=True on a geometrically empty box -- the audit would then
        # record "no evidence" for what should have been a real AOI hit with
        # zero matched cells, or worse, mask a genuine deny-outside-aoi.
        inverted = {
            "min_lat": EATON_BOX["max_lat"],
            "min_lon": EATON_BOX["max_lon"],
            "max_lat": EATON_BOX["min_lat"],
            "max_lon": EATON_BOX["min_lon"],
        }
        correct = self.store.evidence_for_area(EATON_BOX)
        flipped = self.store.evidence_for_area(inverted)
        self.assertEqual(flipped.in_aoi, correct.in_aoi)
        self.assertEqual(flipped.event_ids, correct.event_ids)
        self.assertEqual(sorted(flipped.cells), sorted(correct.cells))

    def test_single_axis_inverted_box_behaves_identically(self):
        lat_inverted = dict(EATON_BOX)
        lat_inverted["min_lat"], lat_inverted["max_lat"] = (
            EATON_BOX["max_lat"],
            EATON_BOX["min_lat"],
        )
        correct = self.store.evidence_for_area(EATON_BOX)
        flipped = self.store.evidence_for_area(lat_inverted)
        self.assertEqual(sorted(flipped.cells), sorted(correct.cells))


def _write_minimal_event(root: Path, event_id: str, tier: int, aoi: dict) -> None:
    dossier = root / event_id / "dossier"
    dossier.mkdir(parents=True)
    (dossier / "event_record.json").write_text(
        json.dumps({"event_id": event_id, "evidence_tier": tier, "aoi_bbox_wgs84": aoi}),
        encoding="utf-8",
    )


class TierWeakestLinkTests(unittest.TestCase):
    """Every committed event today is Tier 3, so no real bounding box can
    distinguish min(tiers) from max(tiers) -- or from "first event touched".
    A synthetic two-event fixture is the cheapest way to make the weakest-
    link rule an assertion that can actually fail."""

    def test_tier_is_the_weakest_among_events_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "events"
            # Overlapping AOIs so one bbox touches both. Tiers deliberately
            # apart (1 vs 3) so min() and max() disagree.
            _write_minimal_event(
                root, "weakcase-2025", tier=1,
                aoi={"min_lat": 34.05, "max_lat": 34.2, "min_lon": -118.05, "max_lon": -117.9},
            )
            _write_minimal_event(
                root, "strongcase-2025", tier=3,
                aoi={"min_lat": 34.0, "max_lat": 34.1, "min_lon": -118.1, "max_lon": -118.0},
            )
            store = EvidenceStore(root)
            bbox = {"min_lat": 34.06, "max_lat": 34.09, "min_lon": -118.06, "max_lon": -118.01}

            ev = store.evidence_for_area(bbox)

            self.assertEqual(sorted(ev.event_ids), ["strongcase-2025", "weakcase-2025"])
            self.assertEqual(ev.evidence_tier, 1)  # the weaker of {1, 3}, not the stronger


class AnswerAreaContractTests(GatewayTestCase):
    """The either-or contract, checked without invoking a model.

    Built on `GatewayTestCase` (from `tests.test_gateway_steward`) rather than
    the brief's `Steward(store=..., llm=None, policy=None)`: `Steward` is a
    dataclass with no `store` field -- `__post_init__` builds the store from
    `events_root` -- and `policy`/`audit` are required, not optional. Reusing
    the existing fixture also means the two assertions below are checked
    against the same construction every other gateway test already trusts.
    """

    def setUp(self):
        super().setUp()
        #: A response that would fail the claim post-check if it were ever
        #: sent to the model. Both cases below must raise before either
        #: purpose classification or an LLM call happens.
        self.steward = self.make_steward(MockLLM(["should never be used"]))

    def test_neither_point_nor_area_is_rejected(self):
        with self.assertRaises(ValueError):
            self.steward.answer("planner", "how bad is it?")

    def test_both_point_and_area_is_rejected(self):
        with self.assertRaises(ValueError):
            self.steward.answer(
                "planner", "how bad is it?", lat=34.19, lon=-118.1, area=EATON_BOX
            )

    def test_half_point_with_area_is_rejected(self):
        # `has_point` requires both coordinates, so a lone `lat` reads as "no
        # point" -- which used to make this combination read as exactly one
        # of {point, area}, and pass. It is really "both": a coordinate AND
        # an area. Any coordinate alongside an area must raise.
        with self.assertRaises(ValueError):
            self.steward.answer("planner", "how bad is it?", lat=34.19, area=EATON_BOX)

    def test_half_point_with_area_the_other_coordinate_is_also_rejected(self):
        # Same defect, the other axis: lon alone alongside an area.
        with self.assertRaises(ValueError):
            self.steward.answer("planner", "how bad is it?", lon=-118.1, area=EATON_BOX)


# Matches `build_fixture_events`'s aoi_bbox_wgs84 in tests/test_gateway_steward.py
# -- NOT EATON_BOX, which sits inside the real events/eaton-2025 AOI. This box has
# to overlap the synthetic "testfire-2025" fixture that `LiveGatewayTestCase`
# builds, or the request would be denied for being outside the AOI before it
# ever reached the facility-context branch this test exists to exercise.
TESTFIRE_BOX = {"min_lat": 34.0, "min_lon": -118.1, "max_lat": 34.1, "max_lon": -118.0}


class AnswerAreaFacilityContextTests(LiveGatewayTestCase):
    """A facility lookup needs a point; a drawn area is not one.

    Before this fix, `uses_live` + `area` fell through to `_lookup`, which
    calls `h3.latlng_to_cell(lat, lon, ...)` with `lat=lon=None` -- a
    `TypeError` escaping to the caller. That is a fifth response type this
    project does not have; every path through `Steward.answer` is supposed to
    end in one of exactly four structured, audited outcomes. The fix declares
    this as a capability gap instead, reusing the same `_live_unavailable`
    shape the "no source configured" and "source unreachable" cases already
    use.

    Uses a real `FakeLiveSource` + `LiveEvidenceRecorder` (via
    `LiveGatewayTestCase`, not a source-less fixture) specifically because the
    gap must be decided from the request shape and not from whether a source
    happens to be configured -- a source-less test would pass for the wrong
    reason and stay green even if the shape check were deleted.
    """

    def test_facility_context_over_an_area_is_a_declared_gap_not_a_crash(self):
        steward = self.make_live_steward(MockLLM(["should never be used"]))
        response = steward.answer(
            "resident", "What hospitals are near here?", area=TESTFIRE_BOX
        )
        self.assertEqual(response["type"], "live_source_unavailable")
        self.assertIn("point", response["reason"])
        # No third party was ever contacted for a request that cannot be
        # served, live source configured or not.
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.live_rows(), [])


class GatewayRequestAuditPayloadTests(GatewayTestCase):
    """Addition 1: the `gateway_request` audit row must record the area for
    an area query -- both are `None` there today, and the bounding box is
    recorded nowhere, so every area query in the audit log looks identical to
    every other one. Existing fields (`lat`, `lon`, and the rest) must stay
    exactly as they are; this is an addition, not a reshaping.
    """

    QUESTION = "How severe is the damage in this area?"

    def _gateway_request_payload(self):
        rows = [r for r in self.audit_rows() if r["action"] == "gateway_request"]
        self.assertEqual(len(rows), 1)
        return rows[0]["payload"]

    def test_area_query_audit_payload_records_the_bounding_box(self):
        llm = MockLLM([f"5 of 10 structures destroyed [artifact:{GRID_ID}]."])
        self.make_steward(llm).answer("planner", self.QUESTION, area=TESTFIRE_BOX)
        payload = self._gateway_request_payload()
        self.assertEqual(payload["area"], TESTFIRE_BOX)
        # Unchanged from a point query: no coordinates were given, so both
        # stay None rather than being repurposed to carry box edges.
        self.assertIsNone(payload["lat"])
        self.assertIsNone(payload["lon"])

    def test_point_query_audit_payload_is_unchanged_apart_from_a_null_area(self):
        llm = MockLLM([f"5 of 10 structures destroyed [artifact:{GRID_ID}]."])
        self.make_steward(llm).answer(
            "planner", self.QUESTION, lat=IN_AOI[0], lon=IN_AOI[1]
        )
        payload = self._gateway_request_payload()
        self.assertEqual(payload["lat"], IN_AOI[0])
        self.assertEqual(payload["lon"], IN_AOI[1])
        self.assertIsNone(payload["area"])


class AskRequestValidationTests(unittest.TestCase):
    def test_area_only_validates(self):
        from gateway.main import AskRequest
        r = AskRequest(role="planner", question="how bad?", area=EATON_BOX)
        self.assertIsNotNone(r.area)

    def test_neither_is_rejected(self):
        from pydantic import ValidationError
        from gateway.main import AskRequest
        with self.assertRaises(ValidationError):
            AskRequest(role="planner", question="how bad?")

    def test_both_is_rejected(self):
        from pydantic import ValidationError
        from gateway.main import AskRequest
        with self.assertRaises(ValidationError):
            AskRequest(
                role="planner", question="how bad?",
                lat=34.19, lon=-118.1, area=EATON_BOX,
            )

    def test_half_point_with_area_is_rejected(self):
        # Addition 2, mirrored at the request-validation layer: `lat` alone
        # (no `lon`) reads as "no point" to a naive `bool(lat and lon)`
        # check, so this shape used to pass both the endpoint's validator and
        # `Steward.answer`. It is a coordinate given alongside an area, which
        # the contract calls "both" -- it must be rejected here too, so the
        # two layers agree about what an ambiguous request looks like.
        from pydantic import ValidationError
        from gateway.main import AskRequest
        with self.assertRaises(ValidationError):
            AskRequest(role="planner", question="how bad?", lat=34.19, area=EATON_BOX)


if __name__ == "__main__":
    unittest.main()
