"""WPC ERO connector: label mapping, fail-closed shapes, product self-account."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from geosteward.sources import wpc_ero

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_watch", REPO / "scripts" / "run_watch.py")
run_watch_module = importlib.util.module_from_spec(spec)
sys.modules["run_watch_ero_test"] = run_watch_module
spec.loader.exec_module(run_watch_module)


def _feat(outlook, geometry=True):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]} if geometry else None,
        "properties": {"outlook": outlook, "issue_time": "2026-09-02 00:50:00",
                       "start_time": "s", "end_time": "e"},
    }


class ParseTest(unittest.TestCase):
    def test_maps_the_four_wpc_labels_to_ordinal_levels(self):
        payload = {"features": [_feat("High (At Least 70%)"), _feat("Marginal (At Least 5%)"),
                                _feat("Slight (At Least 15%)"), _feat("Moderate (At Least 40%)")]}
        features, skipped = wpc_ero.parse(payload)
        self.assertEqual(skipped, 0)
        self.assertEqual([f["properties"]["level"] for f in features], [1, 2, 3, 4])

    def test_probability_suffix_may_change_without_dropping_polygons(self):
        features, skipped = wpc_ero.parse({"features": [_feat("Moderate (At Least 39.9%)")]})
        self.assertEqual((len(features), skipped), (1, 0))

    def test_unknown_label_and_missing_geometry_are_skipped_never_guessed(self):
        payload = {"features": [_feat("Apocalyptic (At Least 99%)"), _feat("Slight", geometry=False)]}
        features, skipped = wpc_ero.parse(payload)
        self.assertEqual((len(features), skipped), (0, 2))

    def test_arcgis_error_envelope_fails_closed(self):
        with self.assertRaises(RuntimeError):
            wpc_ero.raise_on_arcgis_error({"error": {"code": 400}})


class ProductTest(unittest.TestCase):
    def test_product_carries_its_own_boundary_and_counts(self):
        features, skipped = wpc_ero.parse({"features": [_feat("Moderate (At Least 40%)")]})
        product = wpc_ero.build_flood_outlook(features, skipped, "20260902T000000Z")
        props = product["properties"]
        self.assertEqual(props["n_areas"], 1)
        self.assertIn("Outlook only", props["declared_boundary"])
        self.assertIn("not observed flooding", props["declared_boundary"].lower().replace("flooding and", "flooding and"))
        self.assertEqual(props["issue_time"], "2026-09-02 00:50:00")


class RunWatchIntegrationTest(unittest.TestCase):
    def test_outlook_failure_is_recorded_and_never_blocks_the_watch(self):
        broken = types.SimpleNamespace(
            SOURCE="wpc_ero",
            fetch=lambda timeout=30: (_ for _ in ()).throw(RuntimeError("HTTP 503")),
            parse=wpc_ero.parse,
            build_flood_outlook=wpc_ero.build_flood_outlook,
        )
        with tempfile.TemporaryDirectory() as tmp:
            status = run_watch_module.run_watch(
                connectors=[], live_root=Path(tmp), outlook_connector=broken
            )
            self.assertEqual(status["flood_outlook"]["status"], "failed")
            self.assertIn("503", status["flood_outlook"]["error"])
            self.assertFalse((Path(tmp) / "products" / "flood_outlook.geojson").exists())

    def test_outlook_success_writes_the_product_and_status_key(self):
        okay = types.SimpleNamespace(
            SOURCE="wpc_ero",
            fetch=lambda timeout=30: {"features": [_feat("Slight (At Least 15%)")]},
            parse=wpc_ero.parse,
            build_flood_outlook=wpc_ero.build_flood_outlook,
        )
        with tempfile.TemporaryDirectory() as tmp:
            status = run_watch_module.run_watch(
                connectors=[], live_root=Path(tmp), outlook_connector=okay
            )
            self.assertEqual(status["flood_outlook"], {
                "status": "ok", "areas": 1, "skipped": 0, "error": None,
            })
            product = json.loads((Path(tmp) / "products" / "flood_outlook.geojson").read_text())
            self.assertEqual(product["properties"]["n_areas"], 1)


if __name__ == "__main__":
    unittest.main()
