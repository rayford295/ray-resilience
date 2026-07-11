"""Parse Zhejiang Water Resources typhoon-API payloads into normalized tracks.

The API returns one JSON object per typhoon with a `points` list. Each point
carries position, intensity, and quadrant wind radii encoded as
"NE|SE|SW|NW" kilometer strings for Beaufort 7/10/12 (`radius7/10/12`).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

QUADRANT_ORDER = ("ne", "se", "sw", "nw")


@dataclass(frozen=True)
class WindRadii:
    """Quadrant wind radii in kilometers for one Beaufort threshold."""

    ne: float
    se: float
    sw: float
    nw: float

    @classmethod
    def from_api(cls, raw: str | None) -> "WindRadii | None":
        if not raw:
            return None
        parts = raw.split("|")
        if len(parts) != 4:
            return None
        try:
            values = [float(part) for part in parts]
        except ValueError:
            return None
        return cls(*values)

    def max_km(self) -> float:
        return max(self.ne, self.se, self.sw, self.nw)


@dataclass(frozen=True)
class TrackPoint:
    time: str
    lat: float
    lng: float
    grade: str
    beaufort: int | None
    wind_ms: float | None
    pressure_hpa: float | None
    move_dir: str | None
    move_kmh: float | None
    radii: dict[int, WindRadii] = field(default_factory=dict)


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def parse_point(raw: dict[str, Any]) -> TrackPoint:
    radii = {}
    for threshold in (7, 10, 12):
        parsed = WindRadii.from_api(raw.get(f"radius{threshold}"))
        if parsed is not None:
            radii[threshold] = parsed
    lat = _to_float(raw.get("lat"))
    lng = _to_float(raw.get("lng"))
    if lat is None or lng is None:
        raise ValueError(f"Track point missing coordinates: {raw!r}")
    return TrackPoint(
        time=str(raw.get("time")),
        lat=lat,
        lng=lng,
        grade=str(raw.get("strong") or ""),
        beaufort=_to_int(raw.get("power")),
        wind_ms=_to_float(raw.get("speed")),
        pressure_hpa=_to_float(raw.get("pressure")),
        move_dir=raw.get("movedirection") or None,
        move_kmh=_to_float(raw.get("movespeed")),
        radii=radii,
    )


def parse_track(payload: dict[str, Any]) -> list[TrackPoint]:
    return [parse_point(raw) for raw in payload.get("points", [])]


def load_snapshot(path: Path) -> tuple[dict[str, Any], list[TrackPoint]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload, parse_track(payload)


def wind_sector_polygon(
    point: TrackPoint,
    threshold: int,
    steps_per_quadrant: int = 8,
) -> list[tuple[float, float]] | None:
    """Approximate the quadrant wind-radius footprint as a (lng, lat) polygon.

    Quadrant radii are swept through their 90-degree arcs on a local
    equirectangular approximation — adequate for exposure counting at
    typhoon scale, not for navigation.
    """

    radii = point.radii.get(threshold)
    if radii is None:
        return None
    km_per_deg_lat = 110.574
    km_per_deg_lng = 111.320 * math.cos(math.radians(point.lat))
    quadrant_radii = [radii.ne, radii.se, radii.sw, radii.nw]
    polygon = []
    for quadrant_index, radius_km in enumerate(quadrant_radii):
        start_deg = quadrant_index * 90.0
        for step in range(steps_per_quadrant):
            azimuth = math.radians(start_deg + 90.0 * step / steps_per_quadrant)
            north_km = radius_km * math.cos(azimuth)
            east_km = radius_km * math.sin(azimuth)
            polygon.append(
                (
                    point.lng + east_km / km_per_deg_lng,
                    point.lat + north_km / km_per_deg_lat,
                )
            )
    return polygon


def track_summary(points: list[TrackPoint]) -> dict[str, Any]:
    if not points:
        return {"n_points": 0}
    peak = min(
        (p for p in points if p.pressure_hpa is not None),
        key=lambda p: p.pressure_hpa,
        default=None,
    )
    return {
        "n_points": len(points),
        "first_time": points[0].time,
        "last_time": points[-1].time,
        "peak_pressure_hpa": peak.pressure_hpa if peak else None,
        "peak_wind_ms": peak.wind_ms if peak else None,
        "peak_time": peak.time if peak else None,
        "last_position": {"lat": points[-1].lat, "lng": points[-1].lng},
        "last_grade": points[-1].grade,
    }
