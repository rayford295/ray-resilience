"""NIFC/WFIGS current wildfire incidents connector (keyless ArcGIS feed)."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nifc"
HAZARD = "wildfire"
URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
    "?where=1%3D1&outFields=IncidentName,FireDiscoveryDateTime,IncidentSize,"
    "PercentContained,POOState&returnGeometry=true&f=geojson"
)


def raise_on_arcgis_error(payload: Any) -> Any:
    """Fail closed on an ArcGIS error envelope instead of masquerading as zero hazards.

    ArcGIS query endpoints return HTTP 200 with a JSON body like
    ``{"error": {"code": 400, "details": [...]}}`` on a bad request (e.g. an
    invalid outFields name). Without this check, ``parse`` would see no
    "features" key, silently report zero events, and the orchestrator would
    record the source as "ok" — a fail-open masked as ok.
    """

    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(f"ArcGIS error: {payload['error']}")
    return payload


def fetch(timeout: int = 30) -> Any:
    return raise_on_arcgis_error(fetch_json(URL, timeout=timeout))


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            geometry = feature["geometry"]
            if not geometry:
                skipped += 1
                continue
            lon, lat = geometry["coordinates"][:2]
            props = feature["properties"]
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature.get("id", props["IncidentName"])),
                    hazard=HAZARD,
                    name=str(props["IncidentName"]),
                    lat=float(lat),
                    lon=float(lon),
                    severity=str(props.get("IncidentSize", "")),
                    observed_utc=str(props.get("FireDiscoveryDateTime", "")),
                    properties={
                        "percent_contained": props.get("PercentContained"),
                        "state": props.get("POOState"),
                    },
                )
            )
        except (KeyError, TypeError, ValueError, IndexError):
            skipped += 1
    return events, skipped
