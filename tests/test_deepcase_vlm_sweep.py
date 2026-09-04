"""Multi-model VLM runs: tagged output paths, the comparison table built from
committed eval summaries, and the sweep driver's planning — none of it needs
a model."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from geosteward.deepcase.vlm_severity import model_slug, tagged_path

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestTaggedPaths(unittest.TestCase):
    def test_slug_is_filesystem_safe_and_stable(self) -> None:
        self.assertEqual(model_slug("qwen3-vl:32b"), "qwen3-vl-32b")
        self.assertEqual(model_slug("Mistral-Small3.2:24b"), "mistral-small3.2-24b")
        self.assertEqual(model_slug("hf.co/org/model:Q4_K_M"), "hf.co-org-model-q4-k-m")

    def test_slug_refuses_an_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            model_slug(":::")

    def test_tag_goes_before_the_suffix_and_keeps_the_directory(self) -> None:
        self.assertEqual(tagged_path("evidence/vlm_crossview_predictions.jsonl", "gemma3-27b"),
                         "evidence/vlm_crossview_predictions.gemma3-27b.jsonl")
        self.assertEqual(tagged_path("evidence/vlm_severity_h3_r9_grid.geojson", "x"),
                         "evidence/vlm_severity_h3_r9_grid.x.geojson")

    def test_no_tag_is_the_reference_run(self) -> None:
        self.assertEqual(tagged_path("evidence/vlm_bitemporal_eval.json", None), "evidence/vlm_bitemporal_eval.json")
        self.assertEqual(tagged_path("evidence/vlm_bitemporal_eval.json", ""), "evidence/vlm_bitemporal_eval.json")

    def test_every_builder_exposes_run_tag(self) -> None:
        for script in ("build_eaton_vlm.py", "build_milton_vlm_bitemporal.py", "build_palisades_vlm.py"):
            self.assertIn('"--run-tag"', (REPO / "scripts" / script).read_text(encoding="utf-8"), script)


def _eval(event, task, model, acc, tag=None, **extra):
    doc = {
        "event_id": event, "model": model, "model_digest": "abc123def456789", "prompt_sha256": "p" * 64,
        "temperature": 0.0, "run_id": "r1", "run_tag": tag, "sample_per_class": 100, "seed": 2026,
        "n_images": 300, "n_scored": 300, "unanswered_rate": 0.0, "accuracy": acc, "ncse": 0.2,
        "adjacent_error_rate": 0.3, "classes": ["a", "b", "c"],
        "per_class": {"a": {"support": 100, "recall": 0.5}, "b": {"support": 100, "recall": 0.3}, "c": {"support": 100, "recall": 0.9}},
    }
    doc.update(extra)
    doc["_task"] = task
    doc["_file"] = f"events/{event}/evidence/{task}{'.' + tag if tag else ''}.json"
    return doc


class TestComparison(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load("compare_vlm_models")

    def test_blocks_are_per_event_and_task_and_rows_sorted_best_first(self) -> None:
        comp = self.mod.build_comparison([
            _eval("milton-2024", "vlm_bitemporal_eval", "qwen2.5vl:7b", 0.5967),
            _eval("milton-2024", "vlm_bitemporal_eval", "gemma3:27b", 0.71, tag="gemma3-27b"),
            _eval("eaton-2025", "vlm_crossview_eval", "qwen2.5vl:7b", 0.9095),
        ])
        self.assertEqual([b["event_id"] for b in comp["blocks"]], ["eaton-2025", "milton-2024"])
        milton = comp["blocks"][1]
        self.assertEqual([r["model"] for r in milton["rows"]], ["gemma3:27b", "qwen2.5vl:7b"])
        self.assertEqual(milton["rows"][1]["run_tag"], "reference")

    def test_a_different_setup_is_flagged_not_dropped(self) -> None:
        comp = self.mod.build_comparison([
            _eval("milton-2024", "vlm_bitemporal_eval", "qwen2.5vl:7b", 0.59),
            _eval("milton-2024", "vlm_bitemporal_eval", "gemma3:27b", 0.61, tag="gemma3-27b", sample_per_class=50),
            _eval("milton-2024", "vlm_bitemporal_eval", "llama3.2-vision:11b", 0.4, tag="llama", prompt_sha256="q" * 64),
        ])
        rows = {r["model"]: r for r in comp["blocks"][0]["rows"]}
        self.assertTrue(rows["qwen2.5vl:7b"]["same_setup"])
        self.assertFalse(rows["gemma3:27b"]["same_setup"])
        self.assertFalse(rows["llama3.2-vision:11b"]["same_setup"])
        self.assertEqual(len(rows), 3)

    def test_reference_setup_is_the_untagged_run_when_present(self) -> None:
        comp = self.mod.build_comparison([
            _eval("e", "vlm_crossview_eval", "a", 0.5, tag="a", sample_per_class=10),
            _eval("e", "vlm_crossview_eval", "b", 0.5, tag="b", sample_per_class=10),
            _eval("e", "vlm_crossview_eval", "ref", 0.5, sample_per_class=300),
        ])
        self.assertEqual(comp["blocks"][0]["reference_setup"]["sample_per_class"], 300)

    def test_paper_numbers_come_from_the_eval_file_and_render_as_reference_rows(self) -> None:
        comp = self.mod.build_comparison([
            _eval("palisades-2025", "vlm_severity_eval", "qwen2.5vl:7b", 0.47,
                  reference={"reported_accuracy": {"GPT-5.1": 0.570}, "note": "paper numbers"}),
        ])
        md = self.mod.render_markdown(comp)
        self.assertIn("GPT-5.1 (paper, closed API)", md)
        self.assertIn("0.570", md)
        self.assertIn("> paper numbers", md)
        self.assertIn("**0.4700**", md)

    def test_finds_tagged_and_untagged_eval_files_and_skips_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("milton-2024/evidence/vlm_bitemporal_eval.json",
                        "milton-2024/evidence/vlm_bitemporal_eval.gemma3-27b.json",
                        "milton-2024/evidence/vlm_bitemporal_predictions.jsonl",
                        "milton-2024/evidence/vlm_bitemporal_h3_r9_grid.geojson",
                        "archive/old/evidence/vlm_severity_eval.json"):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("{}", encoding="utf-8")
            found = [f.name for f in self.mod.find_eval_files(root)]
        self.assertEqual(found, ["vlm_bitemporal_eval.gemma3-27b.json", "vlm_bitemporal_eval.json"])

    def test_load_eval_derives_task_tag_and_event_from_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "eaton-2025" / "evidence" / "vlm_crossview_eval.qwen3-vl-32b.json"
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"accuracy": 0.9}), encoding="utf-8")
            doc = self.mod.load_eval(p)
        self.assertEqual((doc["_task"], doc["run_tag"], doc["event_id"]), ("vlm_crossview_eval", "qwen3-vl-32b", "eaton-2025"))

    def test_the_committed_tree_renders(self) -> None:
        docs = [self.mod.load_eval(p) for p in self.mod.find_eval_files(REPO / "events")]
        self.assertGreaterEqual(len(docs), 3)  # Palisades, Milton, Eaton reference runs
        md = self.mod.render_markdown(self.mod.build_comparison(docs))
        for needle in ("palisades-2025", "milton-2024", "eaton-2025", "qwen2.5vl:7b"):
            self.assertIn(needle, md)


class TestSweepPlanning(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load("run_vlm_sweep")

    def _args(self, **kw):
        import argparse
        base = dict(palisades_images=None, milton_images=None, milton_pairs_csv=None, milton_sample=100,
                    eaton_dataset=None, eaton_sample=300, seed=2026)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_a_case_without_its_data_is_not_planned(self) -> None:
        a = self._args(eaton_dataset=Path("/data/eaton"))
        self.assertIsNone(self.mod.builder_command("palisades", a))
        self.assertIsNone(self.mod.builder_command("milton", a))
        cmd = self.mod.builder_command("eaton", a)
        self.assertIn("scripts/build_eaton_vlm.py", cmd)
        self.assertEqual(cmd[cmd.index("--run-tag") + 1], "auto")
        self.assertEqual(cmd[cmd.index("--sample") + 1], "300")
        self.assertEqual(cmd[cmd.index("--seed") + 1], "2026")

    def test_every_case_runs_tagged_auto(self) -> None:
        a = self._args(palisades_images=Path("p"), milton_images=Path("m"), milton_pairs_csv=Path("m.csv"), eaton_dataset=Path("e"))
        for case in self.mod.CASES:
            cmd = self.mod.builder_command(case, a)
            self.assertIn("--run-tag", cmd, case)
            self.assertEqual(cmd[cmd.index("--run-tag") + 1], "auto", case)

    def test_eval_files_match_what_the_builders_write(self) -> None:
        for case, rel in self.mod.EVAL_FILE.items():
            script = {"palisades": "build_palisades_vlm.py", "milton": "build_milton_vlm_bitemporal.py", "eaton": "build_eaton_vlm.py"}[case]
            src = (REPO / "scripts" / script).read_text(encoding="utf-8")
            self.assertIn(f'"{rel.split("/", 2)[2]}"', src, (case, rel))

    def test_unreachable_server_means_no_models_not_an_exception(self) -> None:
        self.assertEqual(self.mod.served_models("http://127.0.0.1:9/v1"), {})
        self.assertIsNone(self.mod.placement("http://127.0.0.1:9/v1", "x"))


if __name__ == "__main__":
    unittest.main()
