"""Shared foundations for Tier-1 watch connectors.

Every connector normalizes its payload into WatchEvent rows and archives the
raw payload as an append-only snapshot, so any product can be traced back to
the exact bytes a source served at a specific time.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEADERS = {"User-Agent": "RayResilience-watch/0.1 (https://github.com/rayford295/ray-resilience)"}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fetch_json(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class WatchEvent:
    """One normalized hazard observation from a public source."""

    source: str
    source_id: str
    hazard: str
    name: str
    lat: float
    lon: float
    severity: str
    observed_utc: str
    properties: dict[str, Any] = field(default_factory=dict)

    def as_feature(self) -> dict[str, Any]:
        props: dict[str, Any] = dict(self.properties)
        props.update(
            {
                "source": self.source,
                "source_id": self.source_id,
                "hazard": self.hazard,
                "name": self.name,
                "severity": self.severity,
                "observed_utc": self.observed_utc,
            }
        )
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
            "properties": props,
        }


def save_snapshot(root: Path, source: str, payload: Any) -> Path:
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    path = snapshots / f"{source}_{stamp}.json.gz"
    suffix = 1
    while path.exists():  # same-second rerun: never overwrite, never touch the stamp
        suffix += 1
        path = snapshots / f"{source}_{stamp}_{suffix}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    with (snapshots / "capture_index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"source": source, "path": path.name, "utc": stamp}) + "\n")
    return path


def merge_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a sequence of paginated FeatureCollection payloads into one.

    Keeps every top-level key from the first page (``type``, ``context``,
    etc.) but replaces ``features`` with the concatenation of every page's
    features, and drops any ``pagination`` key since the merged result is
    already the complete, fully-followed set.
    """

    if not pages:
        return {"type": "FeatureCollection", "features": []}
    merged = dict(pages[0])
    features: list[Any] = []
    for page in pages:
        features.extend(page.get("features", []))
    merged["features"] = features
    merged.pop("pagination", None)
    return merged
