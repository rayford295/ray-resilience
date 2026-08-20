"""CDC/ATSDR SVI tract join: assign H3 cells to census tracts, attach SVI.

Pure-python even-odd point-in-polygon over GeoJSON geometry — no GIS
dependency. SVI percentile ranks (RPL_*) are tract-level; attaching them to
an H3 cell is a downscaling approximation and every output row says so.

CDC encodes missing SVI values as -999; those become None and are counted,
never silently dropped.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

SVI_FIELDS = ("RPL_THEMES", "RPL_THEME1", "RPL_THEME2", "RPL_THEME3", "RPL_THEME4")
CDC_MISSING = -999.0


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-cast one ring; even-odd rule accumulates across rings."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    """Even-odd test over all rings: holes flip the state back out."""
    gtype = geometry["type"]
    if gtype == "Polygon":
        polys = [geometry["coordinates"]]
    elif gtype == "MultiPolygon":
        polys = geometry["coordinates"]
    else:
        raise ValueError(f"unsupported geometry type: {gtype}")
    inside = False
    for poly in polys:
        for ring in poly:
            if _point_in_ring(lon, lat, ring):
                inside = not inside
    return inside


def assign_points_to_tracts(
    points: list[tuple[str, float, float]], tract_features: list[dict[str, Any]]
) -> dict[str, str | None]:
    """(id, lat, lon) -> {id: GEOID or None}. Linear scan; AOI-scale inputs."""
    assignment: dict[str, str | None] = {}
    for pid, lat, lon in points:
        assignment[pid] = None
        for feature in tract_features:
            if point_in_geometry(lon, lat, feature["geometry"]):
                assignment[pid] = feature["properties"]["GEOID"]
                break
    return assignment


def load_svi_rows(csv_path: Path, county_fips: str) -> dict[str, dict[str, float | None]]:
    """CDC SVI state CSV -> {tract FIPS: {RPL_*: value or None}}."""
    table: dict[str, dict[str, float | None]] = {}
    with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            fips = (row.get("FIPS") or "").strip()
            if not fips.startswith(county_fips):
                continue
            values: dict[str, float | None] = {}
            for field in SVI_FIELDS:
                try:
                    v = float(row.get(field, ""))
                except (TypeError, ValueError):
                    v = CDC_MISSING
                values[field] = None if v == CDC_MISSING else v
            table[fips] = values
    return table
