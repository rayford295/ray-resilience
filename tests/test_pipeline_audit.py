"""Every pipeline stage — including failures — leaves an audit row."""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.pipeline import run_pre_event


class TestPipelineAudit(unittest.TestCase):
    def test_failed_offline_run_still_writes_stage_audit_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_root = Path(tmp)
            report = run_pre_event(
                event_id="teststorm-2026",
                tfid="000000",
                events_root=events_root,
                skip_watcher=True,
            )
            audit_path = events_root / "teststorm-2026" / "audit_log.jsonl"
            self.assertTrue(audit_path.exists())
            rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
            self.assertEqual(len(rows), len(report["stages"]))
            self.assertTrue(all(row["action"] == "stage" for row in rows))
            statuses = [row["payload"]["status"] for row in rows]
            self.assertTrue(any(status.startswith("failed") for status in statuses))


if __name__ == "__main__":
    unittest.main()
