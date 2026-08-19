"""Process validity: append-only audit log and artifact hashing."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from geosteward.agents.base import EventContext
from geosteward.harness.audit import AuditLog, sha256_file


class TestSha256File(unittest.TestCase):
    def test_hash_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            path.write_text('{"a": 1}', encoding="utf-8")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(sha256_file(path), expected)


class TestAuditLog(unittest.TestCase):
    def test_record_appends_jsonl_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = AuditLog(Path(tmp) / "audit_log.jsonl")
            log.record("stage", "watcher.test", payload={"status": "ok"})
            log.record("refusal", "gateway", rule_id="deny-outside-aoi")
            rows = [json.loads(line) for line in log.path.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["action"], "stage")
            self.assertEqual(rows[0]["payload"], {"status": "ok"})
            self.assertEqual(rows[1]["rule_id"], "deny-outside-aoi")
            self.assertTrue(rows[0]["utc"].endswith("Z"))


class TestManifestHashing(unittest.TestCase):
    def test_write_json_records_sha256_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = EventContext(
                event_id="teststorm-2026",
                event_dir=Path(tmp) / "teststorm-2026",
                hazard="hurricane",
            )
            artifact = context.write_json(
                "dossier/record.json", {"a": 1}, kind="dossier", agent="dossier.test"
            )
            self.assertEqual(artifact.sha256, sha256_file(artifact.path))
            manifest = context.event_dir / "artifact_manifest.jsonl"
            row = json.loads(manifest.read_text().splitlines()[-1])
            self.assertEqual(row["sha256"], artifact.sha256)


if __name__ == "__main__":
    unittest.main()
