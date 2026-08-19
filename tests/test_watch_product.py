"""The watch product: harness-checked, fail-closed, unknowns declared."""

import unittest

from geosteward.sources.watchbase import WatchEvent
from geosteward.watch import build_watch_product


def event(source="usgs", lat=35.0, lon=-100.0, **overrides):
    base = dict(
        source=source,
        source_id=f"{source}-1",
        hazard="earthquake",
        name="test event",
        lat=lat,
        lon=lon,
        severity="1",
        observed_utc="20260819T000000Z",
        properties={},
    )
    base.update(overrides)
    return WatchEvent(**base)


class TestBuildWatchProduct(unittest.TestCase):
    def test_collection_carries_crs_and_all_valid_events(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event(), event(source="usgs")], 0)},
            failures={},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertEqual(collection["geosteward:crs"], "EPSG:4326")
        self.assertEqual(collection["geosteward:generated_utc"], "20260819T120000Z")
        self.assertEqual(len(collection["features"]), 2)
        self.assertEqual(status["sources"]["usgs"]["status"], "ok")
        self.assertEqual(status["sources"]["usgs"]["events"], 2)

    def test_out_of_bounds_events_dropped_and_counted(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event(), event(lat=95.0)], 0)},
            failures={},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(len(collection["features"]), 1)
        self.assertEqual(status["sources"]["usgs"]["dropped_bounds"], 1)

    def test_failed_source_recorded_never_fabricated(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event()], 0)},
            failures={"nhc": "HTTP 503"},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(status["sources"]["nhc"]["status"], "failed")
        self.assertEqual(status["sources"]["nhc"]["error"], "HTTP 503")
        self.assertEqual(status["sources"]["nhc"]["events"], 0)
        sources_in_features = {f["properties"]["source"] for f in collection["features"]}
        self.assertNotIn("nhc", sources_in_features)

    def test_declared_unknowns_always_present_and_name_failures(self) -> None:
        _, clean_status = build_watch_product(
            parsed={"usgs": ([event()], 0)}, failures={}, generated_utc="x"
        )
        self.assertTrue(
            any("monitoring only" in u for u in clean_status["declared_unknowns"])
        )
        _, degraded_status = build_watch_product(
            parsed={"usgs": ([event()], 2)},
            failures={"nifc": "timeout"},
            generated_utc="x",
        )
        joined = " ".join(degraded_status["declared_unknowns"])
        self.assertIn("nifc", joined)
        self.assertIn("skipped", joined)


if __name__ == "__main__":
    unittest.main()
