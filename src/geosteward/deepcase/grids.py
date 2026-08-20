"""Generic H3 grid helpers for deep-case builders.

Any labeled point set (street-view samples, survey points) aggregates the
same way: points -> H3 cells -> label histogram per cell. Hazard-specific
meaning stays in the calling script; this module is geometry and counting.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

import h3


def h3_ring(cell: str) -> list[list[float]]:
    """Closed GeoJSON ring ([lng, lat]) for one H3 cell."""
    ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
    ring.append(ring[0])
    return ring


def aggregate_labeled_points(
    rows: Iterable[tuple[float, float, str, str]], resolution: int
) -> dict[str, dict[str, Any]]:
    """(lat, lon, label, id) tuples -> {cell: {labels: Counter, n, ids}}."""
    cells: dict[str, dict[str, Any]] = {}
    for lat, lon, label, row_id in rows:
        cell = h3.latlng_to_cell(lat, lon, resolution)
        entry = cells.setdefault(cell, {"labels": Counter(), "n": 0, "ids": []})
        entry["labels"][label] += 1
        entry["n"] += 1
        entry["ids"].append(row_id)
    return cells


def cells_to_collection(
    cells: dict[str, dict[str, Any]],
    resolution: int,
    properties: dict[str, Any],
    cell_uncertainty: dict[str, Any],
) -> dict[str, Any]:
    """Cells -> GeoJSON FeatureCollection with per-cell uncertainty attached."""
    features = []
    for cell, entry in sorted(cells.items()):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [h3_ring(cell)]},
                "properties": {
                    "h3_cell": cell,
                    "n_samples": entry["n"],
                    "labels": dict(entry["labels"]),
                    "uncertainty": dict(cell_uncertainty),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "h3_resolution": resolution,
            "n_cells": len(features),
            "resolution_cap": "tile",
            **properties,
        },
    }
