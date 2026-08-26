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
    event_ids: list[str] = field(default_factory=list)
    cells: list[str] = field(default_factory=list)

    @property
    def artifact_ids(self) -> set[str]:
        return {f.artifact_id for f in self.facts}


def normalise_bbox(bbox: dict[str, float]) -> dict[str, float]:
    """Swap any inverted min/max pair so the box is geometrically well-formed.

    A rectangle dragged on a map (or typed by hand) can have its corners in
    either order per axis. Left unnormalised, an inverted box slips past
    `boxes_intersect`'s comparisons as a false "overlap" — the wrong answer
    reaches `EventEvidence.in_aoi`, which becomes `PolicyRequest.in_aoi` and
    gates policy rules, and the audit ends up recording the wrong reason for
    a refusal. Called at the entry points, not inside `boxes_intersect`
    itself, so every caller of `locate_area`/`evidence_for_area` is covered
    regardless of how they built the box.
    """
    return {
        "min_lat": min(bbox["min_lat"], bbox["max_lat"]),
        "max_lat": max(bbox["min_lat"], bbox["max_lat"]),
        "min_lon": min(bbox["min_lon"], bbox["max_lon"]),
        "max_lon": max(bbox["min_lon"], bbox["max_lon"]),
    }


def boxes_intersect(a: dict[str, float], b: dict[str, float]) -> bool:
    """Do two WGS84 bounding boxes overlap? Touching edges count.

    A selection dragged flush against an AOI edge is a real selection; treating
    it as a miss would make the boundary behave differently from either side.

    Assumes both boxes are already normalised (min <= max on each axis); it is
    a pure geometric predicate and does not defend against malformed input.
    """
    return (
        a["min_lat"] <= b["max_lat"]
        and b["min_lat"] <= a["max_lat"]
        and a["min_lon"] <= b["max_lon"]
        and b["min_lon"] <= a["max_lon"]
    )


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

    def locate_area(self, bbox: dict[str, float]) -> list[str]:
        """Every event whose AOI meets the rectangle.

        `locate` returns on its first match, which is right for a point — it can
        sit in only one deep case — and wrong for a rectangle, which can span two.
        """
        bbox = normalise_bbox(bbox)
        hits = []
        for event_id, entry in self.events.items():
            boxes = self._aoi_boxes(entry["record"])
            if any(boxes_intersect(bbox, box) for box in boxes):
                hits.append(event_id)
        return sorted(hits)

    def evidence_for_area(self, bbox: dict[str, float]) -> EventEvidence:
        bbox = normalise_bbox(bbox)
        event_ids = self.locate_area(bbox)
        if not event_ids:
            return EventEvidence(event_id="none", evidence_tier=1, in_aoi=False)

        tiers = [
            int(self.events[e]["record"].get("evidence_tier", 1)) for e in event_ids
        ]
        evidence = EventEvidence(
            event_id="+".join(event_ids),
            #: Weakest of the events touched, for the same reason verifiability
            #: takes the weakest link: an answer spanning a Tier 2 case and a
            #: Tier 3 case is not a Tier 3 answer.
            evidence_tier=min(tiers),
            in_aoi=True,
            event_ids=event_ids,
        )

        for event_id in event_ids:
            matched: set[str] = set()
            per_grid: list[str] = []
            for filename, index in self._grids(event_id).items():
                aid = self._artifact_id(event_id, filename)
                if aid is None:
                    continue  # unhashed data never becomes citable evidence
                hits = 0
                for cell, props in index.items():
                    lat, lon = h3.cell_to_latlng(cell)
                    if not point_in_box(lat, lon, bbox):
                        continue
                    hits += 1
                    matched.add(cell)
                    unc = props.get("uncertainty")
                    unc_note = (
                        f" | uncertainty: {json.dumps(unc, ensure_ascii=False)}"
                        if unc
                        else ""
                    )
                    evidence.facts.append(
                        Fact(
                            text=f"[{event_id} / {filename} / tile {cell}] "
                            f"{_scalar_items(props)}{unc_note}",
                            artifact_id=aid,
                            source_path=filename,
                        )
                    )
                if hits:
                    per_grid.append(f"{filename}: {hits}")

            record = self.events[event_id]["record"]
            record_id = self._artifact_id(event_id, "event_record.json")
            if record_id:
                #: Coverage travels with the evidence as a declared unknown, not
                #: as an authorization input. What the selection did NOT cover is
                #: not computed as a fraction: that would need a geometry of
                #: evaluated ground the repository does not have, and inventing
                #: one would be a claim about the world rather than the artifacts.
                evidence.facts.append(
                    Fact(
                        text=(
                            f"[{event_id} / selection coverage] "
                            f"{len(matched)} evaluated tile(s) inside the selection "
                            f"({'; '.join(per_grid) if per_grid else 'no grid matched'}). "
                            "This answer speaks only for those tiles."
                        ),
                        artifact_id=record_id,
                        source_path="event_record.json",
                    )
                )
                for unknown in record.get("declared_unknowns", []):
                    evidence.facts.append(
                        Fact(
                            text=f"[{event_id} / declared unknown] {unknown}",
                            artifact_id=record_id,
                            source_path="event_record.json",
                        )
                    )
            evidence.cells.extend(sorted(matched))

        return evidence


#: Defined at module level, after `EvidenceStore`, rather than beside
#: `boxes_intersect` above -- so adding it here doesn't shift any of the line
#: numbers the manual cites into this file (`declared_unknowns` at line 183).
#: Used by `evidence_for_area`'s per-cell loop above.
def point_in_box(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    """Does (lat, lon) fall inside a WGS84 bounding box? Edges count, the same
    inclusive rule `boxes_intersect` applies to whole boxes: a cell whose
    centre sits exactly on the selection's edge is matched, not excluded.

    Deliberately duplicated in `cellsInBox()` (`app/src/lib/area.js`) rather
    than shared across the Python/JavaScript boundary: the same
    edge-inclusive, centre-in-box predicate, implemented independently on
    both sides as defence in depth, so a bug in one implementation cannot
    silently make the header count the app shows before asking agree with a
    wrong `cells` list after asking. `tests/test_gateway_area.py`'s
    `CrossLayerAgreementTests` feeds both implementations the same shapes and
    asserts identical accept/reject, so that "deliberately duplicated" claim
    has a guard behind it instead of resting on this comment alone.
    """
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )
