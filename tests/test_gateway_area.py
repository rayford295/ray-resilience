import unittest
from pathlib import Path

from geosteward.gateway.context import EvidenceStore, boxes_intersect

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

    def test_tier_is_the_weakest_among_events_touched(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        tiers = [
            int(self.store.events[e]["record"].get("evidence_tier", 1))
            for e in ev.event_ids
        ]
        self.assertEqual(ev.evidence_tier, min(tiers))


if __name__ == "__main__":
    unittest.main()
