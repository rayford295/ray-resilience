"""Tier-1 watch foundations: event model and append-only snapshot store."""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.sources.watchbase import WatchEvent, save_snapshot


def event(**overrides):
    base = dict(
        source="usgs",
        source_id="us7000abcd",
        hazard="earthquake",
        name="M 4.5 - 10km NE of Somewhere, CA",
        lat=36.5,
        lon=-118.2,
        severity="4.5",
        observed_utc="20260819T120000Z",
        properties={"depth_km": 8.1},
    )
    base.update(overrides)
    return WatchEvent(**base)


class TestWatchEvent(unittest.TestCase):
    def test_as_feature_is_valid_geojson_point(self) -> None:
        feature = event().as_feature()
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"], {"type": "Point", "coordinates": [-118.2, 36.5]})
        props = feature["properties"]
        self.assertEqual(props["source"], "usgs")
        self.assertEqual(props["hazard"], "earthquake")
        self.assertEqual(props["severity"], "4.5")
        self.assertEqual(props["depth_km"], 8.1)

    def test_extra_properties_do_not_shadow_core_fields(self) -> None:
        feature = event(properties={"source": "spoof"}).as_feature()
        self.assertEqual(feature["properties"]["source"], "usgs")


class TestSnapshotStore(unittest.TestCase):
    def test_save_snapshot_appends_index_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = save_snapshot(root, "usgs", {"a": 1})
            second = save_snapshot(root, "usgs", {"a": 2})
            self.assertTrue(first.exists() and second.exists())
            self.assertNotEqual(first, second)
            index = root / "snapshots" / "capture_index.jsonl"
            rows = [json.loads(line) for line in index.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["source"], "usgs")
            self.assertTrue(rows[0]["utc"].endswith("Z"))
            self.assertEqual(json.loads(first.read_text())["a"], 1)


if __name__ == "__main__":
    unittest.main()
