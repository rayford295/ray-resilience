"""USGS and NWS connectors: pure parse functions tested on committed fixtures."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from geosteward.sources import nws, usgs

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class TestUsgsParse(unittest.TestCase):
    def test_parses_valid_features_and_skips_broken(self) -> None:
        events, skipped = usgs.parse(load("usgs_all_day.json"))
        self.assertEqual(len(events), 3)
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

    def test_null_magnitude_with_valid_geometry_uses_placeholder_name(self) -> None:
        events, _ = usgs.parse(load("usgs_all_day.json"))
        quake = next(e for e in events if e.source_id == "us7000quake3")
        self.assertEqual(quake.name, "M ? - 5 km SW of Nowhere, NV")
        self.assertEqual(quake.severity, "")
        self.assertAlmostEqual(quake.lat, 39.2)
        self.assertAlmostEqual(quake.lon, -118.5)

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


class TestNwsPagination(unittest.TestCase):
    def test_follows_next_link_and_merges_features(self) -> None:
        page1 = {
            "type": "FeatureCollection",
            "features": [{"id": "alert-1"}],
            "pagination": {"next": "https://api.weather.gov/alerts/active?cursor=2"},
        }
        page2 = {"type": "FeatureCollection", "features": [{"id": "alert-2"}]}

        def fake_fetch_json(url, timeout=30):
            return page1 if url == nws.URL else page2

        with patch("geosteward.sources.nws.fetch_json", side_effect=fake_fetch_json):
            merged = nws.fetch()
        self.assertEqual([f["id"] for f in merged["features"]], ["alert-1", "alert-2"])
        self.assertNotIn("pagination", merged)

    def test_single_page_without_next_returns_as_is(self) -> None:
        page = {"type": "FeatureCollection", "features": [{"id": "alert-1"}]}
        with patch("geosteward.sources.nws.fetch_json", return_value=page):
            merged = nws.fetch()
        self.assertEqual([f["id"] for f in merged["features"]], ["alert-1"])

    def test_raises_when_page_cap_exceeded_with_more_pages_remaining(self) -> None:
        call_count = {"n": 0}

        def fake_fetch_json(url, timeout=30):
            call_count["n"] += 1
            return {
                "type": "FeatureCollection",
                "features": [{"id": f"alert-{call_count['n']}"}],
                "pagination": {"next": f"https://api.weather.gov/alerts/active?cursor={call_count['n'] + 1}"},
            }

        with patch("geosteward.sources.nws.fetch_json", side_effect=fake_fetch_json):
            with self.assertRaises(RuntimeError) as ctx:
                nws.fetch()
        self.assertIn("pagination", str(ctx.exception).lower())
        self.assertLessEqual(call_count["n"], nws.MAX_PAGES)


if __name__ == "__main__":
    unittest.main()
