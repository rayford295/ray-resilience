"""Dossier maintenance: retiring a declared unknown once an artifact resolves it.

A declared unknown is a promise about what the record does NOT support. When a
later stage lands the artifact that makes the promise untrue, the unknown must
be retired in the same accountable way it was declared: a new dossier version
with its own manifest row and audit trail, never a hand edit.
"""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.agents.base import EventContext
from geosteward.deepcase.dossier import (
    DossierError,
    load_manifest_rows,
    retire_unknown,
)
from geosteward.harness.audit import AuditLog, sha256_file

EVENTS_ROOT = Path(__file__).resolve().parents[1] / "events"
SVI_PENDING = "social-vulnerability join (SVI x exposure) pending: no vulnerability claims yet"


def _seed_event(tmp: Path) -> tuple[EventContext, AuditLog]:
    ctx = EventContext(event_id="testfire-2026", event_dir=tmp / "testfire-2026", hazard="wildfire")
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    ctx.write_json(
        "dossier/event_record.json",
        {
            "event_id": "testfire-2026",
            "declared_unknowns": ["40 points inaccessible", SVI_PENDING],
        },
        kind="event_record",
        agent="dossier.event_record",
    )
    ctx.write_json(
        "exposure/svi_h3_r9_context.geojson",
        {"type": "FeatureCollection", "features": []},
        kind="svi_context_grid",
        agent="exposure.svi_context",
    )
    return ctx, audit


class TestRetireUnknown(unittest.TestCase):
    def test_moves_unknown_to_resolved_and_versions_the_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx, audit = _seed_event(Path(tmp))
            before = sha256_file(ctx.event_dir / "dossier" / "event_record.json")

            artifact = retire_unknown(
                ctx,
                audit,
                stage="exposure.svi_context",
                unknown=SVI_PENDING,
                resolved_by="exposure/svi_h3_r9_context.geojson",
            )

            record = json.loads(artifact.path.read_text(encoding="utf-8"))
            self.assertEqual(record["declared_unknowns"], ["40 points inaccessible"])
            self.assertEqual(len(record["resolved_unknowns"]), 1)
            resolved = record["resolved_unknowns"][0]
            self.assertEqual(resolved["unknown"], SVI_PENDING)
            self.assertEqual(resolved["resolved_by"], "exposure/svi_h3_r9_context.geojson")
            self.assertRegex(resolved["resolved_utc"], r"^\d{8}T\d{6}Z$")
            self.assertEqual(resolved["resolved_by_sha256"], sha256_file(
                ctx.event_dir / "exposure" / "svi_h3_r9_context.geojson"
            ))

            rows = load_manifest_rows(ctx.event_dir)
            record_rows = [r for r in rows if r["path"].endswith("event_record.json")]
            self.assertEqual(len(record_rows), 2, "old row kept, new row appended")
            self.assertEqual(record_rows[0]["sha256"], before)
            self.assertEqual(record_rows[-1]["sha256"], artifact.sha256)
            self.assertNotEqual(before, artifact.sha256)
            self.assertIn("exposure/svi_h3_r9_context.geojson", record_rows[-1]["inputs"])

            log = [json.loads(l) for l in (ctx.event_dir / "audit_log.jsonl").read_text().splitlines()]
            stage_rows = [r for r in log if r["action"] == "stage" and r["actor"] == "exposure.svi_context"]
            self.assertEqual(stage_rows[-1]["payload"]["retired_unknown"], SVI_PENDING)
            self.assertEqual(stage_rows[-1]["payload"]["status"], "ok")

    def test_retiring_twice_is_a_noop_second_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx, audit = _seed_event(Path(tmp))
            first = retire_unknown(ctx, audit, stage="s", unknown=SVI_PENDING,
                                   resolved_by="exposure/svi_h3_r9_context.geojson")
            second = retire_unknown(ctx, audit, stage="s", unknown=SVI_PENDING,
                                    resolved_by="exposure/svi_h3_r9_context.geojson")
            self.assertIsNone(second)
            rows = [r for r in load_manifest_rows(ctx.event_dir) if r["path"].endswith("event_record.json")]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]["sha256"], first.sha256)

    def test_fails_closed_when_unknown_was_never_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx, audit = _seed_event(Path(tmp))
            with self.assertRaises(DossierError):
                retire_unknown(ctx, audit, stage="s", unknown="never said this",
                               resolved_by="exposure/svi_h3_r9_context.geojson")

    def test_fails_closed_when_resolving_artifact_is_not_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx, audit = _seed_event(Path(tmp))
            # On disk but never registered: a file nobody vouched for cannot retire a promise.
            orphan = ctx.event_dir / "exposure" / "orphan.geojson"
            orphan.write_text("{}", encoding="utf-8")
            with self.assertRaises(DossierError):
                retire_unknown(ctx, audit, stage="s", unknown=SVI_PENDING,
                               resolved_by="exposure/orphan.geojson")
            with self.assertRaises(DossierError):
                retire_unknown(ctx, audit, stage="s", unknown=SVI_PENDING,
                               resolved_by="exposure/does_not_exist.geojson")
            record = json.loads((ctx.event_dir / "dossier" / "event_record.json").read_text())
            self.assertIn(SVI_PENDING, record["declared_unknowns"], "record untouched on failure")


class TestCommittedDossiersAreNotStale(unittest.TestCase):
    """Regression guard over the committed events: a declared unknown must not
    outlive the artifact that resolves it. Milton and Ian legitimately keep the
    SVI line — neither has an SVI grid — so the guard is keyed on the manifest."""

    def test_svi_pending_is_not_declared_where_an_svi_grid_is_registered(self) -> None:
        for record_path in sorted(EVENTS_ROOT.glob("*/dossier/event_record.json")):
            with self.subTest(event=record_path.parents[1].name):
                rows = load_manifest_rows(record_path.parents[1])
                has_svi_grid = any(r["kind"] == "svi_context_grid" for r in rows)
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if record.get("model_derived") is True:
                    # An evaluation case (zero-shot predictions against labels)
                    # has no exposure line to be pending on; its dossier
                    # declares "no exposure layer, no SVI join" outright.
                    continue
                declares_pending = any(
                    "social-vulnerability join" in u for u in record.get("declared_unknowns", [])
                )
                if has_svi_grid:
                    self.assertFalse(declares_pending, "SVI grid registered but still declared pending")
                else:
                    self.assertTrue(declares_pending, "no SVI grid yet the pending line is gone")

    def test_resolved_unknowns_point_at_registered_artifacts(self) -> None:
        for record_path in sorted(EVENTS_ROOT.glob("*/dossier/event_record.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            rows = load_manifest_rows(record_path.parents[1])
            event_dir = record_path.parents[1]
            for resolved in record.get("resolved_unknowns", []):
                with self.subTest(event=event_dir.name, unknown=resolved["unknown"]):
                    matching = [r for r in rows if r["path"].endswith(resolved["resolved_by"])]
                    self.assertTrue(matching, "resolving artifact not in manifest")
                    self.assertEqual(matching[-1]["sha256"], resolved["resolved_by_sha256"])
                    self.assertTrue((event_dir / resolved["resolved_by"]).exists())


if __name__ == "__main__":
    unittest.main()
