"""Build the Hurricane Ian 2022 deep case (Tier 3 evidence), fail-closed.

Third event through the same harness — Fort Myers / Lee County, FL
(landfall Cayo Costa, 2022-09-28, Cat 4). Two evidence layers:

- IAN_hurricane_mapillary_matched: 886 post-event street-view samples with
  3-class severity labels, matched to pre-event Mapillary; reliability-gated.
- CVIAN positions: 4,121 street-view sample locations. These carry NO
  reliable per-point severity link (no join key to pairs.csv labels), so
  they ship as a sample-density layer only — candor over coverage.

Usage:
  python scripts/build_ian_case.py [--data-root PATH] [--resolution 9]
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp
from geosteward.deepcase.grids import aggregate_labeled_points, cells_to_collection
from geosteward.harness.audit import AuditLog
from geosteward.harness.checks.outcome import (
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

EVENT_ID = "ian-2022"
AOI = {"min_lat": 26.30, "max_lat": 26.80, "min_lon": -82.40, "max_lon": -81.70}

IAN_CROSSWALK = {
    "0_MinorDamage": "minor",
    "1_ModerateDamage": "moderate",
    "2_SevereDamage": "severe",
}

REGISTRY_SNAPSHOTS = (
    "profiles/IAN_hurricane_mapillary_matched_profile.json",
    "profiles/IAN_hurricane_profile.json",
    "label_crosswalk.json",
)


def fail_closed(audit: AuditLog, stage: str, results) -> None:
    for r in results:
        audit.record("check", stage, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{stage}] outcome check failed: {r.check}: {r.detail}")


def bounds_checks(rows):
    lats = [r[0] for r in rows]
    lons = [r[1] for r in rows]
    return [
        check_bounds("min_lat", min(lats), AOI["min_lat"], AOI["max_lat"]),
        check_bounds("max_lat", max(lats), AOI["min_lat"], AOI["max_lat"]),
        check_bounds("min_lon", min(lons), AOI["min_lon"], AOI["max_lon"]),
        check_bounds("max_lon", max(lons), AOI["min_lon"], AOI["max_lon"]),
    ]


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


def stage_matched_evidence(
    ctx: EventContext, audit: AuditLog, data_root: Path, resolution: int, snapshots: list[str]
) -> None:
    stage = "evidence.crossview_grid"
    manifest = data_root / "IAN_hurricane_mapillary_matched" / "manifest.csv"
    rows = []
    with manifest.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            if row.get("match_quality") not in ("good", "usable"):
                continue
            try:
                lat, lon = float(row["post_latitude"]), float(row["post_longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            label = IAN_CROSSWALK.get((row.get("label_name") or "").strip(), "unknown")
            rows.append((lat, lon, label, row.get("sample_id", "")))
    if not rows:
        raise RuntimeError(f"[{stage}] no gated samples loaded from {manifest}")

    cells = aggregate_labeled_points(rows, resolution)
    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            *bounds_checks(rows),
            check_join_integrity(
                [r[3] for r in rows], [i for e in cells.values() for i in e["ids"]]
            ),
        ],
    )
    collection = cells_to_collection(
        cells,
        resolution,
        properties={
            "n_samples": len(rows),
            "canonical_label_field": "human_damage_perception",
            "source": "IAN_hurricane_mapillary_matched manifest (CrossViewGate line)",
        },
        cell_uncertainty={
            "reliability_gate": "match_quality in {good, usable} only",
            "label_source": "3-class severity from the CVIAN research line",
        },
    )
    fail_closed(audit, stage, [
        check_uncertainty_present(collection["features"][0]["properties"]),
    ])
    ctx.write_json(
        f"evidence/crossview_h3_r{resolution}_grid.geojson",
        collection,
        kind="evidence_grid",
        agent=stage,
        inputs=[manifest.as_posix()] + snapshots,
        notes=f"{len(rows)} gated matched samples in {len(cells)} cells, Fort Myers AOI",
    )
    audit.record("stage", stage, payload={"status": "ok", "n_samples": len(rows), "n_cells": len(cells)})


def stage_sample_density(
    ctx: EventContext, audit: AuditLog, data_root: Path, resolution: int, snapshots: list[str]
) -> None:
    stage = "evidence.svi_sample_density"
    positions = data_root / "IAN_hurricane" / "CVIAN_position.geojson"
    features = json.loads(positions.read_text(encoding="utf-8"))["features"]
    rows = []
    for f in features:
        lon, lat = f["geometry"]["coordinates"][:2]
        rows.append((lat, lon, "svi_sample", str(f["properties"].get("id", ""))))
    if not rows:
        raise RuntimeError(f"[{stage}] no positions loaded from {positions}")

    cells = aggregate_labeled_points(rows, resolution)
    fail_closed(
        audit,
        stage,
        [
            check_crs("EPSG:4326"),
            *bounds_checks(rows),
            check_join_integrity(
                [r[3] for r in rows], [i for e in cells.values() for i in e["ids"]]
            ),
        ],
    )
    collection = cells_to_collection(
        cells,
        resolution,
        properties={
            "n_samples": len(rows),
            "source": "CVIAN street-view sample positions (IAN_hurricane pairs)",
            "labels_note": "positions carry no per-point severity link (no reliable "
            "join key to pairs.csv labels) — density only, no damage claims",
        },
        cell_uncertainty={
            "content": "sample density only; severity labels intentionally not joined "
            "(no verifiable key) — candor over coverage",
        },
    )
    fail_closed(audit, stage, [
        check_uncertainty_present(collection["features"][0]["properties"]),
    ])
    ctx.write_json(
        f"evidence/svi_density_h3_r{resolution}_grid.geojson",
        collection,
        kind="sample_density_grid",
        agent=stage,
        inputs=[positions.as_posix()] + snapshots,
        notes=f"{len(rows)} street-view positions in {len(cells)} cells (unlabeled density)",
    )
    audit.record("stage", stage, payload={"status": "ok", "n_samples": len(rows), "n_cells": len(cells)})


def stage_event_record(ctx: EventContext, audit: AuditLog) -> None:
    stage = "dossier.event_record"
    record = {
        "event_id": EVENT_ID,
        "name": "Hurricane Ian",
        "hazard": "hurricane",
        "landfall": "2022-09-28, Cayo Costa, FL (Cat 4)",
        "aoi_bbox_wgs84": AOI,
        "evidence_tier": 3,
        "data_sources": [
            "IAN_hurricane_mapillary_matched cross-view set (matched_derived; 886 samples)",
            "CVIAN street-view positions (4,121 samples; density only)",
        ],
        "declared_unknowns": [
            "the 4,121-position layer has no verifiable per-point severity link — "
            "it shows where evidence exists, not what it concludes",
            "no exposure layer yet (no ground-truth structure damage source ingested); "
            "evidence-tier claims only",
            "social-vulnerability join pending: no vulnerability claims",
            "no parcel-level claims anywhere: all products are tile (H3 r9) resolution",
        ],
        "uncertainty": {
            "label_crosswalk": "3-class ordinal severity mapped to canonical "
            "minor/moderate/severe; see snapshots/registry/label_crosswalk.json"
        },
    }
    ctx.write_json(
        "dossier/event_record.json",
        record,
        kind="event_record",
        agent=stage,
        inputs=["snapshots/registry"],
        notes="Hurricane Ian 2022 deep-case dossier (evidence tier)",
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
        hazard="hurricane",
    )
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    registry = args.data_root / "_registry"

    snapshots = stage_registry_snapshot(ctx, audit, registry)
    stage_matched_evidence(ctx, audit, args.data_root, args.resolution, snapshots)
    stage_sample_density(ctx, audit, args.data_root, args.resolution, snapshots)
    stage_event_record(ctx, audit)
    print(f"ian-2022 deep case built: {len(ctx.artifacts)} artifacts under {ctx.event_dir}")


if __name__ == "__main__":
    main()
