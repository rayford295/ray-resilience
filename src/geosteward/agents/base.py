"""Agent contract: every stage consumes/produces auditable artifacts.

An artifact is a file on disk plus provenance (which agent, when, from what
inputs). Agents never overwrite each other's artifacts; a rerun writes a new
timestamped version. This keeps the pipeline honest: pre-event products stay
frozen for post-event validation.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class Artifact:
    """One auditable output of an agent."""

    path: Path
    kind: str
    agent: str
    created_utc: str
    inputs: list[str] = field(default_factory=list)
    notes: str = ""
    sha256: str = ""

    def manifest_row(self) -> dict[str, Any]:
        return {
            "path": self.path.as_posix(),
            "kind": self.kind,
            "agent": self.agent,
            "created_utc": self.created_utc,
            "inputs": self.inputs,
            "notes": self.notes,
            "sha256": self.sha256,
        }


@dataclass
class EventContext:
    """Shared state for one disaster event."""

    event_id: str
    event_dir: Path
    hazard: str
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)

    def register(self, artifact: Artifact) -> Artifact:
        if not artifact.sha256 and artifact.path.exists():
            from geosteward.harness.audit import sha256_file

            artifact = replace(artifact, sha256=sha256_file(artifact.path))
        self.artifacts.append(artifact)
        manifest = self.event_dir / "artifact_manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(artifact.manifest_row(), ensure_ascii=False) + "\n")
        return artifact

    def write_json(
        self,
        relative_path: str,
        payload: Any,
        kind: str,
        agent: str,
        inputs: list[str] | None = None,
        notes: str = "",
    ) -> Artifact:
        path = self.event_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        return self.register(
            Artifact(
                path=path,
                kind=kind,
                agent=agent,
                created_utc=utc_stamp(),
                inputs=inputs or [],
                notes=notes,
            )
        )


class Agent(Protocol):
    """A pipeline stage. `run` reads the context, writes artifacts, returns them."""

    name: str

    def run(self, context: EventContext) -> list[Artifact]: ...
