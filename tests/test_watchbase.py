"""Tier-1 watch foundations: event model and append-only snapshot store."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from geosteward.sources.watchbase import HEADERS, WatchEvent, merge_pages, save_snapshot


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

    def test_snapshots_are_gzip_compressed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = save_snapshot(root, "usgs", {"a": 1})
            self.assertTrue(path.name.endswith(".json.gz"))
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["a"], 1)

    def test_same_second_collision_suffixes_filename_not_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = save_snapshot(root, "usgs", {"a": 1})
            second = save_snapshot(root, "usgs", {"a": 2})
            index = root / "snapshots" / "capture_index.jsonl"
            rows = [json.loads(line) for line in index.read_text().splitlines()]
            for row in rows:
                self.assertRegex(row["utc"], r"^\d{8}T\d{6}Z$")
            if first.name != second.name and rows[0]["utc"] == rows[1]["utc"]:
                self.assertNotEqual(first.stem, second.stem)


class TestMergePages(unittest.TestCase):
    def test_merges_features_from_multiple_pages(self) -> None:
        page1 = {"type": "FeatureCollection", "features": [{"id": "a"}, {"id": "b"}]}
        page2 = {"type": "FeatureCollection", "features": [{"id": "c"}]}
        merged = merge_pages([page1, page2])
        self.assertEqual(merged["type"], "FeatureCollection")
        self.assertEqual([f["id"] for f in merged["features"]], ["a", "b", "c"])

    def test_drops_pagination_key_from_merged_result(self) -> None:
        page1 = {
            "type": "FeatureCollection",
            "features": [{"id": "a"}],
            "pagination": {"next": "https://example.com/page2"},
        }
        page2 = {"type": "FeatureCollection", "features": [{"id": "b"}]}
        merged = merge_pages([page1, page2])
        self.assertNotIn("pagination", merged)


class TestHeaders(unittest.TestCase):
    def test_user_agent_identifies_geosteward(self) -> None:
        self.assertIn("GeoSteward-watch", HEADERS["User-Agent"])
        self.assertIn("github.com/rayford295/GeoSteward", HEADERS["User-Agent"])
        self.assertNotIn("@", HEADERS["User-Agent"])


if __name__ == "__main__":
    unittest.main()
