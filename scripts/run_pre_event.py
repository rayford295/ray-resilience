#!/usr/bin/env python
"""Run the DisasterPilot pre-event pipeline for a typhoon event.

Example (Bavi 2026):
    python scripts/run_pre_event.py --event-id bavi-2026 --tfid 202609
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from disasterpilot.pipeline import run_pre_event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--tfid", required=True)
    parser.add_argument("--events-root", type=Path, default=Path("events"))
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the live watcher capture; reuse existing snapshots.",
    )
    args = parser.parse_args()
    report = run_pre_event(
        args.event_id, args.tfid, events_root=args.events_root, skip_watcher=args.offline
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
