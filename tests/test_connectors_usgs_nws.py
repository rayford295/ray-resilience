"""USGS and NWS connectors: pure parse functions tested on committed fixtures."""

import json
import unittest
from pathlib import Path

from geosteward.sources import nws, usgs

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class TestUsgsParse(unittest.TestCase):
    def test_parses_valid_features_and_skips_broken(self) -> None:
        events, skipped = usgs.parse(load("usgs_all_day.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        quake = events[0]
        self.assertEqual(quake.source, "usgs")
        self.assertEqual(quake.hazard, "earthquake")
        self.assertEqual(quake.source_id, "us7000quake1")
        self.assertAlmostEqual(quake.lat, 35.68)
        self.assertAlmostEqual(quake.lon, -117.55)
        self.assertEqual(quake.severity, "4.6")
        self.assertEqual(quake.observed_utc, "20260819T104000Z")
        self.assertAlmostEqual(quake.properties["depth_km"], 8.1)

    def test_module_contract(self) -> None:
        self.assertEqual(usgs.SOURCE, "usgs")
        self.assertTrue(usgs.URL.startswith("https://earthquake.usgs.gov/"))


class TestNwsParse(unittest.TestCase):
    def test_polygon_alert_uses_centroid_and_null_geometry_skipped(self) -> None:
        events, skipped = nws.parse(load("nws_alerts.json"))
        self.assertEqual(len(events), 1)
        self.assertEqual(skipped, 1)
        alert = events[0]
        self.assertEqual(alert.source, "nws")
        self.assertEqual(alert.hazard, "weather_alert")
        self.assertEqual(alert.name, "Flood Warning for Travis County")
        self.assertEqual(alert.severity, "Severe")
        self.assertAlmostEqual(alert.lat, 30.3, places=1)
        self.assertAlmostEqual(alert.lon, -97.4, places=1)
        self.assertEqual(alert.properties["event"], "Flood Warning")

    def test_module_contract(self) -> None:
        self.assertEqual(nws.SOURCE, "nws")
        self.assertTrue(nws.URL.startswith("https://api.weather.gov/alerts/active"))


if __name__ == "__main__":
    unittest.main()
