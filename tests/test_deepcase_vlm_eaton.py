"""The Eaton cross-view VLM stage: the collapse from the prompt's five DINS
classes to the matched set's three repairability classes, and the builder's
sample loading, without a model."""

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from geosteward.deepcase.vlm_severity import (
    DINS5_TO_REPAIRABILITY3,
    REPAIRABILITY_CLASSES,
    WILDFIRE_CLASSES,
    aggregate_h3,
    collapse_wildfire_prediction,
)

REPO = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_eaton_vlm", REPO / "scripts" / "build_eaton_vlm.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_eaton_vlm"] = module
    spec.loader.exec_module(module)
    return module


class TestCollapse(unittest.TestCase):
    def test_every_prompt_class_collapses_onto_a_truth_class(self) -> None:
        for c in WILDFIRE_CLASSES:
            self.assertIn(collapse_wildfire_prediction(c), REPAIRABILITY_CLASSES)

    def test_collapse_is_monotone_in_the_ordinal(self) -> None:
        # Coarsening must not reorder severity: a worse DINS class never maps
        # to a better repairability class.
        rank = {c: i for i, c in enumerate(REPAIRABILITY_CLASSES)}
        collapsed = [rank[DINS5_TO_REPAIRABILITY3[c]] for c in WILDFIRE_CLASSES]
        self.assertEqual(collapsed, sorted(collapsed))

    def test_dins_semantics(self) -> None:
        self.assertEqual(collapse_wildfire_prediction("1_Affected_1_9"), "no_or_trace_damage")
        self.assertEqual(collapse_wildfire_prediction("2_Minor_10_25"), "damaged_repairable")
        self.assertEqual(collapse_wildfire_prediction("3_Major_26_50"), "damaged_repairable")
        self.assertEqual(collapse_wildfire_prediction("4_Destroyed_50plus"), "destroyed")

    def test_no_prediction_stays_no_prediction(self) -> None:
        self.assertIsNone(collapse_wildfire_prediction(None))

    def test_a_label_outside_the_prompt_is_an_error_not_a_guess(self) -> None:
        with self.assertRaises(KeyError):
            collapse_wildfire_prediction("Severe")


class TestAggregateLocationSource(unittest.TestCase):
    def test_location_source_is_written_into_every_cell(self) -> None:
        records = [
            {"lat": 34.19, "lon": -118.13, "truth": "destroyed", "pred": "destroyed", "status": "ok"},
            {"lat": 34.19, "lon": -118.13, "truth": "destroyed", "pred": "no_or_trace_damage", "status": "ok"},
        ]
        features = aggregate_h3(records, REPAIRABILITY_CLASSES, location_source="dataset manifest")
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"]["uncertainty"]["location_source"], "dataset manifest")
        self.assertTrue(features[0]["properties"]["uncertainty"]["model_derived"])

    def test_default_location_source_is_still_exif(self) -> None:
        records = [{"lat": 34.19, "lon": -118.13, "truth": "destroyed", "pred": "destroyed", "status": "ok"}]
        features = aggregate_h3(records, REPAIRABILITY_CLASSES)
        self.assertIn("EXIF", features[0]["properties"]["uncertainty"]["location_source"])


MANIFEST_COLUMNS = [
    "sample_id", "split", "label", "label_name", "target", "post_latitude", "post_longitude",
    "match_quality", "post_event_field_path", "post_event_remote_path",
]


def _write_dataset(root: Path, rows: list[dict]) -> None:
    (root / "images" / "post_event_field").mkdir(parents=True)
    (root / "images" / "post_event_remote").mkdir(parents=True)
    with (root / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k in MANIFEST_COLUMNS})
            if r.get("_write_image", True):
                (root / r["post_event_field_path"]).write_bytes(b"\xff\xd8" + r["sample_id"].encode())
                (root / r["post_event_remote_path"]).write_bytes(b"\xff\xd8R" + r["sample_id"].encode())


def _row(i: int, label: str, quality: str, *, write_image: bool = True) -> dict:
    sid = f"sample_{i:05d}"
    return {
        "sample_id": sid, "split": "model_fit", "label": "0", "label_name": label, "target": label,
        "post_latitude": f"{34.19 + i * 1e-4:.6f}", "post_longitude": f"{-118.13 - i * 1e-4:.6f}",
        "match_quality": quality,
        "post_event_field_path": f"images/post_event_field/{sid}_post_field.jpg",
        "post_event_remote_path": f"images/post_event_remote/{sid}_post_remote.jpg",
        "_write_image": write_image,
    }


class TestLoadSamples(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = _load_builder()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        rows = [
            _row(1, "destroyed", "good"),
            _row(2, "no_or_trace_damage", "usable"),
            _row(3, "damaged_repairable", "good"),
            _row(4, "destroyed", "poor"),                       # fails the quality gate
            _row(5, "Destroyed", "good"),                       # not a dataset label as spelled
            _row(6, "destroyed", "good", write_image=False),    # manifest row, no file
        ]
        _write_dataset(self.root, rows)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gates_and_drops_are_counted_not_silent(self) -> None:
        samples, dropped = self.builder.load_samples(self.root, "post_field", ("good", "usable"))
        self.assertEqual([s["sample_id"] for s in samples], ["sample_00001", "sample_00002", "sample_00003"])
        self.assertEqual(dropped, {"quality_gate": 1, "bad_label": 1, "missing_image": 1})

    def test_quality_gate_is_the_callers_list(self) -> None:
        samples, dropped = self.builder.load_samples(self.root, "post_field", ("good",))
        self.assertEqual([s["sample_id"] for s in samples], ["sample_00001", "sample_00003"])
        self.assertEqual(dropped["quality_gate"], 2)

    def test_view_selects_the_image_column(self) -> None:
        field, _ = self.builder.load_samples(self.root, "post_field", ("good",))
        remote, _ = self.builder.load_samples(self.root, "post_remote", ("good",))
        self.assertTrue(field[0]["image"].name.endswith("_post_field.jpg"))
        self.assertTrue(remote[0]["image"].name.endswith("_post_remote.jpg"))

    def test_coordinates_come_from_the_post_event_point(self) -> None:
        samples, _ = self.builder.load_samples(self.root, "post_field", ("good",))
        self.assertAlmostEqual(samples[0]["lat"], 34.1901, places=4)
        self.assertAlmostEqual(samples[0]["lon"], -118.1301, places=4)

    def test_stratified_sample_caps_each_class_and_is_seeded(self) -> None:
        samples = [
            {"truth": "destroyed", "i": i} for i in range(10)
        ] + [
            {"truth": "no_or_trace_damage", "i": i} for i in range(10)
        ] + [
            {"truth": "damaged_repairable", "i": i} for i in range(2)
        ]
        a = self.builder.stratified(samples, 3, seed=7)
        b = self.builder.stratified(samples, 3, seed=7)
        self.assertEqual(a, b)
        by_class = {c: sum(1 for s in a if s["truth"] == c) for c in REPAIRABILITY_CLASSES}
        # The minority class is fully included when it is smaller than the cap.
        self.assertEqual(by_class, {"no_or_trace_damage": 3, "damaged_repairable": 2, "destroyed": 3})


if __name__ == "__main__":
    unittest.main()
