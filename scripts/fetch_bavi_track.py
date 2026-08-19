#!/usr/bin/env python
"""Capture a timestamped snapshot of a live typhoon track (default: Bavi 202609).

Thin wrapper over the DisasterPilot watcher's source connector. Snapshots are
append-only: each run writes a new UTC-stamped file plus an index row, never
overwriting earlier captures — the forecast-conditioned record stays frozen
for honest post-event validation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.hazards.typhoon import parse_track, track_summary
from geosteward.sources.zj_typhoon import typhoon_detail


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tfid", default="202609", help="Typhoon id (default Bavi 202609)")
    parser.add_argument("--output-dir", type=Path, default=Path("events/bavi-2026/snapshots"))
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Write a snapshot even after the source marks the storm inactive.",
    )
    args = parser.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = typhoon_detail(args.tfid)
    points = parse_track(payload)
    summary = {
        "captured_utc": stamp,
        "tfid": args.tfid,
        "name": payload.get("name"),
        "enname": payload.get("enname"),
        "isactive": payload.get("isactive"),
        **track_summary(points),
    }

    if payload.get("isactive") != "1" and not args.include_inactive:
        summary["capture_status"] = "not_written_inactive"
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / f"bavi_{args.tfid}_{stamp}.json"
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    index_path = args.output_dir / "capture_index.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
    # ensure_ascii for the console: Windows terminals may not be UTF-8
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
