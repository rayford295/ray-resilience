"""Build the Eaton Fire 2025 deep case (Tier 2 exposure + Tier 3 evidence).

Offline Loop-2 pipeline: reads the owner's local dataset registry
(disaster-dataset-Yifan-all/_registry) and the raw DINS / cross-view matched
datasets, and writes harness-checked artifacts under events/eaton-2025/.

Fail-closed: any failed outcome check aborts the stage, and the failure is
itself an audit record. Registry profiles are copied in as source snapshots
so every grid cell traces back to a hashed dataset state.

Usage:
  python scripts/build_eaton_case.py [--data-root PATH] [--resolution 9]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import h3

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.deepcase import dins
from geosteward.harness.audit import AuditLog
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

EVENT_ID = "eaton-2025"
# Generous Eaton Fire AOI (Altadena/Pasadena area); a point outside this box
# is a data error, not a surprise to tolerate.
AOI = {"min_lat": 34.10, "max_lat": 34.30, "min_lon": -118.20, "max_lon": -117.95}

REGISTRY_SNAPSHOTS = (
    "profiles/Eaton_Fire_profile.json",
    "profiles/EATON_wildfire_mapillary_matched_profile.json",
    "profiles/Altadena_Images_profile.json",
    "label_crosswalk.json",
)


def fail_closed(audit: AuditLog, stage: str, results) -> None:
    """Record every check; abort the stage on the first failure."""
    for r in results:
        audit.record("check", stage, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{stage}] outcome check failed: {r.check}: {r.detail}")


def stage_registry_snapshot(ctx: EventContext, audit: AuditLog, registry: Path) -> list[str]:
    """Copy registry profiles + crosswalk in as the case's source snapshots."""
    stage = "snapshot.registry"
    copied: list[str] = []
    for rel in REGISTRY_SNAPSHOTS:
        src = registry / rel
        if not src.exists():
            raise FileNotFoundError(f"registry file missing: {src}")
        dest = ctx.event_dir / "snapshots" / "registry" / Path(rel).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        ctx.register(
            Artifact(
                path=dest,
                kind="dataset_registry_snapshot",
                agent=stage,
                created_utc=utc_stamp(),
                inputs=[src.as_posix()],
                notes="frozen copy of the local dataset registry state",
            )
        )
        copied.append(dest.name)
    audit.record("stage", stage, payload={"status": "ok", "copied": copied})
    return copied


def stage_dins_grid(
    ctx: EventContext, audit: AuditLog, data_root: Path, resolution: int, snapshot_names: list[str]
) -> None:
    """Tier-2 exposure: DINS points -> H3 damage grid, harness-checked."""
    stage = "exposure.dins_grid"
    csvs = sorted((data_root / "Eaton_Fire").glob("Eaton_Fire_*_points.csv"))
    csvs = [p for p in csvs if "attachments" not in p.name and "summary" not in p.name]
    points = dins.load_dins_points(csvs)
    if not points:
        raise RuntimeError(f"[{stage}] no DINS points loaded from {data_root}")

    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    cells = dins.aggregate_h3(points, resolution)
    ids_in_cells = [pid for entry in cells.values() for pid in entry["point_ids"]]

    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            check_bounds("min_lat", min(lats), AOI["min_lat"], AOI["max_lat"]),
            check_bounds("max_lat", max(lats), AOI["min_lat"], AOI["max_lat"]),
            check_bounds("min_lon", min(lons), AOI["min_lon"], AOI["max_lon"]),
            check_bounds("max_lon", max(lons), AOI["min_lon"], AOI["max_lon"]),
            check_join_integrity([p.objectid for p in points], ids_in_cells),
        ],
    )

    collection = dins.grid_feature_collection(
        cells,
        resolution,
        source_notes="CAL FIRE DINS survey points, Eaton Fire 2025; "
        "labels normalized via registry label_crosswalk.json",
    )
    fail_closed(audit, stage, [
        check_uncertainty_present(collection["features"][0]["properties"]),
    ])
    ctx.write_json(
        f"exposure/dins_h3_r{resolution}_damage_grid.geojson",
        collection,
        kind="damage_grid",
        agent=stage,
        inputs=[p.name for p in csvs] + snapshot_names,
        notes=f"{len(points)} structures in {len(cells)} H3 r{resolution} cells; "
        f"totals {dins.severity_totals(points)}",
    )

    # Parcel-level source layer: registered for lineage, resolution-capped —
    # policy forbids serving it to resident-facing surfaces.
    restricted = ctx.event_dir / "exposure" / "dins_points_restricted.csv.gz"
    restricted.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(restricted, "wt", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["objectid", "lat", "lon", "severity", "structure_type"])
        for p in points:
            writer.writerow([p.objectid, p.lat, p.lon, p.severity, p.structure_type])
    ctx.register(
        Artifact(
            path=restricted,
            kind="damage_points_restricted",
            agent=stage,
            created_utc=utc_stamp(),
            inputs=[p.name for p in csvs],
            notes="parcel-level DINS source; resolution_cap=parcel, planner lineage only",
        )
    )
    audit.record("stage", stage, payload={"status": "ok", "n_points": len(points), "n_cells": len(cells)})


def stage_crossview_evidence(
    ctx: EventContext, audit: AuditLog, data_root: Path, resolution: int, snapshot_names: list[str]
) -> None:
    """Tier-3 evidence: cross-view matched samples -> coverage/reliability grid."""
    stage = "evidence.crossview_coverage"
    manifest = data_root / "EATON_wildfire_mapillary_matched" / "manifest.csv"
    rows = []
    with manifest.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            try:
                row["_lat"], row["_lon"] = float(row["post_latitude"]), float(row["post_longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append(row)
    if not rows:
        raise RuntimeError(f"[{stage}] no matched samples loaded from {manifest}")

    gated = [r for r in rows if r.get("match_quality") in ("good", "usable")]
    cells: dict[str, dict] = {}
    for r in gated:
        cell = h3.latlng_to_cell(r["_lat"], r["_lon"], resolution)
        entry = cells.setdefault(cell, {"labels": Counter(), "quality": Counter(), "ids": []})
        entry["labels"][r.get("label_name", "unknown")] += 1
        entry["quality"][r.get("match_quality")] += 1
        entry["ids"].append(r.get("sample_id", ""))

    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            check_bounds("min_lat", min(r["_lat"] for r in gated), AOI["min_lat"], AOI["max_lat"]),
            check_bounds("max_lat", max(r["_lat"] for r in gated), AOI["min_lat"], AOI["max_lat"]),
            check_join_integrity(
                [r.get("sample_id", "") for r in gated],
                [i for e in cells.values() for i in e["ids"]],
            ),
        ],
    )

    features = []
    for cell, entry in sorted(cells.items()):
        boundary = h3.cell_to_boundary(cell)
        ring = [[lng, lat] for lat, lng in boundary]
        ring.append(ring[0])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "h3_cell": cell,
                    "n_matched_samples": sum(entry["labels"].values()),
                    "labels": dict(entry["labels"]),
                    "match_quality": dict(entry["quality"]),
                    "uncertainty": {
                        "reliability_gate": "match_quality in {good, usable} only",
                        "note": "class damaged_repairable has n=30 overall — "
                        "insufficient statistical power; declared, not hidden",
                    },
                },
            }
        )
    collection = {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "h3_resolution": resolution,
            "n_samples_total": len(rows),
            "n_samples_gated": len(gated),
            "resolution_cap": "tile",
            "source": "EATON_wildfire_mapillary_matched manifest (CrossViewGate line)",
        },
    }
    fail_closed(audit, stage, [check_uncertainty_present(features[0]["properties"])])
    ctx.write_json(
        f"evidence/crossview_h3_r{resolution}_coverage.geojson",
        collection,
        kind="evidence_coverage_grid",
        agent=stage,
        inputs=[manifest.as_posix()] + snapshot_names,
        notes=f"{len(gated)}/{len(rows)} samples pass the reliability gate, "
        f"{len(cells)} cells",
    )
    audit.record("stage", stage, payload={"status": "ok", "n_gated": len(gated), "n_cells": len(cells)})


def stage_event_record(ctx: EventContext, audit: AuditLog) -> None:
    """Dossier: machine-readable event record with declared unknowns."""
    stage = "dossier.event_record"
    record = {
        "event_id": EVENT_ID,
        "name": "Eaton Fire",
        "hazard": "wildfire",
        "start_date": "2025-01-07",
        "location": "Altadena / Pasadena, Los Angeles County, CA",
        "aoi_bbox_wgs84": AOI,
        "evidence_tier": 3,
        "data_sources": [
            "CAL FIRE DINS structure damage points (verified_official)",
            "EATON_wildfire_mapillary_matched cross-view set (matched_derived)",
            "NOAA post-event orthoimagery 2025-01-28 (verified_official; imagery not committed)",
        ],
        "declared_unknowns": [
            "40 DINS points are Inaccessible: no damage conclusion supported there",
            "damaged_repairable evidence class has n=30 — no tile-level rate claims from it",
            "social-vulnerability join (SVI x exposure) pending: no vulnerability claims yet",
        ],
        "uncertainty": {
            "label_crosswalk": "percent-loss to perception mapping is approximate; "
            "see snapshots/registry/label_crosswalk.json"
        },
    }
    ctx.write_json(
        "dossier/event_record.json",
        record,
        kind="event_record",
        agent=stage,
        inputs=["snapshots/registry"],
        notes="Eaton Fire 2025 deep-case dossier",
    )
    audit.record("stage", stage, payload={"status": "ok"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-root",
        type=Path,
        default=Path("C:/Users/yyang295/Desktop/disaster-dataset-Yifan-all"),
    )
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--resolution", type=int, default=9)
    args = ap.parse_args()

    ctx = EventContext(
        event_id=EVENT_ID,
        event_dir=args.events_root / EVENT_ID,
        hazard="wildfire",
    )
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    registry = args.data_root / "_registry"

    snapshots = stage_registry_snapshot(ctx, audit, registry)
    stage_dins_grid(ctx, audit, args.data_root, args.resolution, snapshots)
    stage_crossview_evidence(ctx, audit, args.data_root, args.resolution, snapshots)
    stage_event_record(ctx, audit)
    print(f"eaton-2025 deep case built: {len(ctx.artifacts)} artifacts under {ctx.event_dir}")


if __name__ == "__main__":
    main()
