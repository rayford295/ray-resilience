"""Critical-facility context for every published deep case, from OpenStreetMap.

For each event, the AOI is the envelope of grids the event has already
committed — the extract can never cover ground the event's own evidence does
not. The raw Overpass response is frozen (gzip, hashed) before anything is
built from it; the product declares OSM attribution, the presence-not-status
boundary, and per-feature uncertainty. Appends to each event's manifest and
audit log; a rerun writes a new timestamped snapshot, never overwrites one.

Usage:
  python scripts/build_facilities.py                 # all three events
  python scripts/build_facilities.py --event ian-2022
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.deepcase.facilities import (
    AMENITIES,
    DECLARED_UNKNOWNS,
    OSM_ATTRIBUTION,
    OVERPASS_URL,
    bbox_of_features,
    elements_to_features,
    fetch_overpass,
    overpass_query,
)
from geosteward.harness.audit import AuditLog
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_uncertainty_present,
)

STAGE = "exposure.facility_context"

# The grids whose envelopes define each event's AOI(s). Multiple grids give
# multiple bboxes (Milton's two AOIs sit 200 km apart; their union envelope
# would cover open gulf and is deliberately not used).
EVENT_GRIDS: dict[str, dict[str, list[str]]] = {
    "eaton-2025": {
        "hazard": "wildfire",
        "grids": ["exposure/dins_h3_r9_damage_grid.geojson"],
    },
    "milton-2024": {
        "hazard": "hurricane",
        "grids": [
            "evidence/bitemporal_h3_r9_grid.geojson",
            "exposure/debris_h3_r9_grid.geojson",
        ],
    },
    "ian-2022": {
        "hazard": "hurricane",
        "grids": ["evidence/crossview_h3_r9_grid.geojson"],
    },
}


def fail_closed(audit: AuditLog, results) -> None:
    for r in results:
        audit.record("check", STAGE, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{STAGE}] outcome check failed: {r.check}: {r.detail}")


def build_event(event_id: str, events_root: Path) -> None:
    spec = EVENT_GRIDS[event_id]
    ctx = EventContext(event_id=event_id, event_dir=events_root / event_id, hazard=spec["hazard"])
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")

    bboxes = []
    grid_names = []
    for rel in spec["grids"]:
        grid_path = ctx.event_dir / rel
        if not grid_path.exists():
            raise RuntimeError(f"{event_id}: AOI grid missing: {grid_path} — refusing to invent an AOI")
        grid = json.loads(grid_path.read_text(encoding="utf-8"))
        bboxes.append(bbox_of_features(grid["features"]))
        grid_names.append(Path(rel).name)

    query = overpass_query(bboxes)
    payload = fetch_overpass(query)
    elements = payload.get("elements", [])

    stamp = utc_stamp()
    snap_dir = ctx.event_dir / "snapshots" / "facilities"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap = snap_dir / f"overpass_{stamp}.json.gz"
    with gzip.open(snap, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    ctx.register(
        Artifact(
            path=snap, kind="source_snapshot_odbl", agent=STAGE, created_utc=stamp,
            inputs=[f"{OVERPASS_URL} (amenity in {'/'.join(AMENITIES)}, {len(bboxes)} AOI bbox(es))"],
            notes=f"raw Overpass response, {len(elements)} elements; {OSM_ATTRIBUTION}",
        )
    )

    features = elements_to_features(elements)
    # Every point must fall inside one of the padded AOI envelopes it was
    # queried with — a coordinate outside them means the query and the
    # product no longer describe the same ground.
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        inside = any(s <= lat <= n and w <= lon <= e for s, w, n, e in bboxes)
        if not inside:
            fail_closed(audit, [check_bounds("facility_in_aoi", 0.0, 1.0, 1.0)])
    checks = [check_crs("EPSG:4326")]
    if features:
        checks.append(check_uncertainty_present(features[0]["properties"]))
    fail_closed(audit, checks)

    counts: dict[str, int] = {}
    for f in features:
        counts[f["properties"]["category"]] = counts.get(f["properties"]["category"], 0) + 1

    collection = {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "source": "OpenStreetMap via Overpass API",
            "attribution": OSM_ATTRIBUTION,
            "license": "ODbL-1.0",
            "amenities_in_scope": list(AMENITIES),
            "n_facilities": len(features),
            "counts_by_category": counts,
            "resolution_cap": "tile",
            "declared_unknowns": DECLARED_UNKNOWNS,
            "aoi_from": grid_names,
        },
    }
    ctx.write_json(
        "exposure/critical_facilities.geojson",
        collection,
        kind="facility_context_points",
        agent=STAGE,
        inputs=[snap.name, *grid_names],
        notes=f"{len(features)} OSM facilities ({counts}) inside {len(bboxes)} AOI envelope(s); "
        "presence, not operational status",
    )
    audit.record(
        "stage", STAGE,
        payload={"status": "ok", "n_facilities": len(features), "counts": counts,
                 "n_aoi_bboxes": len(bboxes)},
    )
    print(f"{event_id}: {len(features)} facilities {counts}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", choices=sorted(EVENT_GRIDS), help="one event (default: all)")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    args = ap.parse_args()
    for event_id in [args.event] if args.event else sorted(EVENT_GRIDS):
        build_event(event_id, args.events_root)


if __name__ == "__main__":
    main()
