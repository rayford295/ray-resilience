"""NWS active alerts connector (keyless): floods, storms, heat, more.

Note on ``geometry: null``: zone/county-scoped alerts (e.g. many Heat
Advisories, Winter Weather Advisories) are issued against NWS forecast
zones rather than a drawn polygon, so the feature's ``geometry`` field is
``null`` by design — this is normal NWS behavior, not malformed data. Such
alerts cannot be plotted as a point today and are not displayed; a future
enhancement (see Plan 4) may resolve zone centroids from the NWS zone
geometry service so these alerts can be shown too.
"""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json, merge_pages

SOURCE = "nws"
HAZARD = "weather_alert"
URL = "https://api.weather.gov/alerts/active?status=actual"
MAX_PAGES = 10  # api.weather.gov pages at 500 features; bound the walk and fail closed


def fetch(timeout: int = 30) -> Any:
    """Fetch active alerts, following pagination.next until exhausted.

    ``alerts/active`` pages results (500 features/page). Silently stopping
    at page one would under-report alerts during large events without any
    signal that data was dropped, so every ``pagination.next`` link is
    followed and merged. The walk is bounded (``MAX_PAGES``) and fails
    closed — raising rather than silently truncating — if the feed still
    has more pages once the cap is reached.
    """

    pages = [fetch_json(URL, timeout=timeout)]
    while pages[-1].get("pagination", {}).get("next"):
        if len(pages) >= MAX_PAGES:
            raise RuntimeError("NWS pagination exceeded page cap")
        next_url = pages[-1]["pagination"]["next"]
        pages.append(fetch_json(next_url, timeout=timeout))
    return merge_pages(pages)


def _centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Mean of the outer ring's vertices — a display anchor, not a survey point."""

    if geometry["type"] == "Point":
        lon, lat = geometry["coordinates"][:2]
        return float(lat), float(lon)
    ring = geometry["coordinates"][0]
    if geometry["type"] == "MultiPolygon":
        ring = geometry["coordinates"][0][0]
    lats = [point[1] for point in ring]
    lons = [point[0] for point in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            geometry = feature["geometry"]
            if not geometry:
                skipped += 1
                continue
            lat, lon = _centroid(geometry)
            props = feature["properties"]
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature["id"]),
                    hazard=HAZARD,
                    name=props.get("headline") or props["event"],
                    lat=lat,
                    lon=lon,
                    severity=str(props.get("severity", "Unknown")),
                    observed_utc=str(props.get("effective", "")),
                    properties={"event": props["event"], "area": props.get("areaDesc", "")},
                )
            )
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            skipped += 1
    return events, skipped
