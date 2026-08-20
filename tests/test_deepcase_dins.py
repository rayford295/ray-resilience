"""Deep-case DINS module: crosswalk, ingest, and tile aggregation checks."""

import unittest
from pathlib import Path

from geosteward.deepcase.dins import (
    CANONICAL_SCALE,
    DINS_CROSSWALK,
    MIN_CELL_COUNT,
    aggregate_h3,
    cell_feature,
    grid_feature_collection,
    load_dins_points,
    severity_totals,
)

FIXTURE = Path(__file__).parent / "fixtures" / "dins_points_sample.csv"


class TestCrosswalk(unittest.TestCase):
    def test_all_native_labels_map_onto_canonical_scale(self) -> None:
        for native, canonical in DINS_CROSSWALK.items():
            self.assertIn(canonical, CANONICAL_SCALE, native)

    def test_covers_all_six_dins_categories(self) -> None:
        self.assertEqual(len(DINS_CROSSWALK), 6)
        self.assertEqual(DINS_CROSSWALK["Destroyed (>50%)"], "destroyed")
        self.assertEqual(DINS_CROSSWALK["Inaccessible"], "unknown")


class TestLoadDinsPoints(unittest.TestCase):
    def test_loads_rows_and_skips_missing_coordinates(self) -> None:
        points = load_dins_points([FIXTURE])
        # row 6 has an empty lat and must be skipped
        self.assertEqual(len(points), 5)
        self.assertEqual(points[0].severity, "destroyed")
        self.assertEqual(points[4].severity, "unknown")

    def test_unmapped_native_label_falls_back_to_unknown(self) -> None:
        points = load_dins_points([FIXTURE])
        self.assertTrue(all(p.severity in CANONICAL_SCALE for p in points))


class TestAggregation(unittest.TestCase):
    def setUp(self) -> None:
        self.points = load_dins_points([FIXTURE])
        self.cells = aggregate_h3(self.points, resolution=9)

    def test_every_point_lands_in_exactly_one_cell(self) -> None:
        ids = [pid for entry in self.cells.values() for pid in entry["point_ids"]]
        self.assertCountEqual(ids, [p.objectid for p in self.points])

    def test_nearby_points_share_a_cell(self) -> None:
        # points 1-3 are within metres of each other
        biggest = max(self.cells.values(), key=lambda e: e["n"])
        self.assertEqual(biggest["n"], 3)

    def test_cell_feature_has_mandatory_uncertainty_and_low_n_flag(self) -> None:
        for cell, entry in self.cells.items():
            props = cell_feature(cell, entry)["properties"]
            self.assertIn("uncertainty", props)
            self.assertEqual(props["uncertainty"]["low_n"], entry["n"] < MIN_CELL_COUNT)

    def test_destroyed_rate_is_none_when_all_points_unassessed(self) -> None:
        only_unknown = {p.objectid: p for p in self.points if p.severity == "unknown"}
        cells = aggregate_h3(list(only_unknown.values()), resolution=9)
        for cell, entry in cells.items():
            self.assertIsNone(cell_feature(cell, entry)["properties"]["destroyed_rate"])

    def test_collection_declares_crs_and_tile_resolution_cap(self) -> None:
        collection = grid_feature_collection(self.cells, 9, "fixture")
        self.assertEqual(collection["crs_declared"], "EPSG:4326")
        self.assertEqual(collection["properties"]["resolution_cap"], "tile")
        self.assertEqual(collection["properties"]["n_cells"], len(self.cells))

    def test_severity_totals_include_every_canonical_level(self) -> None:
        totals = severity_totals(self.points)
        self.assertEqual(set(totals), set(CANONICAL_SCALE))
        self.assertEqual(totals["destroyed"], 2)
        self.assertEqual(totals["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
