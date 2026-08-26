import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import h3

from geosteward.gateway.context import EvidenceStore, boxes_intersect, normalise_bbox, point_in_box
from geosteward.gateway.steward import Steward
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import PolicyEngine

from tests.test_gateway_live import LiveGatewayTestCase
from tests.test_gateway_steward import GRID_ID, IN_AOI, GatewayTestCase, MockLLM

POLICY = Path(__file__).resolve().parents[1] / "src" / "geosteward" / "harness" / "policy_v1.yaml"
AREA_JS = Path(__file__).resolve().parents[1] / "app" / "src" / "lib" / "area.js"

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


def _write_minimal_event(
    root: Path, event_id: str, tier: int, aoi: dict, *, cells: dict | None = None
) -> None:
    """A synthetic event: a dossier record, and -- when `cells` is given --
    one grid registered in the artifact manifest so `_artifact_id` actually
    resolves. Earlier this fixture wrote no manifest at all, so every grid
    would have been silently unciteable anyway; `TierWeakestLinkTests` never
    noticed only because it never gave itself a grid to begin with. `cells`
    is `{h3_cell: extra_properties}`.
    """
    event_dir = root / event_id
    dossier = event_dir / "dossier"
    dossier.mkdir(parents=True)
    (dossier / "event_record.json").write_text(
        json.dumps({"event_id": event_id, "evidence_tier": tier, "aoi_bbox_wgs84": aoi}),
        encoding="utf-8",
    )
    record_sha = hashlib.sha256(f"{event_id}-record".encode()).hexdigest()
    rows = [{"path": f"{dossier}/event_record.json", "sha256": record_sha}]
    if cells:
        exposure = event_dir / "exposure"
        exposure.mkdir()
        grid_sha = hashlib.sha256(f"{event_id}-grid".encode()).hexdigest()
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
                "properties": {"h3_cell": cell, **props},
            }
            for cell, props in cells.items()
        ]
        (exposure / "grid.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
        )
        rows.append({"path": f"{exposure}/grid.geojson", "sha256": grid_sha})
    (event_dir / "artifact_manifest.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
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
            # apart (1 vs 3) so min() and max() disagree. Each event also gets
            # one grid-bearing cell inside the shared selection, so this
            # fixture can pin more than the tier: spec section 3.3's "never
            # merged across events" claim needs events that actually produce
            # separate, non-empty coverage counts to be a real assertion
            # rather than one that would pass even if merging were re-added.
            weak_cell = h3.latlng_to_cell(34.07, -118.03, 9)
            strong_cell = h3.latlng_to_cell(34.08, -118.02, 9)
            _write_minimal_event(
                root, "weakcase-2025", tier=1,
                aoi={"min_lat": 34.05, "max_lat": 34.2, "min_lon": -118.05, "max_lon": -117.9},
                cells={weak_cell: {"n_structures": 4}},
            )
            _write_minimal_event(
                root, "strongcase-2025", tier=3,
                aoi={"min_lat": 34.0, "max_lat": 34.1, "min_lon": -118.1, "max_lon": -118.0},
                cells={strong_cell: {"n_structures": 9}},
            )
            store = EvidenceStore(root)
            bbox = {"min_lat": 34.06, "max_lat": 34.09, "min_lon": -118.06, "max_lon": -118.01}

            ev = store.evidence_for_area(bbox)

            self.assertEqual(sorted(ev.event_ids), ["strongcase-2025", "weakcase-2025"])
            self.assertEqual(ev.evidence_tier, 1)  # the weaker of {1, 3}, not the stronger

            # The property this fixture previously could not check at all:
            # each event contributes its own, separately-countable coverage
            # -- one matched cell apiece, named to its own event -- rather
            # than a single combined number. `assertCountEqual` because the
            # per-event ordering `evidence_for_area` produces is an
            # implementation detail, not a contract.
            self.assertCountEqual(ev.cells, [weak_cell, strong_cell])
            coverage = [f for f in ev.facts if "selection coverage" in f.text]
            self.assertEqual(len(coverage), 2, "expected one coverage fact per event")
            weak_coverage = next(f for f in coverage if "weakcase-2025" in f.text)
            strong_coverage = next(f for f in coverage if "strongcase-2025" in f.text)
            self.assertIn("1 evaluated tile", weak_coverage.text)
            self.assertIn("1 evaluated tile", strong_coverage.text)


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


# Same AOI as `build_fixture_events`'s testfire-2025, but a slice of it far
# from the fixture's single grid cell (centred near IN_AOI = (34.05, -118.05)).
# Inside the AOI bounding box, off the evaluated grid -- exactly the
# distinction spec section 6 draws between "in the area of interest" and "on
# evaluated ground".
TESTFIRE_CORNER = {"min_lat": 34.0, "max_lat": 34.02, "min_lon": -118.1, "max_lon": -118.08}


class AnswerAreaNoEvidenceTests(GatewayTestCase):
    """Blocking defect: `evidence_for_area` always appends a "selection
    coverage" fact and the declared unknowns, so `evidence.facts` is never
    empty for an area selection even when zero cells matched -- the old
    `if not evidence.facts` guard never fired, and a selection landing off
    the grid but inside the AOI reached the model with only "0 evaluated
    tile(s)" to write about. This is the test spec section 8 asked for and
    the review found nobody had written: an in-AOI, zero-cell selection must
    return `no_evidence`.
    """

    def test_in_aoi_zero_cell_selection_is_no_evidence(self):
        llm = MockLLM(["should never be used"])
        steward = self.make_steward(llm)
        result = steward.answer(
            "planner", "How severe is the damage in this area?", area=TESTFIRE_CORNER
        )
        self.assertEqual(result["type"], "no_evidence")
        # The reason carries what the (suppressed) coverage fact would have
        # said -- which event the selection touched -- since no_evidence
        # returns before the model ever sees the evidence block.
        self.assertIn("testfire-2025", result["reason"])
        self.assertEqual(llm.calls, 0)

    def test_selection_entirely_outside_every_aoi_is_still_a_refusal(self):
        # Contrast case: zero cells AND zero events touched is a different
        # failure (`deny-outside-aoi`), not `no_evidence` -- this fix must not
        # blur the two apart.
        llm = MockLLM(["should never be used"])
        steward = self.make_steward(llm)
        nowhere = {"min_lat": -10.0, "min_lon": -120.0, "max_lat": -9.0, "max_lon": -119.0}
        result = steward.answer("planner", "How severe is the damage in this area?", area=nowhere)
        self.assertEqual(result["type"], "refusal")
        self.assertEqual(result["rule_id"], "deny-outside-aoi")
        self.assertEqual(llm.calls, 0)


class AnswerAreaMixedCoverageTests(unittest.TestCase):
    """The other seam blocking 3 has to get right: a selection touching two
    events where only one of them has anything to show for it must still
    answer -- not fall back to `no_evidence` for the whole selection -- and
    the zero-tile event's own coverage fact must survive in the evidence the
    model actually sees, alongside the one that matched. Suppressing a
    per-event coverage fact to make this case look like a clean answer would
    lose exactly the information spec section 5 says a coverage fact exists
    to state.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.events_root = self.root / "events"
        self.has_cell = h3.latlng_to_cell(34.07, -118.03, 9)
        _write_minimal_event(
            self.events_root, "hascells-2025", tier=3,
            aoi={"min_lat": 34.05, "max_lat": 34.2, "min_lon": -118.05, "max_lon": -117.9},
            cells={self.has_cell: {"n_structures": 4}},
        )
        _write_minimal_event(
            self.events_root, "emptycells-2025", tier=3,
            aoi={"min_lat": 34.0, "max_lat": 34.1, "min_lon": -118.1, "max_lon": -118.0},
            # Deliberately no `cells`: this event's AOI is touched by the
            # selection below but its grid never matches anything inside it.
        )
        self.grid_id = hashlib.sha256(b"hascells-2025-grid").hexdigest()[:12]

    def tearDown(self):
        self.tmp.cleanup()

    def test_mixed_selection_answers_and_keeps_both_coverage_facts(self):
        llm = MockLLM([f"5 of 10 structures destroyed [artifact:{self.grid_id}]."])
        steward = Steward(
            events_root=self.events_root,
            policy=PolicyEngine.from_yaml(POLICY),
            audit=AuditLog(self.root / "audit.jsonl"),
            llm=llm,
        )
        selection = {"min_lat": 34.06, "max_lat": 34.09, "min_lon": -118.06, "max_lon": -118.01}
        result = steward.answer(
            "planner", "How severe is the damage in this area?", area=selection
        )

        self.assertEqual(result["type"], "answer")
        self.assertEqual(result["cells"], [self.has_cell])

        evidence_block = llm.last_messages[1]["content"]
        self.assertIn("hascells-2025 / selection coverage", evidence_block)
        self.assertIn("1 evaluated tile(s)", evidence_block)
        self.assertIn("emptycells-2025 / selection coverage", evidence_block)
        self.assertIn("0 evaluated tile(s)", evidence_block)


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


class CrossLayerAgreementTests(unittest.TestCase):
    """The edge-inclusive, centre-in-box predicate is implemented twice,
    independently, on purpose: `point_in_box` in
    `src/geosteward/gateway/context.py`, and `cellsInBox()` in
    `app/src/lib/area.js`, as defence in depth so the count the app shows
    before asking and the `cells` an answer cites cannot both drift the same
    wrong way from a shared bug. That is a promise about two implementations
    staying in step, not a proof -- this test is the guard: it feeds the
    same points and the same box to both and checks they keep exactly the
    same ones, including on the edges the docstrings both claim to include.
    """

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node is None:
            raise unittest.SkipTest("node is not on PATH; cannot exercise app/src/lib/area.js")

    def _js_kept(self, points: list[tuple[str, float, float]], bbox: dict) -> set[str]:
        """Runs the real `cellsInBox()` from `app/src/lib/area.js` in Node,
        via a `cellToLatLng` stub that looks the point up by the id standing
        in for an H3 cell -- the function under test never inspects the id
        itself, only what the lookup returns for it."""
        script = (
            f"import {{ cellsInBox }} from {json.dumps(str(AREA_JS))};\n"
            f"const points = {json.dumps(points)};\n"
            f"const bbox = {json.dumps(bbox)};\n"
            "const byId = new Map(points.map((p) => [p[0], [p[1], p[2]]]));\n"
            "const cellToLatLng = (id) => byId.get(id);\n"
            "const cells = points.map((p) => p[0]);\n"
            "process.stdout.write(JSON.stringify(cellsInBox(cells, bbox, cellToLatLng)));\n"
        )
        result = subprocess.run(
            [self.node, "--input-type=module"],
            input=script, capture_output=True, text=True, timeout=15, check=True,
        )
        return set(json.loads(result.stdout))

    def test_python_and_javascript_predicates_agree_on_the_same_shapes(self):
        bbox = {"min_lat": 10.0, "min_lon": 20.0, "max_lat": 12.0, "max_lon": 22.0}
        points = [
            ("inside", 11.0, 21.0),
            ("on-min-lat-edge", 10.0, 21.0),
            ("on-max-lat-edge", 12.0, 21.0),
            ("on-min-lon-edge", 11.0, 20.0),
            ("on-max-lon-edge", 11.0, 22.0),
            ("on-corner", 10.0, 20.0),
            ("outside-lat-below", 9.9, 21.0),
            ("outside-lat-above", 12.1, 21.0),
            ("outside-lon-below", 11.0, 19.9),
            ("outside-lon-above", 11.0, 22.1),
            ("outside-both", 0.0, 0.0),
        ]
        python_kept = {pid for pid, lat, lon in points if point_in_box(lat, lon, bbox)}
        js_kept = self._js_kept(points, bbox)
        self.assertEqual(python_kept, js_kept)
        # The specific claim both docstrings make, not just "the sets match"
        # by coincidence of the fixture: every edge/corner point above is
        # kept by both sides, not silently dropped by neither.
        edge_ids = {p[0] for p in points if p[0].startswith("on-")}
        self.assertTrue(edge_ids <= python_kept)
        self.assertTrue(edge_ids <= js_kept)


if __name__ == "__main__":
    unittest.main()
