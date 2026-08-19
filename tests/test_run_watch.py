"""Orchestration: fail-closed per source, audited, products written."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_watch", REPO / "scripts" / "run_watch.py")
run_watch_module = importlib.util.module_from_spec(spec)
sys.modules["run_watch"] = run_watch_module
spec.loader.exec_module(run_watch_module)

from geosteward.sources.watchbase import WatchEvent  # noqa: E402


def fake_connector(source: str, ok: bool) -> types.SimpleNamespace:
    def fetch(timeout: int = 30):
        if not ok:
            raise RuntimeError("HTTP 503")
        return {"payload": source}

    def parse(payload):
        return (
            [
                WatchEvent(
                    source=source,
                    source_id=f"{source}-1",
                    hazard="test",
                    name="event",
                    lat=30.0,
                    lon=-90.0,
                    severity="1",
                    observed_utc="20260819T000000Z",
                    properties={},
                )
            ],
            0,
        )

    return types.SimpleNamespace(SOURCE=source, fetch=fetch, parse=parse)


class TestRunWatch(unittest.TestCase):
    def test_failed_source_does_not_block_others_and_all_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live_root = Path(tmp)
            status = run_watch_module.run_watch(
                connectors=[fake_connector("good", True), fake_connector("bad", False)],
                live_root=live_root,
            )
            self.assertEqual(status["sources"]["good"]["status"], "ok")
            self.assertEqual(status["sources"]["bad"]["status"], "failed")
            collection = json.loads(
                (live_root / "products" / "national_watch.geojson").read_text()
            )
            self.assertEqual(len(collection["features"]), 1)
            written_status = json.loads(
                (live_root / "products" / "watch_status.json").read_text()
            )
            self.assertEqual(written_status["sources"]["bad"]["error"], "HTTP 503")
            snapshots = list((live_root / "snapshots").glob("good_*.json"))
            self.assertEqual(len(snapshots), 1)
            audit_rows = [
                json.loads(line)
                for line in (live_root / "audit_log.jsonl").read_text().splitlines()
            ]
            actions = [row["action"] for row in audit_rows]
            self.assertIn("source_ok", actions)
            self.assertIn("source_failed", actions)
            self.assertIn("product_built", actions)


if __name__ == "__main__":
    unittest.main()
