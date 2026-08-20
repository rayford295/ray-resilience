"""Process validity: append-only audit log and artifact hashing.

Every consequential action — a pipeline stage, a policy refusal, a human
trade-off adjustment — is one immutable JSONL row. Artifact hashes let the
frontend verify that what it fetched is what the manifest promised.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class AuditLog:
    """Append-only log for one run.

    A stage can be rejected, fixed, and re-run, and both attempts belong in the
    log — erasing the rejected one would erase the evidence that the harness
    worked. But a reader then has to tell the attempts apart, and second-
    resolution timestamps cannot always do it: one run may straddle a second
    boundary while two runs may share one. So each log stamps a `run_id` on
    every row it writes.

    Logs written before this existed are not rewritten; the frontend recovers
    their runs from the check sequence instead.
    """

    path: Path
    run_id: str = field(default_factory=new_run_id)

    def record(
        self,
        action: str,
        actor: str,
        payload: dict[str, Any] | None = None,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "action": action,
            "actor": actor,
            "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "run_id": self.run_id,
            "payload": payload or {},
            "rule_id": rule_id,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
