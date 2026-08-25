import json
import tempfile
import unittest
from pathlib import Path

from geosteward.gateway.context import EvidenceStore, boxes_intersect, normalise_bbox

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


if __name__ == "__main__":
    unittest.main()
