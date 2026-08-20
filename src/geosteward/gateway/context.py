"""Evidence retrieval: manifest-listed artifacts only, never the open web.

Every fact handed to the LLM carries an artifact ID (the first 12 hex chars
of the artifact's manifest SHA-256), so every sentence the agent writes can
cite its way back to a committed, hashed product.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h3

RESOLUTION = 9


@dataclass
class Fact:
    text: str
    artifact_id: str
    source_path: str

    def as_evidence_line(self) -> str:
        return f"{self.text} [artifact:{self.artifact_id}]"


@dataclass
class EventEvidence:
    event_id: str
    evidence_tier: int
    in_aoi: bool
    facts: list[Fact] = field(default_factory=list)

    @property
    def artifact_ids(self) -> set[str]:
        return {f.artifact_id for f in self.facts}


def _scalar_items(props: dict[str, Any]) -> str:
    pairs = []
    for k, v in props.items():
        if k in ("h3_cell",) or isinstance(v, (dict, list)):
            continue
        pairs.append(f"{k}={v}")
    return ", ".join(pairs)


class EvidenceStore:
    """Loads committed deep-case artifacts and serves tile-level facts."""

    def __init__(self, events_root: Path):
        self.events_root = Path(events_root)
        self.events: dict[str, dict[str, Any]] = {}
        self._grid_cache: dict[str, dict[str, dict[str, Any]]] = {}
        for record_path in sorted(self.events_root.glob("*/dossier/event_record.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            event_id = record["event_id"]
            manifest_path = record_path.parents[1] / "artifact_manifest.jsonl"
            manifest: dict[str, dict[str, Any]] = {}
            if manifest_path.exists():
                for line in manifest_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        manifest[Path(row["path"]).name] = row  # latest row wins
            self.events[event_id] = {"record": record, "manifest": manifest}

    def _artifact_id(self, event_id: str, filename: str) -> str | None:
        row = self.events[event_id]["manifest"].get(filename)
        return row["sha256"][:12] if row and row.get("sha256") else None

    def _aoi_boxes(self, record: dict[str, Any]) -> list[dict[str, float]]:
        aoi = record.get("aoi_bbox_wgs84") or record.get("aoi")
        if aoi is None:
            return []
        if "min_lat" in aoi:
            return [aoi]
        return [box for box in aoi.values() if isinstance(box, dict) and "min_lat" in box]

    def locate(self, lat: float, lon: float) -> tuple[str | None, bool]:
        """(event_id, in_aoi) for a point; None when no deep case covers it."""
        for event_id, entry in self.events.items():
            for box in self._aoi_boxes(entry["record"]):
                if (
                    box["min_lat"] <= lat <= box["max_lat"]
                    and box["min_lon"] <= lon <= box["max_lon"]
                ):
                    return event_id, True
        return None, False

    def _grids(self, event_id: str) -> dict[str, dict[str, Any]]:
        """{relative_name: {h3_cell: properties}} for every grid artifact."""
        if event_id in self._grid_cache:
            return self._grid_cache[event_id]
        grids: dict[str, dict[str, Any]] = {}
        event_dir = self.events_root / event_id
        for path in sorted(event_dir.glob("*/*.geojson")):
            if "snapshots" in path.parts:
                continue
            collection = json.loads(path.read_text(encoding="utf-8"))
            index = {}
            for feature in collection.get("features", []):
                cell = feature.get("properties", {}).get("h3_cell")
                if cell:
                    index[cell] = feature["properties"]
            if index:
                grids[path.name] = index
        self._grid_cache[event_id] = grids
        return grids

    def evidence_for(self, lat: float, lon: float) -> EventEvidence:
        event_id, in_aoi = self.locate(lat, lon)
        if event_id is None:
            return EventEvidence(event_id="none", evidence_tier=1, in_aoi=False)

        record = self.events[event_id]["record"]
        evidence = EventEvidence(
            event_id=event_id,
            evidence_tier=int(record.get("evidence_tier", 1)),
            in_aoi=True,
        )
        cell = h3.latlng_to_cell(lat, lon, RESOLUTION)
        for filename, index in self._grids(event_id).items():
            props = index.get(cell)
            if props is None:
                continue
            aid = self._artifact_id(event_id, filename)
            if aid is None:
                continue  # unhashed data never becomes citable evidence
            unc = props.get("uncertainty")
            unc_note = f" | uncertainty: {json.dumps(unc, ensure_ascii=False)}" if unc else ""
            evidence.facts.append(
                Fact(
                    text=f"[{event_id} / {filename} / tile {cell}] "
                    f"{_scalar_items(props)}{unc_note}",
                    artifact_id=aid,
                    source_path=filename,
                )
            )
        record_id = self._artifact_id(event_id, "event_record.json")
        if record_id:
            for unknown in record.get("declared_unknowns", []):
                evidence.facts.append(
                    Fact(
                        text=f"[{event_id} / declared unknown] {unknown}",
                        artifact_id=record_id,
                        source_path="event_record.json",
                    )
                )
        return evidence
