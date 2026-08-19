"""Exposure agent: hazard footprint geometry from the captured track."""

from __future__ import annotations

import json

from geosteward.agents.base import Agent, Artifact, EventContext
from geosteward.agents.dossier import latest_snapshot
from geosteward.hazards.typhoon import parse_track, wind_sector_polygon


class TyphoonExposure:
    """Beaufort-threshold wind footprints as GeoJSON, per track point.

    This is the geometry layer of Phase 1: downstream population/building
    intersection consumes these polygons. Footprints derived from forecast
    points are forecast-conditioned and labeled as such.
    """

    name = "exposure.typhoon"
    thresholds = (7, 10, 12)

    def run(self, context: EventContext) -> list[Artifact]:
        snapshot_path = latest_snapshot(context)
        if snapshot_path is None:
            raise FileNotFoundError(f"No snapshots under {context.event_dir}/snapshots.")
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        points = parse_track(payload)

        features = []
        for point in points:
            for threshold in self.thresholds:
                polygon = wind_sector_polygon(point, threshold)
                if polygon is None:
                    continue
                ring = [[lng, lat] for lng, lat in polygon]
                ring.append(ring[0])
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [ring]},
                        "properties": {
                            "time": point.time,
                            "beaufort_threshold": threshold,
                            "grade": point.grade,
                            "pressure_hpa": point.pressure_hpa,
                            "wind_ms": point.wind_ms,
                        },
                    }
                )
        collection = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "event_id": context.event_id,
                "source_snapshot": snapshot_path.name,
                "note": "observed-track footprints; equirectangular approximation",
            },
        }
        artifact = context.write_json(
            "exposure/wind_footprints.geojson",
            collection,
            kind="wind_footprints",
            agent=self.name,
            inputs=[snapshot_path.name],
            notes=f"{len(features)} sector polygons across thresholds {self.thresholds}",
        )
        return [artifact]
