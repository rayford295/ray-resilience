#!/usr/bin/env python
"""Capture a timestamped snapshot of the live Bavi (202609) track.

Snapshots are append-only: each run writes a new UTC-stamped file plus a
normalized summary, never overwriting earlier captures. That preserves the
forecast-conditioned record needed for honest post-event validation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bavi.tracks import parse_track, track_summary

API_URL = "https://typhoon.slt.zj.gov.cn/Api/TyphoonInfo/{tfid}"


def fetch(tfid: str, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        API_URL.format(tfid=tfid),
        headers={
            "Referer": "https://typhoon.slt.zj.gov.cn/",
            "User-Agent": "Mozilla/5.0 (research snapshot; bavi-resilience)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tfid", default="202609", help="Typhoon id (default Bavi 202609)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/snapshots"))
    args = parser.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = fetch(args.tfid)
    points = parse_track(payload)
    summary = {
        "captured_utc": stamp,
        "tfid": args.tfid,
        "name": payload.get("name"),
        "enname": payload.get("enname"),
        "isactive": payload.get("isactive"),
        **track_summary(points),
    }

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
