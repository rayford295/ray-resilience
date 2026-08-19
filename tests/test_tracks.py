from __future__ import annotations

import unittest

from geosteward.hazards.typhoon import WindRadii, parse_point, parse_track, track_summary, wind_sector_polygon

SAMPLE_POINT = {
    "time": "2026-07-08 05:00:00",
    "lng": "128.40",
    "lat": "20.10",
    "strong": "超强台风",
    "power": "17",
    "speed": "60",
    "pressure": "920",
    "movespeed": "22",
    "movedirection": "西北",
    "radius7": "300|280|260|300",
    "radius10": "120|100|90|110",
    "radius12": "60|50|40|55",
}


class WindRadiiTests(unittest.TestCase):
    def test_parses_quadrant_string(self) -> None:
        radii = WindRadii.from_api("300|280|260|300")
        self.assertEqual(radii.ne, 300.0)
        self.assertEqual(radii.sw, 260.0)
        self.assertEqual(radii.max_km(), 300.0)

    def test_rejects_empty_and_malformed(self) -> None:
        self.assertIsNone(WindRadii.from_api(""))
        self.assertIsNone(WindRadii.from_api(None))
        self.assertIsNone(WindRadii.from_api("300|280"))
        self.assertIsNone(WindRadii.from_api("a|b|c|d"))


class ParsePointTests(unittest.TestCase):
    def test_parses_full_point(self) -> None:
        point = parse_point(SAMPLE_POINT)
        self.assertEqual(point.beaufort, 17)
        self.assertEqual(point.pressure_hpa, 920.0)
        self.assertEqual(set(point.radii), {7, 10, 12})
        self.assertEqual(point.radii[12].ne, 60.0)

    def test_missing_radii_are_omitted(self) -> None:
        raw = dict(SAMPLE_POINT, radius10="", radius12=None)
        point = parse_point(raw)
        self.assertEqual(set(point.radii), {7})

    def test_missing_coordinates_raise(self) -> None:
        with self.assertRaises(ValueError):
            parse_point(dict(SAMPLE_POINT, lat=None))


class GeometryTests(unittest.TestCase):
    def test_polygon_extent_matches_radii(self) -> None:
        point = parse_point(SAMPLE_POINT)
        polygon = wind_sector_polygon(point, 7)
        self.assertEqual(len(polygon), 32)
        lats = [lat for _, lat in polygon]
        # 300 km north at ~110.6 km/deg -> ~2.7 deg above center
        self.assertAlmostEqual(max(lats) - point.lat, 300 / 110.574, delta=0.05)
        # All points stay within the max radius bound in degrees latitude
        self.assertTrue(all(abs(lat - point.lat) <= 300 / 110.574 + 0.05 for lat in lats))

    def test_polygon_none_when_threshold_missing(self) -> None:
        point = parse_point(dict(SAMPLE_POINT, radius12=""))
        self.assertIsNone(wind_sector_polygon(point, 12))


class SummaryTests(unittest.TestCase):
    def test_summary_finds_peak_pressure(self) -> None:
        weaker = dict(SAMPLE_POINT, time="2026-07-05 05:00:00", pressure="960")
        points = parse_track({"points": [weaker, SAMPLE_POINT]})
        summary = track_summary(points)
        self.assertEqual(summary["n_points"], 2)
        self.assertEqual(summary["peak_pressure_hpa"], 920.0)
        self.assertEqual(summary["peak_time"], "2026-07-08 05:00:00")

    def test_empty_track(self) -> None:
        self.assertEqual(track_summary([]), {"n_points": 0})


if __name__ == "__main__":
    unittest.main()
