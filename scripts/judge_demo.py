#!/usr/bin/env python
"""One end-to-end pass for a reviewer, in about a minute, with no keys and no data download.

    python scripts/judge_demo.py            # writes to a temporary directory, prints what happened
    python scripts/judge_demo.py --out /tmp/judge   # keep the products, snapshots and audit log

Three things happen, each through the Steward Harness, each printed as it happens:

1. **Fetch and build.** The four keyless federal connectors (USGS, NWS, NHC, NIFC/WFIGS)
   and the NOAA/WPC Day-1 outlook are fetched live; every raw response is saved as an
   append-only snapshot; a failing source is recorded in the audit log and declared in
   `watch_status.json`, never fabricated and never allowed to block the others; the
   national watch product is built and its per-source health printed.
2. **Publish only what the policy allows.** The distribution plane classifies every file
   under `events/` — allowed or denied, with the rule id — exactly as the CI gate does
   before a deploy.
3. **Decide what the agent may say.** The claim plane is evaluated on a small matrix of
   requests (role × purpose × resolution × evidence); each decision names the rule. No
   language model is involved: this is the gate that runs *before* any model call.

Nothing here writes into `events/`; the outputs go to `--out`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from geosteward.harness.distribution import DistributionPolicy  # noqa: E402
from geosteward.harness.policy import PolicyEngine, PolicyRequest  # noqa: E402
from geosteward.harness.publication import plan_publication  # noqa: E402
from geosteward.sources import wpc_ero  # noqa: E402
from run_watch import CONNECTORS, run_watch  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
POLICY = REPO / "src" / "geosteward" / "harness" / "policy_v1.yaml"


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}", flush=True)


def step_watch(out: Path, timeout: int) -> None:
    banner("1/3  Fetch the federal feeds and build the national watch product (Steward Harness)")
    t0 = time.time()
    status = run_watch(list(CONNECTORS), out / "live", timeout=timeout, outlook_connector=wpc_ero)
    for name, s in status.get("sources", status).items() if isinstance(status.get("sources"), dict) else status.items():
        if not isinstance(s, dict):
            continue
        state = s.get("status")
        count = s.get("events", s.get("areas", ""))
        extra = f"  skipped={s.get('skipped')}" if s.get("skipped") not in (None, 0) else ""
        err = f"  error: {s.get('error')}" if s.get("error") else ""
        print(f"  {name:<14} {state:<7} {count!s:>6}{extra}{err}", flush=True)
    products = out / "live" / "products"
    audit = out / "live" / "audit_log.jsonl"
    rows = audit.read_text(encoding="utf-8").splitlines() if audit.exists() else []
    snaps = sorted((out / "live" / "snapshots").rglob("*")) if (out / "live" / "snapshots").exists() else []
    print(f"\n  products: {', '.join(p.name for p in sorted(products.glob('*')))}")
    print(f"  snapshots saved: {sum(1 for p in snaps if p.is_file())}   audit rows appended: {len(rows)}   ({time.time() - t0:.1f}s)")
    if rows:
        last = json.loads(rows[-1])
        print(f"  last audit row: {last.get('action')} by {last.get('actor')} at {last.get('utc')}")


def step_publication() -> None:
    banner("2/3  Distribution plane: what under events/ may be published, and why not")
    policy = DistributionPolicy.from_yaml(POLICY)
    plan = plan_publication(REPO / "events", policy, policy.published_events)
    print(f"  published events: {', '.join(policy.published_events)}")
    print(f"  allowed: {len(plan.allowed)} file(s)   denied: {len(plan.denied)} file(s)")
    by_rule: dict[str, int] = {}
    for d in plan.denied:
        by_rule[d.rule_id] = by_rule.get(d.rule_id, 0) + 1
    for rule, n in sorted(by_rule.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>4}  {rule}")
    sample = [a.path for a in plan.allowed if a.path.endswith(".geojson")][:4]
    print("  e.g. allowed: " + "; ".join(sample))


def step_claims() -> None:
    banner("3/3  Claim plane: what each role may be told, before any model call")
    engine = PolicyEngine.from_yaml(POLICY)
    cases = [
        ("resident", "watch", "tile", 1, True),
        ("resident", "exposure", "tile", 2, True),
        ("resident", "damage_assessment", "tile", 3, True),
        ("planner", "damage_assessment", "tile", 3, True),
        ("planner", "damage_assessment", "tile", 2, True),
        ("planner", "damage_assessment", "parcel", 3, True),
        ("planner", "damage_assessment", "tile", 3, False),
        ("planner", "facility_context", "tile", 2, True),
    ]
    print(f"  {'role':<9} {'purpose':<18} {'resolution':<10} {'tier':>4} {'in_aoi':<7} decision  rule")
    for role, purpose, resolution, tier, in_aoi in cases:
        d = engine.evaluate(PolicyRequest(role=role, purpose=purpose, resolution=resolution, evidence_tier=tier, in_aoi=in_aoi))
        verdict = "ALLOW" if d.allowed else "deny "
        print(f"  {role:<9} {purpose:<18} {resolution:<10} {tier:>4} {str(in_aoi):<7} {verdict}     {d.rule_id}")
    print("\n  Every refusal the agent gives names one of these rules; every answer must cite an artifact or is refused.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None, help="where to write snapshots, products and the audit log (default: a temp dir)")
    ap.add_argument("--timeout", type=int, default=30, help="per-source HTTP timeout, seconds")
    ap.add_argument("--skip-fetch", action="store_true", help="skip the live fetch (offline review)")
    args = ap.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="ray-judge-"))
    out.mkdir(parents=True, exist_ok=True)
    print(f"Ray Resilience — reviewer pass. Outputs under: {out}")
    if not args.skip_fetch:
        step_watch(out, args.timeout)
    step_publication()
    step_claims()
    print(f"\nDone. Inspect {out / 'live'} (snapshots/, products/, audit_log.jsonl).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
