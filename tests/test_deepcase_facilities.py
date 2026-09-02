"""Facility-context extraction: pure logic, fixture payloads, no network."""

import unittest

from geosteward.deepcase.facilities import (
    AMENITIES,
    bbox_of_features,
    elements_to_features,
    overpass_query,
)


def _cell_feature(lon: float, lat: float) -> dict:
    d = 0.001
    ring = [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {}}


def _node(el_id: int, amenity: str, name: str = "X", lat: float = 34.19, lon: float = -118.1) -> dict:
    return {"type": "node", "id": el_id, "lat": lat, "lon": lon, "tags": {"amenity": amenity, "name": name}}


class BboxTest(unittest.TestCase):
    def test_envelope_covers_all_cells_with_padding(self):
        bbox = bbox_of_features([_cell_feature(-118.1, 34.19), _cell_feature(-118.0, 34.25)], pad_deg=0.02)
        south, west, north, east = bbox
        self.assertLess(south, 34.19 - 0.001)
        self.assertLess(west, -118.1 - 0.001)
        self.assertGreater(north, 34.25 + 0.001)
        self.assertGreater(east, -118.0 + 0.001)

    def test_empty_features_fail_closed(self):
        with self.assertRaises(ValueError):
            bbox_of_features([])


class QueryTest(unittest.TestCase):
    def test_query_names_every_bbox_and_amenity(self):
        q = overpass_query([(34.0, -118.2, 34.3, -118.0), (29.4, -83.3, 29.5, -83.2)])
        self.assertEqual(q.count("node["), 2)
        self.assertEqual(q.count("way["), 2)
        for amenity in AMENITIES:
            self.assertIn(amenity, q)
        self.assertIn("out center tags", q)


class ElementsTest(unittest.TestCase):
    def test_converts_nodes_and_way_centers(self):
        els = [
            _node(1, "hospital", "General"),
            {"type": "way", "id": 2, "center": {"lat": 34.2, "lon": -118.05},
             "tags": {"amenity": "fire_station", "name": "Station 12"}},
        ]
        feats = elements_to_features(els)
        self.assertEqual(len(feats), 2)
        cats = {f["properties"]["category"] for f in feats}
        self.assertEqual(cats, {"hospital", "fire_station"})

    def test_deduplicates_by_osm_id_and_drops_out_of_scope(self):
        els = [
            _node(1, "hospital"),
            _node(1, "hospital"),          # duplicate id
            _node(2, "bar"),               # amenity out of scope
            {"type": "way", "id": 3, "tags": {"amenity": "clinic"}},  # no coordinates
        ]
        feats = elements_to_features(els)
        self.assertEqual(len(feats), 1)

    def test_every_feature_declares_its_status_boundary(self):
        feats = elements_to_features([_node(1, "police", "PD")])
        unc = feats[0]["properties"]["uncertainty"]
        self.assertIn("operational_status", unc)
        self.assertIn("presence", unc["operational_status"])

    def test_unnamed_facilities_say_so_rather_than_inventing_a_name(self):
        el = _node(1, "clinic")
        del el["tags"]["name"]
        feats = elements_to_features([el])
        self.assertEqual(feats[0]["properties"]["name"], "(unnamed in OSM)")


if __name__ == "__main__":
    unittest.main()
