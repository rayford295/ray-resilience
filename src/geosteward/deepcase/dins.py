"""DINS structure-damage ingest and H3 tile aggregation (Eaton Fire 2025).

CAL FIRE Damage Inspection (DINS) points are per-structure damage records —
parcel-level ground truth. Institutional validity caps public products at
tile level, so the published grid aggregates points into H3 cells and
suppresses per-structure identity; the point layer itself is registered as a
restricted-resolution artifact, never shipped to the resident-facing app.

Labels are normalized through the registry crosswalk to the canonical
`human_damage_perception` scale: none/minor/moderate/severe/destroyed/unknown.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import h3

CANONICAL_SCALE = ("none", "minor", "moderate", "severe", "destroyed", "unknown")

#: Native DINS DAMAGE values -> canonical severity. Percent-loss to perception
#: mapping is approximate; declared in the registry crosswalk for owner review.
DINS_CROSSWALK = {
    "No Damage": "none",
    "Affected (1-9%)": "minor",
    "Minor (10-25%)": "moderate",
    "Major (26-50%)": "severe",
    "Destroyed (>50%)": "destroyed",
    "Inaccessible": "unknown",
}

#: Cells with fewer structures than this are flagged low_n: too few records
#: for a stable rate, and small counts edge toward parcel identifiability.
MIN_CELL_COUNT = 3


@dataclass(frozen=True)
class DinsPoint:
    lat: float
    lon: float
    damage_native: str
    severity: str
    structure_type: str
    objectid: str


def load_dins_points(csv_paths: Iterable[Path]) -> list[DinsPoint]:
    """Read DINS per-class CSV exports; skip rows without coordinates."""
    points: list[DinsPoint] = []
    for path in csv_paths:
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                try:
                    lat, lon = float(row["lat"]), float(row["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                native = (row.get("DAMAGE") or "").strip()
                points.append(
                    DinsPoint(
                        lat=lat,
                        lon=lon,
                        damage_native=native,
                        severity=DINS_CROSSWALK.get(native, "unknown"),
                        structure_type=(row.get("STRUCTURETYPE") or "").strip(),
                        objectid=str(row.get("OBJECTID", "")),
                    )
                )
    return points


def aggregate_h3(points: list[DinsPoint], resolution: int = 9) -> dict[str, dict[str, Any]]:
    """Aggregate points into H3 cells: severity histogram + uncertainty fields."""
    cells: dict[str, dict[str, Any]] = {}
    for p in points:
        cell = h3.latlng_to_cell(p.lat, p.lon, resolution)
        entry = cells.setdefault(
            cell, {"counts": Counter(), "n": 0, "point_ids": []}
        )
        entry["counts"][p.severity] += 1
        entry["n"] += 1
        entry["point_ids"].append(p.objectid)
    return cells


def cell_feature(cell: str, entry: dict[str, Any]) -> dict[str, Any]:
    """One H3 cell as a GeoJSON feature with mandatory uncertainty fields."""
    boundary = h3.cell_to_boundary(cell)  # ((lat, lng), ...)
    ring = [[lng, lat] for lat, lng in boundary]
    ring.append(ring[0])
    counts = entry["counts"]
    n = entry["n"]
    assessed = n - counts.get("unknown", 0)
    destroyed_rate = counts.get("destroyed", 0) / assessed if assessed else None
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {
            "h3_cell": cell,
            "n_structures": n,
            **{f"n_{s}": counts.get(s, 0) for s in CANONICAL_SCALE},
            "destroyed_rate": round(destroyed_rate, 4) if destroyed_rate is not None else None,
            "uncertainty": {
                "n_unassessed": counts.get("unknown", 0),
                "low_n": n < MIN_CELL_COUNT,
                "source": "DINS field survey; rates undefined where all points inaccessible",
            },
        },
    }


def grid_feature_collection(
    cells: dict[str, dict[str, Any]], resolution: int, source_notes: str
) -> dict[str, Any]:
    features = [cell_feature(cell, entry) for cell, entry in sorted(cells.items())]
    return {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "h3_resolution": resolution,
            "n_cells": len(features),
            "resolution_cap": "tile",
            "canonical_label_field": "human_damage_perception",
            "source": source_notes,
        },
    }


def severity_totals(points: list[DinsPoint]) -> dict[str, int]:
    totals = Counter(p.severity for p in points)
    return {s: totals.get(s, 0) for s in CANONICAL_SCALE}
