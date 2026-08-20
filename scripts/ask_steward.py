"""Ask the Steward a question against the committed deep cases.

Runs the full gateway chain locally (policy pre-check -> evidence -> LLM ->
claim post-check -> audit). The LLM endpoint comes from STEWARD_LLM_* env
vars (default: local Ollama, gpt-oss:20b).

Usage:
  python scripts/ask_steward.py --role planner --lat 34.19 --lon -118.10 \
      --question "How severe is the damage in this area?"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.gateway.steward import Steward
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import PolicyEngine

POLICY = Path(__file__).resolve().parents[1] / "src" / "geosteward" / "harness" / "policy_v1.yaml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["resident", "planner"], required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--audit", type=Path, default=Path("events") / "gateway_audit.jsonl")
    args = ap.parse_args()

    steward = Steward(
        events_root=args.events_root,
        policy=PolicyEngine.from_yaml(POLICY),
        audit=AuditLog(args.audit),
    )
    result = steward.answer(args.role, args.lat, args.lon, args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
