"""NHC and NIFC connectors: pure parse functions tested on committed fixtures."""

import json
import unittest
from pathlib import Path

from geosteward.sources import nhc, nifc

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class TestNhcParse(unittest.TestCase):
    def test_parses_active_storms_and_skips_broken(self) -> None:
        events, skipped = nhc.parse(load("nhc_current_storms.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        storm = events[0]
        self.assertEqual(storm.source, "nhc")
        self.assertEqual(storm.hazard, "tropical_cyclone")
        self.assertEqual(storm.source_id, "al062026")
        self.assertEqual(storm.name, "Hurricane Franklin")
        self.assertAlmostEqual(storm.lat, 24.9)
        self.assertAlmostEqual(storm.lon, -83.4)
        self.assertEqual(storm.severity, "85")
        self.assertEqual(storm.properties["classification"], "HU")

    def test_classification_labels(self) -> None:
        events, _ = nhc.parse(load("nhc_current_storms.json"))
        self.assertEqual(events[1].name, "Tropical Storm Gil")

    def test_module_contract(self) -> None:
        self.assertEqual(nhc.SOURCE, "nhc")
        self.assertTrue(nhc.URL.startswith("https://www.nhc.noaa.gov/"))


class TestNifcParse(unittest.TestCase):
    def test_parses_incidents_and_skips_null_geometry(self) -> None:
        events, skipped = nifc.parse(load("nifc_incidents.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        fire = events[0]
        self.assertEqual(fire.source, "nifc")
        self.assertEqual(fire.hazard, "wildfire")
        self.assertEqual(fire.name, "EATON")
        self.assertAlmostEqual(fire.lat, 34.19)
        self.assertAlmostEqual(fire.lon, -118.13)
        self.assertEqual(fire.severity, "14021.0")
        self.assertEqual(fire.properties["percent_contained"], 100.0)
        self.assertEqual(fire.properties["state"], "US-CA")

    def test_module_contract(self) -> None:
        self.assertEqual(nifc.SOURCE, "nifc")
        self.assertIn("f=geojson", nifc.URL)


if __name__ == "__main__":
    unittest.main()
