"""Tile-level population exposure from 2020 Census blocks.

The unit of allocation is the census block — the smallest geography the
decennial count publishes — assigned to the H3 r9 tile its centroid falls
in. TIGERweb serves the centroid and the count as plain attributes
(CENTLAT/CENTLON, POP100), so no polygon is ever downloaded and no areal
interpolation is invented: a block straddling tile edges is wholly assigned
to its centroid's tile, and every feature declares exactly that.

Two boundaries are declared rather than smoothed over. The count is the
2020 decennial — it predates every event here, so it is *pre-event
population*, not who was present when the hazard arrived. And the query
envelope is larger than the evaluated tiles, so population landing in
unevaluated cells is reported as an unassigned total, never silently
dropped and never invented into tiles the event has no evidence for.
"""

from __future__ import annotations

import json
from typing import Any, Iterable
from urllib import parse as _parse
from urllib import request as _request

import h3

TIGERWEB_BLOCKS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "Tracts_Blocks/MapServer/12/query"
)

_UA = "GeoSteward/1.0 (research prototype; github.com/rayford295/GeoSteward)"


def blocks_query_params(bbox: tuple[float, float, float, float]) -> dict[str, str]:
    """Query params for one AOI envelope: attributes only, no geometry."""
    south, west, north, east = bbox
    return {
        "where": "1=1",
        "geometry": f"{west},{south},{east},{north}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "GEOID,POP100,CENTLAT,CENTLON",
        "returnGeometry": "false",
        "resultRecordCount": "100000",
        "f": "json",
    }


def fetch_blocks(bbox: tuple[float, float, float, float], url: str = TIGERWEB_BLOCKS_URL, timeout: int = 120) -> dict[str, Any]:
    """One envelope's blocks; fail closed on errors and on truncation.

    ArcGIS reports truncation as `exceededTransferLimit: true` inside a 200
    response. A truncated block set would silently undercount population,
    so it aborts the build instead of shipping a partial sum.
    """
    req = _request.Request(
        url + "?" + _parse.urlencode(blocks_query_params(bbox)),
        headers={"User-Agent": _UA},
    )
    payload = json.loads(_request.urlopen(req, timeout=timeout).read().decode("utf-8"))  # noqa: S310
    if "error" in payload:
        raise RuntimeError(f"TIGERweb error envelope: {payload['error']}")
    if payload.get("exceededTransferLimit"):
        raise RuntimeError("TIGERweb truncated the block set; refusing a partial population sum")
    return payload


def blocks_to_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """ArcGIS attribute rows -> {geoid, pop, lat, lon}, dropping the unusable.

    Rows without a parseable centroid cannot be allocated and are returned
    separately by the caller's accounting (length difference), not guessed.
    """
    rows = []
    for feat in payload.get("features", []):
        a = feat.get("attributes", {})
        try:
            lat, lon = float(a["CENTLAT"]), float(a["CENTLON"])
        except (KeyError, TypeError, ValueError):
            continue
        pop = a.get("POP100") or 0
        rows.append({"geoid": a.get("GEOID", "?"), "pop": int(pop), "lat": lat, "lon": lon})
    return rows


def allocate_to_cells(
    rows: Iterable[dict[str, Any]], evaluated_cells: set[str], resolution: int = 9
) -> tuple[dict[str, int], int, int]:
    """Sum block populations into evaluated tiles by centroid containment.

    Returns (per-cell sums over evaluated cells, population assigned,
    population that fell in the envelope but outside every evaluated cell).
    Duplicate GEOIDs — a block intersecting two query envelopes — count once.
    """
    per_cell: dict[str, int] = {}
    assigned = 0
    unassigned = 0
    seen: set[str] = set()
    for row in rows:
        if row["geoid"] in seen:
            continue
        seen.add(row["geoid"])
        cell = h3.latlng_to_cell(row["lat"], row["lon"], resolution)
        if cell in evaluated_cells:
            per_cell[cell] = per_cell.get(cell, 0) + row["pop"]
            assigned += row["pop"]
        else:
            unassigned += row["pop"]
    return per_cell, assigned, unassigned
