"""Eaton deep case, SVI stage: join CDC SVI 2022 onto the DINS damage grid.

Appends to events/eaton-2025/ (append-only manifest + audit). Inputs are the
already-committed damage grid plus two captured sources:

- Census TIGERweb 2020 tracts intersecting the AOI (GeoJSON, captured)
- CDC/ATSDR SVI 2022 California tract CSV (captured; LA County subset frozen)

Every cell is assigned to exactly one tract by centroid point-in-polygon;
tract-level SVI attached to a tile is a downscaling approximation and is
declared per feature. Fail-closed: unassigned cells abort the stage.

Usage:
  python scripts/build_eaton_svi.py --tracts PATH --svi-csv PATH
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import h3

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.deepcase.dossier import retire_unknown
from geosteward.deepcase.svi import SVI_FIELDS, assign_points_to_tracts, load_svi_rows
from geosteward.harness.audit import AuditLog, sha256_file
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

EVENT_ID = "eaton-2025"
LA_COUNTY_FIPS = "06037"
TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/"
    "MapServer/10/query (Census 2020 tracts, AOI envelope, EPSG:4326)"
)
SVI_URL = "https://svi.cdc.gov/Documents/Data/2022/csv/states/California.csv"
#: Must match scripts/build_eaton_case.py stage_event_record verbatim.
SVI_PENDING_UNKNOWN = (
    "social-vulnerability join (SVI x exposure) pending: no vulnerability claims yet"
)


def fail_closed(audit: AuditLog, stage: str, results) -> None:
    for r in results:
        audit.record("check", stage, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{stage}] outcome check failed: {r.check}: {r.detail}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracts", type=Path, required=True, help="captured TIGERweb tract GeoJSON")
    ap.add_argument("--svi-csv", type=Path, required=True, help="captured CDC SVI state CSV")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    args = ap.parse_args()

    stage = "exposure.svi_context"
    ctx = EventContext(
        event_id=EVENT_ID, event_dir=args.events_root / EVENT_ID, hazard="wildfire"
    )
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")

    damage_grid_path = ctx.event_dir / "exposure" / "dins_h3_r9_damage_grid.geojson"
    grid = json.loads(damage_grid_path.read_text(encoding="utf-8"))
    tracts = json.loads(args.tracts.read_text(encoding="utf-8"))["features"]
    svi = load_svi_rows(args.svi_csv, LA_COUNTY_FIPS)

    # Freeze captured sources: tract geometry as-is; SVI as the county subset
    # actually consumed, with the full-file hash recorded for verification.
    snap_dir = ctx.event_dir / "snapshots" / "svi"
    snap_dir.mkdir(parents=True, exist_ok=True)
    tract_snap = snap_dir / "eaton_aoi_tracts_2020.geojson"
    tract_snap.write_text(
        json.dumps({"type": "FeatureCollection", "features": tracts}), encoding="utf-8"
    )
    ctx.register(
        Artifact(
            path=tract_snap, kind="source_snapshot", agent=stage,
            created_utc=utc_stamp(), inputs=[TIGERWEB_URL],
            notes=f"{len(tracts)} Census 2020 tracts intersecting the Eaton AOI envelope",
        )
    )
    svi_snap = snap_dir / "svi2022_la_county.json.gz"
    with gzip.open(svi_snap, "wt", encoding="utf-8") as f:
        json.dump(svi, f)
    ctx.register(
        Artifact(
            path=svi_snap, kind="source_snapshot", agent=stage,
            created_utc=utc_stamp(), inputs=[SVI_URL],
            notes=f"LA County subset ({len(svi)} tracts) of CDC SVI 2022 CA; "
            f"full-file sha256={sha256_file(args.svi_csv)}",
        )
    )

    cells = [f["properties"]["h3_cell"] for f in grid["features"]]
    centroids = []
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        centroids.append((cell, lat, lon))
    assignment = assign_points_to_tracts(centroids, tracts)

    assigned = {c: g for c, g in assignment.items() if g is not None}
    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            check_join_integrity(cells, list(assigned.keys())),  # every cell in a tract
            # Assigned GEOIDs must all come from the fetched tract set (no
            # orphans); the envelope legitimately covers more tracts than the
            # burn area touches, so full coverage is NOT required here.
            check_join_integrity(
                [t["properties"]["GEOID"] for t in tracts],
                list(set(assigned.values())),
                min_coverage=0.0,
            ),
        ],
    )

    # SVI percentile ranks must be in [0, 1]; -999 was already mapped to None.
    present = [
        v
        for geoid in set(assigned.values())
        for v in svi.get(geoid, {}).values()
        if v is not None
    ]
    if present:
        fail_closed(audit, stage, [
            check_bounds("svi_rank_min", min(present), 0.0, 1.0),
            check_bounds("svi_rank_max", max(present), 0.0, 1.0),
        ])

    features = []
    n_missing_svi = 0
    for feature in grid["features"]:
        cell = feature["properties"]["h3_cell"]
        geoid = assigned[cell]
        values = svi.get(geoid, {f: None for f in SVI_FIELDS})
        if values["RPL_THEMES"] is None:
            n_missing_svi += 1
        features.append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "h3_cell": cell,
                    "tract_geoid": geoid,
                    **values,
                    "n_structures": feature["properties"]["n_structures"],
                    "n_destroyed": feature["properties"]["n_destroyed"],
                    "destroyed_rate": feature["properties"]["destroyed_rate"],
                    "uncertainty": {
                        "svi_vintage": "2022 (pre-fire); tract-level rank attached to a "
                        "tile is a downscaling approximation",
                        "svi_missing": values["RPL_THEMES"] is None,
                        **feature["properties"]["uncertainty"],
                    },
                },
            }
        )

    collection = {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "h3_resolution": grid["properties"]["h3_resolution"],
            "n_cells": len(features),
            "n_cells_svi_missing": n_missing_svi,
            "resolution_cap": "tile",
            "source": "DINS damage grid x CDC SVI 2022 via Census 2020 tract assignment",
        },
    }
    fail_closed(audit, stage, [check_uncertainty_present(features[0]["properties"])])
    ctx.write_json(
        "exposure/svi_h3_r9_context.geojson",
        collection,
        kind="svi_context_grid",
        agent=stage,
        inputs=[damage_grid_path.name, tract_snap.name, svi_snap.name],
        notes=f"{len(features)} cells joined to {len(set(assigned.values()))} tracts; "
        f"{n_missing_svi} cells lack SVI (declared)",
    )
    audit.record(
        "stage", stage,
        payload={"status": "ok", "n_cells": len(features),
                 "n_tracts": len(set(assigned.values())), "n_svi_missing": n_missing_svi},
    )
    # The dossier was written before this join existed and declares it pending.
    # Landing the grid is what makes that line untrue, so this stage retires it —
    # a new dossier version with its own manifest row, never a hand edit.
    retire_unknown(
        ctx, audit, stage=stage,
        unknown=SVI_PENDING_UNKNOWN,
        resolved_by="exposure/svi_h3_r9_context.geojson",
    )
    print(f"svi context built: {len(features)} cells, {len(set(assigned.values()))} tracts")


if __name__ == "__main__":
    main()
