"""Process validity: append-only audit log and artifact hashing."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from geosteward.agents.base import Artifact, EventContext
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


class TestRunIdentity(unittest.TestCase):
    """Every row carries the run that wrote it.

    Without this, reconstructing runs from an append-only log means inferring
    boundaries from timestamps and check sequences — which the frontend still
    does for logs written before `run_id` existed, because those logs are not
    rewritten. New logs should not need the inference.
    """

    def test_rows_from_one_log_share_a_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = AuditLog(Path(tmp) / "audit_log.jsonl")
            log.record("check", "stage.a", payload={"check": "crs", "passed": True})
            log.record("stage", "stage.a", payload={"status": "ok"})
            rows = [json.loads(line) for line in log.path.read_text().splitlines()]
            self.assertTrue(rows[0]["run_id"])
            self.assertEqual(rows[0]["run_id"], rows[1]["run_id"])

    def test_separate_logs_get_separate_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = AuditLog(Path(tmp) / "a.jsonl")
            second = AuditLog(Path(tmp) / "b.jsonl")
            first.record("stage", "stage.a", payload={"status": "ok"})
            second.record("stage", "stage.a", payload={"status": "ok"})
            a = json.loads(first.path.read_text().splitlines()[0])["run_id"]
            b = json.loads(second.path.read_text().splitlines()[0])["run_id"]
            self.assertNotEqual(a, b)

    def test_run_id_can_be_supplied_so_a_rerun_is_distinguishable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit_log.jsonl"
            AuditLog(path, run_id="run-one").record("stage", "stage.a", payload={"status": "failed"})
            AuditLog(path, run_id="run-two").record("stage", "stage.a", payload={"status": "ok"})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r["run_id"] for r in rows], ["run-one", "run-two"])


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


class TestRegisterHashesArtifactsWithoutSha256(unittest.TestCase):
    def test_register_fills_sha256_for_directly_registered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = EventContext(
                event_id="teststorm-2026",
                event_dir=Path(tmp) / "teststorm-2026",
                hazard="hurricane",
            )
            md_path = context.event_dir / "decision" / "watch_bulletin.md"
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text("# Watch bulletin\n", encoding="utf-8")
            artifact = context.register(
                Artifact(
                    path=md_path,
                    kind="watch_bulletin_md",
                    agent="decision.watch_bulletin",
                    created_utc="20260101T000000Z",
                    sha256="",
                )
            )
            self.assertEqual(artifact.sha256, sha256_file(md_path))
            manifest = context.event_dir / "artifact_manifest.jsonl"
            row = json.loads(manifest.read_text().splitlines()[-1])
            self.assertEqual(row["sha256"], sha256_file(md_path))


if __name__ == "__main__":
    unittest.main()
