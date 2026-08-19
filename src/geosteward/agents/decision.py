"""Decision agent: turn upstream artifacts into a watch bulletin with actions."""

from __future__ import annotations

import json

from geosteward.agents.base import Agent, Artifact, EventContext, utc_stamp


class WatchBulletin:
    """Pre-event decision product: what to watch, what to prepare, what is unknown.

    Consumes the dossier record and exposure footprints; emits a Markdown
    bulletin plus a machine-readable action list. Every action carries its
    evidence source; unknowns are listed explicitly rather than omitted.
    """

    name = "decision.watch_bulletin"

    def run(self, context: EventContext) -> list[Artifact]:
        record_path = context.event_dir / "dossier" / "event_record.json"
        footprints_path = context.event_dir / "exposure" / "wind_footprints.geojson"
        if not record_path.exists() or not footprints_path.exists():
            raise FileNotFoundError("WatchBulletin needs dossier + exposure artifacts first.")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        footprints = json.loads(footprints_path.read_text(encoding="utf-8"))

        track = record.get("track", {})
        last = track.get("last_position", {})
        n_severe = sum(
            1
            for feature in footprints["features"]
            if feature["properties"]["beaufort_threshold"] >= 10
        )
        actions = [
            {
                "action": "maintain_track_capture",
                "reason": f"event isactive={record.get('isactive')}",
                "evidence": record.get("source_snapshot"),
            },
            {
                "action": "prepare_imagery_tasking",
                "reason": "SAR (Sentinel-1) first post-landfall pass sees through cloud",
                "evidence": "methodology.md Phase 2",
            },
            {
                "action": "intersect_footprints_with_population",
                "reason": f"{n_severe} Beaufort>=10 footprint polygons available",
                "evidence": "exposure/wind_footprints.geojson",
            },
        ]
        unknowns = [
            "population/building exposure counts (grids not yet integrated)",
            "landfall parameters until best-track reconciliation",
            "post-event damage (evidence agent fails closed pre-imagery)",
        ]
        payload = {
            "event_id": context.event_id,
            "generated_utc": utc_stamp(),
            "last_position": last,
            "last_grade": track.get("last_grade"),
            "peak_pressure_hpa": track.get("peak_pressure_hpa"),
            "actions": actions,
            "declared_unknowns": unknowns,
        }
        json_artifact = context.write_json(
            "decision/watch_bulletin.json",
            payload,
            kind="watch_bulletin",
            agent=self.name,
            inputs=["dossier/event_record.json", "exposure/wind_footprints.geojson"],
        )

        lines = [
            f"# Watch bulletin — {record.get('enname')} ({record.get('tfid')})",
            "",
            f"Generated {payload['generated_utc']} · last fix {last} "
            f"({track.get('last_grade')}), peak {track.get('peak_pressure_hpa')} hPa.",
            "",
            "## Actions",
            "",
        ]
        lines += [f"- **{a['action']}** — {a['reason']} _(evidence: {a['evidence']})_" for a in actions]
        lines += ["", "## Declared unknowns", ""]
        lines += [f"- {u}" for u in unknowns]
        lines.append("")
        md_path = context.event_dir / "decision" / "watch_bulletin.md"
        md_path.write_text("\n".join(lines), encoding="utf-8")
        md_artifact = context.register(
            Artifact(
                path=md_path,
                kind="watch_bulletin_md",
                agent=self.name,
                created_utc=payload["generated_utc"],
                inputs=json_artifact.inputs,
            )
        )
        return [json_artifact, md_artifact]
