"""Pipeline orchestrator: run the agent sequence for one event.

The pre-event pipeline is watcher -> dossier -> exposure -> decision.
The evidence agent joins post-event (it fails closed without imagery).
Agents that cannot run report why; the pipeline never fabricates a stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geosteward.agents.base import EventContext
from geosteward.harness.audit import AuditLog
from geosteward.agents.decision import WatchBulletin
from geosteward.agents.dossier import TyphoonDossier
from geosteward.agents.exposure import TyphoonExposure
from geosteward.agents.watcher import TyphoonWatcher

PRE_EVENT_AGENTS = (TyphoonWatcher, TyphoonDossier, TyphoonExposure, WatchBulletin)


def run_pre_event(
    event_id: str,
    tfid: str,
    events_root: Path = Path("events"),
    skip_watcher: bool = False,
) -> dict[str, Any]:
    context = EventContext(
        event_id=event_id,
        event_dir=events_root / event_id,
        hazard="typhoon",
        metadata={"tfid": tfid},
    )
    report: dict[str, Any] = {"event_id": event_id, "stages": []}
    audit = AuditLog(context.event_dir / "audit_log.jsonl")
    for agent_cls in PRE_EVENT_AGENTS:
        agent = agent_cls()
        if skip_watcher and isinstance(agent, TyphoonWatcher):
            report["stages"].append({"agent": agent.name, "status": "skipped (offline mode)"})
            audit.record("stage", agent.name, payload=report["stages"][-1])
            continue
        try:
            artifacts = agent.run(context)
            report["stages"].append(
                {
                    "agent": agent.name,
                    "status": "ok",
                    "artifacts": [a.path.as_posix() for a in artifacts],
                }
            )
            audit.record("stage", agent.name, payload=report["stages"][-1])
        except Exception as error:  # noqa: BLE001 - surfaced, not swallowed
            report["stages"].append({"agent": agent.name, "status": f"failed: {error}"})
            audit.record("stage", agent.name, payload=report["stages"][-1])
            break
    return report
