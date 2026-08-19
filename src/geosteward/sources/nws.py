"""NWS active alerts connector (keyless): floods, storms, heat, more."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nws"
HAZARD = "weather_alert"
URL = "https://api.weather.gov/alerts/active?status=actual"


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


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
