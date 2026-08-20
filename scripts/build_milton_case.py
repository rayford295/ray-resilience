"""Build the Hurricane Milton 2024 deep case (Tier 2/3), fail-closed.

Two AOIs, two verified sources, one harness:

- Horseshoe Beach, FL (Big Bend): the published Bi-Temporal street-view set
  (Figshare 10.6084/m9.figshare.28801208.v2) -> evidence grid. The post
  imagery is from 2024, AFTER a season with Debby, Helene AND Milton —
  single-event attribution is NOT supported and is declared, not implied.
- Pinellas County, FL: county debris-program volumes aggregated to H3 r9
  (Rayford-AI/debris-estimate) -> exposure grid with Milton wind/rain
  covariates.

GenDisasterSVI is explicitly excluded (generated imagery, candor rule); its
registry profile is frozen into snapshots/ so the exclusion is auditable.

Usage:
  python scripts/build_milton_case.py [--data-root PATH] [--debris-csv PATH]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.deepcase.grids import aggregate_labeled_points, cells_to_collection, h3_ring
from geosteward.harness.audit import AuditLog, sha256_file
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

EVENT_ID = "milton-2024"

HORSESHOE_AOI = {"min_lat": 29.35, "max_lat": 29.55, "min_lon": -83.40, "max_lon": -83.20}
PINELLAS_AOI = {"min_lat": 27.55, "max_lat": 28.25, "min_lon": -82.95, "max_lon": -82.50}

#: Bi-Temporal human_damage_perception values (case-inconsistent at source).
BITEMPORAL_CROSSWALK = {"mild": "minor", "moderate": "moderate", "severe": "severe"}

DEBRIS_SOURCE_URL = (
    "https://raw.githubusercontent.com/Rayford-AI/debris-estimate/main/"
    "data/alphaearth/full/h9_debrisv6_matched_baseline_n5618.csv"
)
DEBRIS_COLUMNS = ("VolCD", "VolVG", "VolCD_sum", "VolVG_sum", "VolBoth_sum",
                  "windgust_M", "rainfall_M", "dist_htrack_M")

REGISTRY_SNAPSHOTS = (
    "profiles/Bi-temporal_hurricane_profile.json",
    "profiles/hurrican-milton-GenDisasterSVI_profile.json",
    "label_crosswalk.json",
)


def fail_closed(audit: AuditLog, stage: str, results) -> None:
    for r in results:
        audit.record("check", stage, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{stage}] outcome check failed: {r.check}: {r.detail}")


def stage_registry_snapshot(ctx: EventContext, audit: AuditLog, registry: Path) -> list[str]:
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


def stage_bitemporal_evidence(
    ctx: EventContext, audit: AuditLog, data_root: Path, resolution: int, snapshots: list[str]
) -> None:
    stage = "evidence.bitemporal_grid"
    location_csv = data_root / "Bi-temporal_hurricane" / "Location.csv"
    rows = []
    with location_csv.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for i, row in enumerate(csv.DictReader(f)):
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            native = (row.get("human_damage_perception") or "").strip()
            label = BITEMPORAL_CROSSWALK.get(native.lower(), "unknown")
            rows.append((lat, lon, label, str(i)))
    if not rows:
        raise RuntimeError(f"[{stage}] no samples loaded from {location_csv}")

    cells = aggregate_labeled_points(rows, resolution)
    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            check_bounds("min_lat", min(r[0] for r in rows),
                         HORSESHOE_AOI["min_lat"], HORSESHOE_AOI["max_lat"]),
            check_bounds("max_lat", max(r[0] for r in rows),
                         HORSESHOE_AOI["min_lat"], HORSESHOE_AOI["max_lat"]),
            check_bounds("min_lon", min(r[1] for r in rows),
                         HORSESHOE_AOI["min_lon"], HORSESHOE_AOI["max_lon"]),
            check_bounds("max_lon", max(r[1] for r in rows),
                         HORSESHOE_AOI["min_lon"], HORSESHOE_AOI["max_lon"]),
            check_join_integrity(
                [r[3] for r in rows],
                [i for e in cells.values() for i in e["ids"]],
            ),
        ],
    )
    collection = cells_to_collection(
        cells,
        resolution,
        properties={
            "n_samples": len(rows),
            "canonical_label_field": "human_damage_perception",
            "source": "Bi-Temporal street-view set (Figshare 10.6084/m9.figshare.28801208.v2)",
            "attribution_caveat": "post imagery is 2024 season cumulative "
            "(Debby + Helene + Milton); single-event attribution not supported",
        },
        cell_uncertainty={
            "event_attribution": "2024-season cumulative, not Milton-specific",
            "label_source": "human perception scoring of image pairs",
        },
    )
    fail_closed(audit, stage, [
        check_uncertainty_present(collection["features"][0]["properties"]),
    ])
    ctx.write_json(
        f"evidence/bitemporal_h3_r{resolution}_grid.geojson",
        collection,
        kind="evidence_grid",
        agent=stage,
        inputs=[location_csv.as_posix()] + snapshots,
        notes=f"{len(rows)} labeled pairs in {len(cells)} cells, Horseshoe Beach AOI",
    )
    audit.record("stage", stage, payload={"status": "ok", "n_samples": len(rows), "n_cells": len(cells)})


def stage_debris_exposure(
    ctx: EventContext, audit: AuditLog, debris_csv: Path, snapshots: list[str]
) -> None:
    stage = "exposure.debris_grid"
    rows = []
    with debris_csv.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if not rows:
        raise RuntimeError(f"[{stage}] no debris cells loaded from {debris_csv}")

    # Freeze the upstream CSV as a snapshot: append-only provenance.
    snap = ctx.event_dir / "snapshots" / "debris" / (debris_csv.name + ".gz")
    snap.parent.mkdir(parents=True, exist_ok=True)
    with debris_csv.open("rb") as src, gzip.open(snap, "wb") as dst:
        shutil.copyfileobj(src, dst)
    ctx.register(
        Artifact(
            path=snap,
            kind="source_snapshot",
            agent=stage,
            created_utc=utc_stamp(),
            inputs=[DEBRIS_SOURCE_URL],
            notes=f"upstream sha256={sha256_file(debris_csv)}",
        )
    )

    import h3 as _h3

    features = []
    lats = []
    for row in rows:
        cell = row["GRID_ID"]
        lat, _lng = _h3.cell_to_latlng(cell)
        lats.append(lat)
        props = {"h3_cell": cell}
        for col in DEBRIS_COLUMNS:
            raw = (row.get(col) or "").strip()
            try:
                props[col] = round(float(raw), 4)
            except ValueError:
                props[col] = None
        props["uncertainty"] = {
            "source": "county debris-program volumes aggregated to H3; "
            "wind/rain covariates are event-model estimates",
            "missing_fields": [c for c in DEBRIS_COLUMNS if props[c] is None],
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [h3_ring(cell)]},
                "properties": props,
            }
        )

    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            check_bounds("min_lat", min(lats), PINELLAS_AOI["min_lat"], PINELLAS_AOI["max_lat"]),
            check_bounds("max_lat", max(lats), PINELLAS_AOI["min_lat"], PINELLAS_AOI["max_lat"]),
            check_join_integrity(
                [r["GRID_ID"] for r in rows],
                [f["properties"]["h3_cell"] for f in features],
            ),
            check_uncertainty_present(features[0]["properties"]),
        ],
    )
    collection = {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "h3_resolution": 9,
            "n_cells": len(features),
            "resolution_cap": "tile",
            "source": DEBRIS_SOURCE_URL,
            "note": "debris volumes reflect the 2024 season response in Pinellas County; "
            "windgust_M/rainfall_M/dist_htrack_M are Milton-specific covariates",
        },
    }
    ctx.write_json(
        "exposure/debris_h3_r9_grid.geojson",
        collection,
        kind="debris_exposure_grid",
        agent=stage,
        inputs=[snap.name] + snapshots,
        notes=f"{len(features)} Pinellas H3 r9 cells with debris volumes + Milton covariates",
    )
    audit.record("stage", stage, payload={"status": "ok", "n_cells": len(features)})


def stage_event_record(ctx: EventContext, audit: AuditLog) -> None:
    stage = "dossier.event_record"
    record = {
        "event_id": EVENT_ID,
        "name": "Hurricane Milton",
        "hazard": "hurricane",
        "landfall": "2024-10-09, Siesta Key, FL (Cat 3)",
        "aoi": {
            "horseshoe_beach": HORSESHOE_AOI,
            "pinellas_county": PINELLAS_AOI,
        },
        "evidence_tier": 3,
        "data_sources": [
            "Bi-Temporal street-view damage set (published_verified; Figshare DOI)",
            "Pinellas County H3 debris grids (Rayford-AI/debris-estimate)",
        ],
        "excluded_sources": [
            {
                "dataset": "hurrican-milton-GenDisasterSVI",
                "reason": "post-event street images are InstructPix2Pix-generated "
                "(source paths reference experiment2_ip2p); candor rule forbids "
                "generated imagery as evidence",
                "registry_tier": "generated_excluded",
                "open_question": "2,555 post_sat satellite images may be real; "
                "owner to confirm provenance before any use",
            }
        ],
        "declared_unknowns": [
            "Horseshoe Beach post imagery is 2024-season cumulative "
            "(Debby + Helene + Milton) — damage there is NOT attributable to Milton alone",
            "no parcel-level claims anywhere: all products are tile (H3 r9) resolution",
            "social-vulnerability join (SVI x exposure) pending: no vulnerability claims yet",
        ],
        "uncertainty": {
            "label_crosswalk": "perception labels mild/moderate/severe mapped to canonical "
            "minor/moderate/severe; see snapshots/registry/label_crosswalk.json"
        },
    }
    ctx.write_json(
        "dossier/event_record.json",
        record,
        kind="event_record",
        agent=stage,
        inputs=["snapshots/registry"],
        notes="Hurricane Milton 2024 deep-case dossier (two AOIs, honest attribution)",
    )
    audit.record("stage", stage, payload={"status": "ok"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-root",
        type=Path,
        default=Path("C:/Users/yyang295/Desktop/disaster-dataset-Yifan-all"),
    )
    ap.add_argument("--debris-csv", type=Path, required=True,
                    help="local copy of h9_debrisv6_matched_baseline_n5618.csv")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--resolution", type=int, default=9)
    args = ap.parse_args()

    ctx = EventContext(
        event_id=EVENT_ID,
        event_dir=args.events_root / EVENT_ID,
        hazard="hurricane",
    )
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    registry = args.data_root / "_registry"

    snapshots = stage_registry_snapshot(ctx, audit, registry)
    stage_bitemporal_evidence(ctx, audit, args.data_root, args.resolution, snapshots)
    stage_debris_exposure(ctx, audit, args.debris_csv, snapshots)
    stage_event_record(ctx, audit)
    print(f"milton-2024 deep case built: {len(ctx.artifacts)} artifacts under {ctx.event_dir}")


if __name__ == "__main__":
    main()
