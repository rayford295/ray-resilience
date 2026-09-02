"""WPC Excessive Rainfall Outlook connector (keyless NOAA ArcGIS feed).

This is the project's first *forward-looking* source, and the product it
feeds is kept separate from the national watch on purpose: the watch layer
says what is happening; this says where excessive rainfall — the flash-flood
precursor — is more likely than not to occur within Day 1. Polygons, not
points, and a forecast, not an observation, so mixing the two into one file
would let each borrow the other's meaning.

The outlook categories are WPC's own ordinal scale. An outlook label this
module does not recognize is skipped and counted, never guessed into a
level — a new WPC category deserves a code change, not a silent bucket.
"""

from __future__ import annotations

from typing import Any

from geosteward.sources.nifc import raise_on_arcgis_error
from geosteward.sources.watchbase import fetch_json

SOURCE = "wpc_ero"
URL = (
    "https://mapservices.weather.noaa.gov/vector/rest/services/hazards/"
    "wpc_precip_hazards/MapServer/0/query"
    "?where=1%3D1&outFields=outlook,issue_time,start_time,end_time"
    "&returnGeometry=true&outSR=4326&f=geojson"
)

#: WPC's Day-1 categories, ordinal. Keys are matched on the label's leading
#: word so the probability suffix ("(At Least 5%)") can change without
#: silently dropping every polygon.
LEVELS = {"marginal": 1, "slight": 2, "moderate": 3, "high": 4}

BOUNDARY = (
    "Outlook only — a forecast of excessive-rainfall potential (Day 1), not "
    "observed flooding and not damage. No damage or exposure conclusions are "
    "supported. Does not replace official NWS warnings."
)


def fetch(timeout: int = 30) -> Any:
    return raise_on_arcgis_error(fetch_json(URL, timeout=timeout))


def parse(payload: Any) -> tuple[list[dict[str, Any]], int]:
    """(polygon features with normalized properties, skipped count)."""
    features: list[dict[str, Any]] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            geometry = feature["geometry"]
            props = feature["properties"]
            label = (props.get("outlook") or "").strip()
            level = LEVELS.get(label.split(" ")[0].lower()) if label else None
            if not geometry or level is None:
                skipped += 1
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "outlook": label,
                        "level": level,
                        "issue_time": props.get("issue_time"),
                        "start_time": props.get("start_time"),
                        "end_time": props.get("end_time"),
                    },
                }
            )
        except (KeyError, TypeError, AttributeError):
            skipped += 1
    features.sort(key=lambda f: f["properties"]["level"])
    return features, skipped


def build_flood_outlook(
    features: list[dict[str, Any]], skipped: int, generated_utc: str
) -> dict[str, Any]:
    """The published product: polygons plus their own account of what they are."""
    issue_times = sorted({f["properties"]["issue_time"] for f in features if f["properties"]["issue_time"]})
    return {
        "type": "FeatureCollection",
        "crs_declared": "EPSG:4326",
        "features": features,
        "properties": {
            "source": "NOAA/WPC Excessive Rainfall Outlook, Day 1 (public domain)",
            "generated_utc": generated_utc,
            "issue_time": issue_times[-1] if issue_times else None,
            "n_areas": len(features),
            "skipped": skipped,
            "levels": {str(v): k for k, v in LEVELS.items()},
            "declared_boundary": BOUNDARY,
        },
    }
