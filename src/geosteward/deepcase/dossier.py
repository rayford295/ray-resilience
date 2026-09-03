"""Dossier maintenance: retire a declared unknown once an artifact resolves it.

A dossier's `declared_unknowns` are promises about what the event record does
NOT support. They are written by the case builder before downstream joins
exist, so a later stage can make one untrue — Eaton's SVI join did exactly
that in 2026-08, and the agent kept speaking the stale line to users because
the gateway feeds every declared unknown into its evidence context.

The fix has to keep the mechanism trustworthy: if unknowns can silently go
stale, "not listed as unknown" stops meaning "confirmed". So a retirement is
performed only by the stage that lands the resolving artifact, and it is done
the same accountable way the unknown was declared —

* the resolving artifact must already be REGISTERED in the manifest (a file on
  disk that nobody vouched for cannot retire a promise);
* the unknown is MOVED to `resolved_unknowns` with the resolver's path, sha256
  and time — never deleted, so the record keeps saying what it once could not
  support and why that changed;
* the record is rewritten through `EventContext.write_json`, which appends a
  new manifest row (new sha256) and leaves the earlier row in place; readers
  take the latest row per path, and the audit log gets a `stage` row.

Nothing here edits history: the manifest and audit log stay append-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.harness.audit import AuditLog

RECORD_PATH = "dossier/event_record.json"


class DossierError(RuntimeError):
    """A retirement that would leave the record less accountable than before."""


def load_manifest_rows(event_dir: Path) -> list[dict[str, Any]]:
    """All manifest rows for an event, oldest first (a path may appear more than once)."""
    manifest = Path(event_dir) / "artifact_manifest.jsonl"
    if not manifest.exists():
        return []
    return [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def latest_row_for(event_dir: Path, relative_path: str) -> dict[str, Any] | None:
    """The most recent manifest row whose path ends with `relative_path`, if any."""
    rows = [r for r in load_manifest_rows(event_dir) if r["path"].endswith(relative_path)]
    return rows[-1] if rows else None


def retire_unknown(
    ctx: EventContext,
    audit: AuditLog,
    *,
    stage: str,
    unknown: str,
    resolved_by: str,
    note: str = "",
) -> Artifact | None:
    """Move `unknown` from `declared_unknowns` to `resolved_unknowns`.

    Returns the new dossier artifact, or None when the unknown was already
    retired (so a stage can call this unconditionally on every run).
    Raises DossierError, leaving the record untouched, when the unknown was
    never declared or the resolving artifact is not a registered artifact.
    """
    record_path = ctx.event_dir / RECORD_PATH
    if not record_path.exists():
        raise DossierError(f"{record_path} does not exist; nothing to retire from")
    record = json.loads(record_path.read_text(encoding="utf-8"))

    already = [r for r in record.get("resolved_unknowns", []) if r.get("unknown") == unknown]
    declared = list(record.get("declared_unknowns", []))
    if unknown not in declared:
        if already:
            return None
        raise DossierError(f"unknown was never declared in {record_path}: {unknown!r}")

    resolver_row = latest_row_for(ctx.event_dir, resolved_by)
    if resolver_row is None:
        raise DossierError(
            f"{resolved_by!r} is not a registered artifact of {ctx.event_id}; "
            "register it first — an unregistered file cannot retire a declared unknown"
        )
    if not (ctx.event_dir / resolved_by).exists():
        raise DossierError(f"{resolved_by!r} is registered but missing on disk")

    declared.remove(unknown)
    record["declared_unknowns"] = declared
    record.setdefault("resolved_unknowns", []).append(
        {
            "unknown": unknown,
            "resolved_by": resolved_by,
            "resolved_by_sha256": resolver_row.get("sha256", ""),
            "resolved_utc": utc_stamp(),
            "resolved_by_stage": stage,
            **({"note": note} if note else {}),
        }
    )

    artifact = ctx.write_json(
        RECORD_PATH,
        record,
        kind="event_record",
        agent=stage,
        inputs=[resolved_by],
        notes=f"dossier reissued: retired declared unknown resolved by {resolved_by}",
    )
    audit.record(
        "stage",
        stage,
        payload={
            "status": "ok",
            "action": "retire_unknown",
            "retired_unknown": unknown,
            "resolved_by": resolved_by,
            "record_sha256": artifact.sha256,
        },
    )
    return artifact
