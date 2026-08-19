"""Tier-1 watch product builder.

Merges normalized events from every source into one national FeatureCollection,
running Steward Harness outcome checks and declaring what is NOT known with the
same prominence as what is. A failed source appears as a recorded failure —
never as silently-missing data.
"""

from __future__ import annotations

from typing import Any

from geosteward.harness.checks import check_bounds, check_crs
from geosteward.sources.watchbase import WatchEvent

CRS = "EPSG:4326"


def build_watch_product(
    parsed: dict[str, tuple[list[WatchEvent], int]],
    failures: dict[str, str],
    generated_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    features: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    checks = [check_crs(CRS).as_row()]

    for source, (events, skipped) in parsed.items():
        dropped = 0
        for event in events:
            lat_ok = check_bounds("lat", event.lat, -90.0, 90.0)
            lon_ok = check_bounds("lon", event.lon, -180.0, 180.0)
            if lat_ok.passed and lon_ok.passed:
                features.append(event.as_feature())
            else:
                dropped += 1
                checks.append((lat_ok if not lat_ok.passed else lon_ok).as_row())
        sources[source] = {
            "status": "ok",
            "events": len(events) - dropped,
            "skipped": skipped,
            "dropped_bounds": dropped,
            "error": None,
        }
    for source, error in failures.items():
        sources[source] = {
            "status": "failed",
            "events": 0,
            "skipped": 0,
            "dropped_bounds": 0,
            "error": error,
        }

    unknowns = ["Watch data supports monitoring only; no damage or exposure conclusions."]
    failed = sorted(failures)
    if failed:
        unknowns.append(f"Sources currently failed (no data, not zero hazards): {', '.join(failed)}.")
    total_skipped = sum(row["skipped"] for row in sources.values())
    total_dropped = sum(row["dropped_bounds"] for row in sources.values())
    if total_skipped or total_dropped:
        unknowns.append(
            f"{total_skipped} feature(s) skipped as malformed; {total_dropped} dropped by bounds checks."
        )

    collection = {
        "type": "FeatureCollection",
        "geosteward:crs": CRS,
        "geosteward:generated_utc": generated_utc,
        "features": features,
    }
    status = {
        "generated_utc": generated_utc,
        "sources": sources,
        "declared_unknowns": unknowns,
        "checks": checks,
    }
    return collection, status
