"""Critical-facility context from OpenStreetMap, for deep-case AOIs.

What this module extracts is *presence in OSM*: a facility mapped by
contributors, at a point, with a category. What it deliberately does not
claim is operational status — whether a hospital is open, staffed, or
standing after the event is a different statement needing different
evidence, and every feature carries that boundary in its own uncertainty
field. Absence from the extract is not evidence of absence on the ground:
OSM completeness varies by place, and the collection declares that too.

License: OSM data is ODbL — redistributable with attribution and
share-alike. The attribution string is embedded in the artifact itself so
the obligation travels with the file, and the artifact kind is classified
`open-license-attribution` in the distribution plane.
"""

from __future__ import annotations

import json
from typing import Any, Iterable
from urllib import parse as _parse
from urllib import request as _request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
#: Public Overpass instances, tried in order. The main instance sheds load
#: with 504s at busy times; a mirror serving the same OSM data is not a
#: different source, so falling through preserves fail-closed semantics —
#: what is never accepted is a *partial* response (see `remark` handling).
OVERPASS_MIRRORS = (
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
)
OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL 1.0)"

#: The four amenity values extracted, and the honest scope of each: these are
#: the disaster-relevant categories with the strongest OSM tagging conventions.
#: Shelters and schools are deliberately excluded in v1 — their OSM tagging is
#: inconsistent enough that an extract would understate more than it informs.
AMENITIES = ("hospital", "clinic", "fire_station", "police")

DECLARED_UNKNOWNS = [
    "OSM presence only: whether a facility is open, staffed, or intact after "
    "the event is not claimed and cannot be read from this layer",
    "OSM completeness varies by place: a facility absent here may exist on "
    "the ground",
]


def bbox_of_features(features: Iterable[dict[str, Any]], pad_deg: float = 0.02) -> tuple[float, float, float, float]:
    """(south, west, north, east) envelope of a GeoJSON feature list, padded.

    The AOI a facility extract belongs to is defined by the evidence already
    committed — the envelope of an event's grid cells — so the extract can
    never quietly cover ground the event's own artifacts do not.
    """
    lats: list[float] = []
    lons: list[float] = []

    def walk(coords: Any) -> None:
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                walk(c)

    for f in features:
        walk(f["geometry"]["coordinates"])
    if not lats:
        raise ValueError("no coordinates in features; cannot derive an AOI bbox")
    return (min(lats) - pad_deg, min(lons) - pad_deg, max(lats) + pad_deg, max(lons) + pad_deg)


def overpass_query(bboxes: list[tuple[float, float, float, float]], amenities: tuple[str, ...] = AMENITIES) -> str:
    """One Overpass QL query covering every AOI bbox of an event."""
    regex = "|".join(amenities)
    parts = []
    for south, west, north, east in bboxes:
        box = f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"
        parts.append(f'node["amenity"~"{regex}"]{box};')
        parts.append(f'way["amenity"~"{regex}"]{box};')
    body = "".join(parts)
    return f"[out:json][timeout:60];({body});out center tags;"


def fetch_overpass(
    query: str, urls: tuple[str, ...] = OVERPASS_MIRRORS, timeout: int = 90
) -> dict[str, Any]:
    """POST the query to each instance in turn; fail closed if all refuse.

    Overpass reports its own truncations and timeouts as a 200 response with
    a `remark` field. Treating that as success would build a silently partial
    extract, which is exactly the failure mode this pipeline exists to refuse
    — so a `remark` is an error, never a fallthrough to the next mirror with
    the partial payload kept.
    """
    errors: list[str] = []
    for url in urls:
        try:
            return _fetch_one(query, url, timeout)
        except Exception as exc:  # noqa: BLE001 — every mirror error is recorded
            errors.append(f"{url}: {exc}")
    raise RuntimeError("all Overpass instances refused the query: " + "; ".join(errors))


def _fetch_one(query: str, url: str, timeout: int) -> dict[str, Any]:
    # Overpass's usage policy asks clients to identify themselves; the default
    # Python-urllib agent is rejected outright (HTTP 406).
    req = _request.Request(
        url,
        data=_parse.urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "RayResilience/0.1 (research prototype; github.com/rayford295/ray-resilience)"},
    )
    data = _request.urlopen(req, timeout=timeout)  # noqa: S310 — fixed https endpoint
    payload = json.loads(data.read().decode("utf-8"))
    if payload.get("remark"):
        raise RuntimeError(f"Overpass reported a problem; refusing partial data: {payload['remark']}")
    return payload


def elements_to_features(
    elements: Iterable[dict[str, Any]], amenities: tuple[str, ...] = AMENITIES
) -> list[dict[str, Any]]:
    """Overpass elements -> GeoJSON point features, deduplicated by OSM id.

    Ways and relations collapse to their Overpass-computed center point —
    a building footprint's center is well within tile resolution (H3 r9,
    ~0.1 km²), which is the finest geography this artifact may support
    anyway. Elements without a resolvable coordinate or an amenity in scope
    are dropped and counted by the caller via the length difference.
    """
    seen: set[tuple[str, int]] = set()
    features: list[dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        if amenity not in amenities:
            continue
        key = (el.get("type", "?"), el.get("id", -1))
        if key in seen:
            continue
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        seen.add(key)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": tags.get("name") or "(unnamed in OSM)",
                    "category": amenity,
                    "osm_ref": f"{el['type']}/{el['id']}",
                    "uncertainty": {
                        "operational_status": "unknown — OSM records presence, not status",
                        "position": "way/relation centers are footprint centroids",
                    },
                },
            }
        )
    features.sort(key=lambda f: (f["properties"]["category"], f["properties"]["name"]))
    return features
