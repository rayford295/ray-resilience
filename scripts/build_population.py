"""Tile-level population exposure for every published deep case.

2020 Census block counts (TIGERweb, public domain) allocated to each
event's evaluated H3 r9 tiles by block-centroid containment. The raw
attribute payloads are frozen (gzip, hashed) before anything is built;
population falling inside the query envelope but outside every evaluated
tile is declared as a total, never dropped silently or invented into
tiles the event has no evidence for. Appends to each event's manifest and
audit log.

Usage:
  python scripts/build_population.py                 # all three events
  python scripts/build_population.py --event ian-2022
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import h3

from geosteward.agents.base import EventContext, Artifact, utc_stamp
from geosteward.deepcase.aoi import EVENT_GRIDS
from geosteward.deepcase.facilities import bbox_of_features
from geosteward.deepcase.population import (
    TIGERWEB_BLOCKS_URL,
    allocate_to_cells,
    blocks_to_rows,
    fetch_blocks,
)
from geosteward.harness.audit import AuditLog
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

STAGE = "exposure.population"


def fail_closed(audit: AuditLog, results) -> None:
    for r in results:
        audit.record("check", STAGE, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{STAGE}] outcome check failed: {r.check}: {r.detail}")


def build_event(event_id: str, events_root: Path) -> None:
    spec = EVENT_GRIDS[event_id]
    ctx = EventContext(event_id=event_id, event_dir=events_root / event_id, hazard=spec["hazard"])
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")

    evaluated: dict[str, dict] = {}  # cell -> geometry, union over the event's grids
    bboxes = []
    grid_names = []
    for rel in spec["grids"]:
        grid_path = ctx.event_dir / rel
        if not grid_path.exists():
            raise RuntimeError(f"{event_id}: AOI grid missing: {grid_path}")
        grid = json.loads(grid_path.read_text(encoding="utf-8"))
        for f in grid["features"]:
            evaluated.setdefault(f["properties"]["h3_cell"], f["geometry"])
        bboxes.append(bbox_of_features(grid["features"]))
        grid_names.append(Path(rel).name)

    stamp = utc_stamp()
    snap_dir = ctx.event_dir / "snapshots" / "population"
    snap_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    n_features_raw = 0
    for i, bbox in enumerate(bboxes):
        payload = fetch_blocks(bbox)
        n_features_raw += len(payload.get("features", []))
        snap = snap_dir / f"tigerweb_blocks_{stamp}_bbox{i}.json.gz"
        with gzip.open(snap, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh)
        ctx.register(
            Artifact(
                path=snap, kind="source_snapshot", agent=STAGE, created_utc=stamp,
                inputs=[f"{TIGERWEB_BLOCKS_URL} (2020 blocks, envelope {i}, attributes only)"],
                notes=f"{len(payload.get('features', []))} blocks; POP100 + centroid attributes",
            )
        )
        rows.extend(blocks_to_rows(payload))

    per_cell, assigned, unassigned = allocate_to_cells(rows, set(evaluated))
    n_unparseable = n_features_raw - len(rows)

    fail_closed(audit, [
        check_crs("EPSG:4326"),
        # Every populated cell must be an evaluated cell — allocation cannot
        # invent coverage (population outside is a declared total instead).
        check_join_integrity(list(evaluated), list(per_cell), min_coverage=0.0),
        check_bounds("population_min", min(per_cell.values(), default=0), 0, 10**7),
    ])

    features = []
    for cell, geometry in evaluated.items():
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "h3_cell": cell,
                "pop_2020": per_cell.get(cell, 0),
                "uncertainty": {
                    "allocation": "block centroid -> tile; a block straddling tile "
                    "edges is wholly assigned to its centroid's tile",
                    "vintage": "2020 decennial count — pre-event population, not "
                    "presence at event time",
                },
            },
        })
    fail_closed(audit, [check_uncertainty_present(features[0]["properties"])])

    collection = {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "source": "US Census 2020 PL blocks via TIGERweb (POP100, block centroids)",
            "h3_resolution": 9,
            "n_cells": len(features),
            "pop_assigned": assigned,
            "pop_in_envelope_unassigned": unassigned,
            "n_blocks_without_centroid": n_unparseable,
            "resolution_cap": "tile",
            "aoi_from": grid_names,
        },
    }
    ctx.write_json(
        "exposure/population_h3_r9.geojson",
        collection,
        kind="population_grid",
        agent=STAGE,
        inputs=grid_names,
        notes=f"{assigned:,} residents (2020) allocated to {len(per_cell)} of "
        f"{len(features)} evaluated cells; {unassigned:,} in envelope but outside "
        "evaluated tiles (declared, not mapped)",
    )
    audit.record(
        "stage", STAGE,
        payload={"status": "ok", "pop_assigned": assigned, "pop_unassigned": unassigned,
                 "n_cells": len(features), "n_blocks": len(rows)},
    )
    print(f"{event_id}: {assigned:,} residents in {len(per_cell)} cells "
          f"({unassigned:,} in envelope, outside evaluation)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", choices=sorted(EVENT_GRIDS), help="one event (default: all)")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    args = ap.parse_args()
    for event_id in [args.event] if args.event else sorted(EVENT_GRIDS):
        build_event(event_id, args.events_root)


if __name__ == "__main__":
    main()
