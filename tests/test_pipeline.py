from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from disasterpilot.pipeline import run_pre_event

SNAPSHOT = {
    "tfid": "209999",
    "name": "测试",
    "enname": "TESTSTORM",
    "isactive": "1",
    "land": [],
    "points": [
        {
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
        },
        {
            "time": "2026-07-09 05:00:00",
            "lng": "126.00",
            "lat": "22.00",
            "strong": "台风",
            "power": "13",
            "speed": "40",
            "pressure": "955",
            "movespeed": "20",
            "movedirection": "西北",
            "radius7": "280|260|240|280",
            "radius10": "",
            "radius12": "",
        },
    ],
}


class OfflinePipelineTests(unittest.TestCase):
    def run_offline(self, events_root: Path) -> dict:
        event_dir = events_root / "teststorm-2026" / "snapshots"
        event_dir.mkdir(parents=True)
        (event_dir / "teststorm_20260709T000000Z.json").write_text(
            json.dumps(SNAPSHOT, ensure_ascii=False), encoding="utf-8"
        )
        return run_pre_event(
            "teststorm-2026", "209999", events_root=events_root, skip_watcher=True
        )

    def test_offline_pipeline_produces_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_root = Path(tmp)
            report = self.run_offline(events_root)
            statuses = {stage["agent"]: stage["status"] for stage in report["stages"]}
            self.assertTrue(statuses["watcher.typhoon"].startswith("skipped"))
            self.assertEqual(statuses["dossier.typhoon"], "ok")
            self.assertEqual(statuses["exposure.typhoon"], "ok")
            self.assertEqual(statuses["decision.watch_bulletin"], "ok")

            event_dir = events_root / "teststorm-2026"
            record = json.loads(
                (event_dir / "dossier" / "event_record.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["track"]["peak_pressure_hpa"], 920.0)

            footprints = json.loads(
                (event_dir / "exposure" / "wind_footprints.geojson").read_text(encoding="utf-8")
            )
            # point 1 has 3 thresholds, point 2 only radius7
            self.assertEqual(len(footprints["features"]), 4)

            bulletin = json.loads(
                (event_dir / "decision" / "watch_bulletin.json").read_text(encoding="utf-8")
            )
            self.assertTrue(bulletin["declared_unknowns"])
            self.assertTrue((event_dir / "decision" / "watch_bulletin.md").exists())
            manifest_lines = (
                (event_dir / "artifact_manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
            )
            self.assertEqual(len(manifest_lines), 4)

    def test_pipeline_fails_closed_without_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_pre_event(
                "empty-2026", "209998", events_root=Path(tmp), skip_watcher=True
            )
            statuses = [stage["status"] for stage in report["stages"]]
            self.assertTrue(any(status.startswith("failed") for status in statuses))


class EvidenceFailClosedTests(unittest.TestCase):
    def test_evidence_agent_requires_imagery(self) -> None:
        from disasterpilot.agents.base import EventContext
        from disasterpilot.agents.evidence import CrossViewEvidence

        with tempfile.TemporaryDirectory() as tmp:
            context = EventContext(
                event_id="x", event_dir=Path(tmp), hazard="typhoon"
            )
            with self.assertRaises(FileNotFoundError):
                CrossViewEvidence().run(context)


if __name__ == "__main__":
    unittest.main()
