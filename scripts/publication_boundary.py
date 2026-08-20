"""Enforce the distribution plane at the two places it can be enforced.

Usage:
    python scripts/publication_boundary.py plan [--check]
    python scripts/publication_boundary.py verify <site_dir>

`plan` asks the distribution policy about every file under `events/` and writes
`app/public/publication_allowlist.json`, which the PWA build copies from. With
`--check` it writes nothing and exits non-zero if the committed allowlist has
drifted from the policy — that is what stops a hand-edited allowlist from
widening the public surface behind the policy's back.

`verify` is the gate that actually matters, because it inspects the artifact
about to be deployed rather than the intent that produced it. Run it on the
assembled site directory; a non-zero exit must fail the deploy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from geosteward.harness.audit import AuditLog
from geosteward.harness.distribution import DistributionPolicy
from geosteward.harness.publication import plan_publication, verify_site, write_allowlist

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = REPO_ROOT / "src" / "geosteward" / "harness" / "policy_v1.yaml"
EVENTS = REPO_ROOT / "events"
ALLOWLIST = REPO_ROOT / "app" / "public" / "publication_allowlist.json"
AUDIT = EVENTS / "publication_audit.jsonl"


def command_plan(check: bool) -> int:
    policy = DistributionPolicy.from_yaml(POLICY)
    plan = plan_publication(EVENTS, policy)
    rendered = plan.to_json() + "\n"

    print(f"allowed: {len(plan.allowed)} file(s)")
    for denied in plan.denied:
        print(f"  DENY  {denied.path}  [{denied.rule_id}]")

    if check:
        if not ALLOWLIST.exists():
            print(f"\nFAIL: {ALLOWLIST.relative_to(REPO_ROOT)} is missing.", file=sys.stderr)
            return 1
        if ALLOWLIST.read_text(encoding="utf-8") != rendered:
            print(
                f"\nFAIL: {ALLOWLIST.relative_to(REPO_ROOT)} differs from the policy. "
                "Run `python scripts/publication_boundary.py plan` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("\nallowlist matches the distribution policy")
        return 0

    write_allowlist(plan, ALLOWLIST)
    AuditLog(AUDIT).record(
        "publication_plan",
        "harness.distribution",
        payload={
            "n_allowed": len(plan.allowed),
            "n_denied": len(plan.denied),
            "denied": [{"path": d.path, "rule_id": d.rule_id} for d in plan.denied],
        },
    )
    print(f"\nwrote {ALLOWLIST.relative_to(REPO_ROOT)}")
    return 0


def command_verify(site_dir: Path) -> int:
    if not ALLOWLIST.exists():
        print(f"FAIL: {ALLOWLIST.relative_to(REPO_ROOT)} is missing; run `plan`.", file=sys.stderr)
        return 1
    allowlist = [
        entry["path"]
        for entry in json.loads(ALLOWLIST.read_text(encoding="utf-8"))["allowed"]
    ]
    violations = verify_site(site_dir, allowlist)
    if not violations:
        print(f"publication boundary holds for {site_dir} ({len(allowlist)} authorised file(s))")
        return 0
    print(f"FAIL: {len(violations)} publication-boundary violation(s):", file=sys.stderr)
    for violation in violations:
        print(f"  [{violation.kind}] {violation.detail}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="regenerate the publication allowlist")
    plan.add_argument(
        "--check",
        action="store_true",
        help="verify the committed allowlist matches the policy instead of rewriting it",
    )

    verify = sub.add_parser("verify", help="check an assembled site tree against the allowlist")
    verify.add_argument("site_dir", type=Path)

    args = parser.parse_args(argv)
    if args.command == "plan":
        return command_plan(check=args.check)
    return command_verify(args.site_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
