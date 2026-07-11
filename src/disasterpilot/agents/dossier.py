"""Dossier agent: turn the latest raw snapshot into a structured event record."""

from __future__ import annotations

import json
from pathlib import Path

from disasterpilot.agents.base import Agent, Artifact, EventContext
from disasterpilot.hazards.typhoon import parse_track, track_summary


def latest_snapshot(context: EventContext) -> Path | None:
    snapshots = sorted((context.event_dir / "snapshots").glob("*.json"))
    return snapshots[-1] if snapshots else None


class TyphoonDossier:
    """Structured, source-attributed event record from captured track data.

    Numbers here come only from captured payloads; narrative facts (casualties,
    warnings) live in the human-curated dossier document and are never
    auto-generated from unverified text.
    """

    name = "dossier.typhoon"

    def run(self, context: EventContext) -> list[Artifact]:
        snapshot_path = latest_snapshot(context)
        if snapshot_path is None:
            raise FileNotFoundError(f"No snapshots under {context.event_dir}/snapshots.")
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        points = parse_track(payload)
        summary = track_summary(points)
        record = {
            "event_id": context.event_id,
            "hazard": "typhoon",
            "tfid": payload.get("tfid"),
            "name": payload.get("name"),
            "enname": payload.get("enname"),
            "isactive": payload.get("isactive"),
            "source_snapshot": snapshot_path.name,
            "track": summary,
            "landfalls_reported_by_source": payload.get("land", []),
        }
        artifact = context.write_json(
            "dossier/event_record.json",
            record,
            kind="event_record",
            agent=self.name,
            inputs=[snapshot_path.name],
            notes="machine-verifiable facts only; narrative dossier is curated separately",
        )
        return [artifact]
