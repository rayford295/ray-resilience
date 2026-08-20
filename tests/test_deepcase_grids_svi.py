"""Generic H3 grid helpers and the SVI tract-join primitives."""

import tempfile
import unittest
from pathlib import Path

from geosteward.deepcase.grids import aggregate_labeled_points, cells_to_collection
from geosteward.deepcase.svi import (
    assign_points_to_tracts,
    load_svi_rows,
    point_in_geometry,
)


class TestLabeledPointGrid(unittest.TestCase):
    POINTS = [
        (29.44, -83.28, "minor", "a"),
        (29.4400001, -83.2800001, "severe", "b"),
        (29.50, -83.30, "moderate", "c"),
    ]

    def test_every_point_lands_and_labels_are_counted(self) -> None:
        cells = aggregate_labeled_points(self.POINTS, resolution=9)
        ids = [i for e in cells.values() for i in e["ids"]]
        self.assertCountEqual(ids, ["a", "b", "c"])
        biggest = max(cells.values(), key=lambda e: e["n"])
        self.assertEqual(biggest["labels"], {"minor": 1, "severe": 1})

    def test_collection_declares_crs_cap_and_uncertainty(self) -> None:
        cells = aggregate_labeled_points(self.POINTS, resolution=9)
        collection = cells_to_collection(
            cells, 9, properties={"source": "test"}, cell_uncertainty={"note": "x"}
        )
        self.assertEqual(collection["crs_declared"], "EPSG:4326")
        self.assertEqual(collection["properties"]["resolution_cap"], "tile")
        for feature in collection["features"]:
            self.assertIn("uncertainty", feature["properties"])


SQUARE = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
}
SQUARE_WITH_HOLE = {
    "type": "Polygon",
    "coordinates": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
    ],
}
MULTI = {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]}


class TestPointInGeometry(unittest.TestCase):
    def test_inside_and_outside_square(self) -> None:
        self.assertTrue(point_in_geometry(5, 5, SQUARE))
        self.assertFalse(point_in_geometry(15, 5, SQUARE))

    def test_hole_is_outside(self) -> None:
        self.assertFalse(point_in_geometry(5, 5, SQUARE_WITH_HOLE))
        self.assertTrue(point_in_geometry(2, 2, SQUARE_WITH_HOLE))

    def test_multipolygon(self) -> None:
        self.assertTrue(point_in_geometry(5, 5, MULTI))

    def test_unsupported_geometry_raises(self) -> None:
        with self.assertRaises(ValueError):
            point_in_geometry(0, 0, {"type": "Point", "coordinates": [0, 0]})


class TestTractAssignment(unittest.TestCase):
    TRACTS = [
        {"geometry": SQUARE, "properties": {"GEOID": "T1"}},
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]],
            },
            "properties": {"GEOID": "T2"},
        },
    ]

    def test_points_assign_to_containing_tract_or_none(self) -> None:
        # assign_points_to_tracts takes (id, lat, lon); geometry is (lon, lat)
        assignment = assign_points_to_tracts(
            [("p1", 5, 5), ("p2", 5, 15), ("p3", 5, 50)], self.TRACTS
        )
        self.assertEqual(assignment, {"p1": "T1", "p2": "T2", "p3": None})


class TestSviLoading(unittest.TestCase):
    CSV = (
        "FIPS,RPL_THEMES,RPL_THEME1,RPL_THEME2,RPL_THEME3,RPL_THEME4\n"
        "06037001,0.85,0.9,0.8,0.7,0.6\n"
        "06037002,-999,-999,0.5,0.5,0.5\n"
        "06111003,0.2,0.2,0.2,0.2,0.2\n"
    )

    def test_filters_county_and_maps_missing_to_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "svi.csv"
            path.write_text(self.CSV, encoding="utf-8")
            table = load_svi_rows(path, "06037")
        self.assertEqual(set(table), {"06037001", "06037002"})
        self.assertEqual(table["06037001"]["RPL_THEMES"], 0.85)
        self.assertIsNone(table["06037002"]["RPL_THEMES"])
        self.assertEqual(table["06037002"]["RPL_THEME2"], 0.5)


if __name__ == "__main__":
    unittest.main()
