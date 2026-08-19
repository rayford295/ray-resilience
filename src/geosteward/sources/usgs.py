"""USGS earthquake feed connector (keyless, updated every minute)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "usgs"
HAZARD = "earthquake"
URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            lon, lat, depth_km = feature["geometry"]["coordinates"][:3]
            props = feature["properties"]
            observed = dt.datetime.fromtimestamp(
                props["time"] / 1000, tz=dt.timezone.utc
            ).strftime("%Y%m%dT%H%M%SZ")
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature["id"]),
                    hazard=HAZARD,
                    name=f"M {props['mag']} - {props['place']}",
                    lat=float(lat),
                    lon=float(lon),
                    severity=str(props["mag"]),
                    observed_utc=observed,
                    properties={"depth_km": float(depth_km)},
                )
            )
        except (KeyError, TypeError, ValueError, IndexError):
            skipped += 1
    return events, skipped
