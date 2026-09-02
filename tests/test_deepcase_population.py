"""Population allocation: pure logic, fixture payloads, no network."""

import unittest

import h3

from geosteward.deepcase.population import (
    allocate_to_cells,
    blocks_query_params,
    blocks_to_rows,
)


def _row(geoid: str, pop: int, lat: float, lon: float) -> dict:
    return {"geoid": geoid, "pop": pop, "lat": lat, "lon": lon}


class QueryParamsTest(unittest.TestCase):
    def test_requests_attributes_only(self):
        p = blocks_query_params((34.0, -118.2, 34.3, -118.0))
        self.assertEqual(p["returnGeometry"], "false")
        self.assertIn("POP100", p["outFields"])
        self.assertIn("CENTLAT", p["outFields"])
        self.assertEqual(p["geometry"], "-118.2,34.0,-118.0,34.3")


class BlocksToRowsTest(unittest.TestCase):
    def test_parses_signed_string_centroids(self):
        payload = {"features": [{"attributes": {
            "GEOID": "g1", "POP100": 27, "CENTLAT": "+34.1856527", "CENTLON": "-118.1510767"}}]}
        rows = blocks_to_rows(payload)
        self.assertEqual(rows[0]["pop"], 27)
        self.assertAlmostEqual(rows[0]["lat"], 34.1856527)

    def test_drops_rows_without_a_parseable_centroid(self):
        payload = {"features": [
            {"attributes": {"GEOID": "g1", "POP100": 5, "CENTLAT": None, "CENTLON": "-118.1"}},
            {"attributes": {"GEOID": "g2", "POP100": 7, "CENTLAT": "+34.19", "CENTLON": "-118.15"}},
        ]}
        self.assertEqual(len(blocks_to_rows(payload)), 1)

    def test_null_population_counts_as_zero(self):
        payload = {"features": [{"attributes": {
            "GEOID": "g1", "POP100": None, "CENTLAT": "+34.19", "CENTLON": "-118.15"}}]}
        self.assertEqual(blocks_to_rows(payload)[0]["pop"], 0)


class AllocateTest(unittest.TestCase):
    def test_sums_into_evaluated_cells_and_declares_the_rest(self):
        inside = h3.latlng_to_cell(34.19, -118.15, 9)
        rows = [
            _row("a", 10, 34.19, -118.15),      # inside the evaluated cell
            _row("b", 5, 34.1901, -118.1501),   # same cell, second block
            _row("c", 99, 35.00, -119.00),      # in envelope, outside evaluation
        ]
        per_cell, assigned, unassigned = allocate_to_cells(rows, {inside})
        self.assertEqual(per_cell[inside], 15)
        self.assertEqual(assigned, 15)
        self.assertEqual(unassigned, 99)

    def test_duplicate_geoids_across_envelopes_count_once(self):
        inside = h3.latlng_to_cell(34.19, -118.15, 9)
        rows = [_row("a", 10, 34.19, -118.15), _row("a", 10, 34.19, -118.15)]
        per_cell, assigned, _ = allocate_to_cells(rows, {inside})
        self.assertEqual(per_cell[inside], 10)
        self.assertEqual(assigned, 10)


if __name__ == "__main__":
    unittest.main()
