"""NHC current tropical cyclones connector (keyless)."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nhc"
HAZARD = "tropical_cyclone"
URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

_CLASS_LABELS = {
    "HU": "Hurricane",
    "TS": "Tropical Storm",
    "TD": "Tropical Depression",
    "STD": "Subtropical Depression",
    "STS": "Subtropical Storm",
    "PTC": "Post-tropical Cyclone",
    "PC": "Potential Tropical Cyclone",
}


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for storm in payload.get("activeStorms", []):
        try:
            classification = str(storm.get("classification", ""))
            label = _CLASS_LABELS.get(classification, classification or "Cyclone")
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(storm["id"]),
                    hazard=HAZARD,
                    name=f"{label} {storm['name']}",
                    lat=float(storm["latitudeNumeric"]),
                    lon=float(storm["longitudeNumeric"]),
                    severity=str(storm.get("intensity", "")),
                    observed_utc=str(storm.get("lastUpdate", "")),
                    properties={
                        "classification": classification,
                        "pressure_mb": storm.get("pressure"),
                        "movement_dir": storm.get("movementDir"),
                        "movement_kt": storm.get("movementSpeed"),
                    },
                )
            )
        except (KeyError, TypeError, ValueError):
            skipped += 1
    return events, skipped
