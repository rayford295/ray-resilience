"""Process validity: append-only audit log and artifact hashing.

Every consequential action — a pipeline stage, a policy refusal, a human
trade-off adjustment — is one immutable JSONL row. Artifact hashes let the
frontend verify that what it fetched is what the manifest promised.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class AuditLog:
    path: Path

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
            "payload": payload or {},
            "rule_id": rule_id,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
