#!/usr/bin/env python
"""Close an event from its final committed source snapshot.

This creates a separate post-event closure artifact. It never changes the
pre-event dossier, footprints, or watch bulletin that were available before
landfall. The result records what the source reported and, just as important,
what still needs an official reconciliation or post-event evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from disasterpilot.hazards.typhoon import parse_track, track_summary


def _capture_time_from_name(path: Path) -> str:
    """Return the UTC capture time encoded by a snapshot filename when present."""
    token = path.stem.rsplit("_", 1)[-1]
    try:
        return dt.datetime.strptime(token, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=dt.timezone.utc
        ).isoformat()
    except ValueError:
        return dt.datetime.now(dt.timezone.utc).isoformat()


def _markdown(payload: dict) -> str:
    track = payload["track"]
    landfalls = payload["source_reported_landfalls"]
    lines = [
        f"# Event Closure: {payload['event_id']}",
        "",
        f"**Status:** {payload['event_status']}",
        "",
        f"**Closure basis:** {payload['closure_basis']}",
        "",
        "## Captured Track Record",
        "",
        f"- Final committed source snapshot: `{payload['source_snapshot']}`",
        f"- Source capture time: {payload['source_capture_utc']}",
        f"- Track points: {track['n_points']} ({track['first_time']} to {track['last_time']})",
        f"- Captured peak: {track['peak_pressure_hpa']} hPa at {track['peak_time']}",
        "",
        "## Source-Reported Landfalls",
        "",
    ]
    if landfalls:
        for landfall in landfalls:
            lines.append(
                f"- {landfall.get('landtime')}: {landfall.get('landaddress')} "
                f"({landfall.get('lat')}, {landfall.get('lng')})"
            )
    else:
        lines.append("- None reported in the final captured source payload.")
    lines += ["", "## What This Does Not Establish", ""]
    lines += [f"- {item}" for item in payload["declared_unknowns"]]
    lines += ["", "## Frozen Pre-Event Products", ""]
    lines += [f"- `{item}`" for item in payload["frozen_pre_event_artifacts"]]
    lines.append("")
    return "\n".join(lines)


def close_event(event_dir: Path) -> dict:
    snapshots = sorted((event_dir / "snapshots").glob("*.json"))
    if not snapshots:
        raise FileNotFoundError(f"No snapshots under {event_dir}/snapshots.")
    snapshot_path = snapshots[-1]
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if payload.get("isactive") == "1":
        raise ValueError("The source still marks this event active; refusing to close it.")

    closure_dir = event_dir / "closure"
    closure_json = closure_dir / "event_close.json"
    closure_md = closure_dir / "CLOSURE.md"
    if closure_json.exists() or closure_md.exists():
        raise FileExistsError("Closure artifacts already exist; preserve the first closure record.")

    manifest_path = event_dir / "artifact_manifest.jsonl"
    frozen = []
    if manifest_path.exists():
        for row in manifest_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(row)
            if record.get("agent") in {
                "dossier.typhoon",
                "exposure.typhoon",
                "decision.watch_bulletin",
            }:
                frozen.append(record["path"])

    record = {
        "event_id": event_dir.name,
        "event_status": "closed_by_source",
        "closure_basis": (
            "The final committed Zhejiang Water Resources API payload marks isactive=0; "
            "this is not an official best-track reconciliation."
        ),
        "source": "Zhejiang Water Resources typhoon API",
        "source_snapshot": snapshot_path.name,
        "source_capture_utc": _capture_time_from_name(snapshot_path),
        "source_isactive": payload.get("isactive"),
        "track": track_summary(parse_track(payload)),
        "source_reported_landfalls": payload.get("land", []),
        "frozen_pre_event_artifacts": frozen,
        "declared_unknowns": [
            "Official best-track reconciliation of intensity and landfall parameters.",
            "Population and building exposure counts; the required grids are not integrated.",
            "Post-event damage evidence; no imagery manifest has been ingested.",
            "A watchlist validation scorecard; observed damage labels are not available.",
        ],
    }
    closure_dir.mkdir(parents=True, exist_ok=True)
    closure_json.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    closure_md.write_text(_markdown(record), encoding="utf-8")

    created_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with manifest_path.open("a", encoding="utf-8") as handle:
        for path, kind in ((closure_json, "event_closure"), (closure_md, "event_closure_md")):
            handle.write(
                json.dumps(
                    {
                        "path": f"{event_dir.parent.name}/{path.relative_to(event_dir.parent).as_posix()}",
                        "kind": kind,
                        "agent": "closure.typhoon",
                        "created_utc": created_utc,
                        "inputs": [snapshot_path.name, "artifact_manifest.jsonl"],
                        "notes": "separate post-event closure; pre-event products remain frozen",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(close_event(args.event_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
