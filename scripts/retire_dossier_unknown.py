#!/usr/bin/env python
"""Retroactively retire a declared unknown that a committed artifact already resolves.

The builders now retire unknowns themselves when they land the resolving
artifact (see scripts/build_eaton_svi.py). This CLI exists for artifacts that
landed BEFORE that behaviour did, and cannot be rebuilt on this machine. It
does exactly what the builder would have done, through the same function, so
the resulting record, manifest row and audit row are indistinguishable from a
builder-issued retirement except for the stage name, which says what happened.

Example (the 2026-08-24 finding — Eaton's SVI join landed 2026-08-20 but the
dossier kept declaring it pending):

    python scripts/retire_dossier_unknown.py --event eaton-2025 \
        --unknown "social-vulnerability join (SVI x exposure) pending: no vulnerability claims yet" \
        --resolved-by exposure/svi_h3_r9_context.geojson
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import EventContext  # noqa: E402
from geosteward.deepcase.dossier import DossierError, retire_unknown  # noqa: E402
from geosteward.harness.audit import AuditLog  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True, help="event id, e.g. eaton-2025")
    ap.add_argument("--unknown", required=True, help="exact declared_unknowns text to retire")
    ap.add_argument("--resolved-by", required=True, help="event-relative path of the registered artifact that resolves it")
    ap.add_argument("--note", default="", help="optional free-text reason kept in the record")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    args = ap.parse_args()

    ctx = EventContext(event_id=args.event, event_dir=args.events_root / args.event, hazard="")
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    try:
        artifact = retire_unknown(
            ctx, audit, stage="dossier.retire_unknown",
            unknown=args.unknown, resolved_by=args.resolved_by, note=args.note,
        )
    except DossierError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if artifact is None:
        print("already retired; nothing written")
        return 0
    print(f"retired; new dossier sha256 {artifact.sha256[:12]} appended to the manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
