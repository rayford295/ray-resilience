# GeoSteward Plan 1: Foundation (Package Rename + Steward Harness Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the Python package to `geosteward`, archive the Bavi case, and build the Steward Harness core (outcome checks, audit + artifact hashing, declarative policy engine) wired into the pipeline.

**Architecture:** The harness is a new `src/geosteward/harness/` package with three units: `checks/outcome.py` (pure functions returning `CheckResult`), `audit.py` (append-only JSONL audit log + SHA-256 artifact hashing), and `policy.py` (ordered first-match rule engine loaded from YAML, default deny). The existing agent/pipeline machinery is kept; `EventContext.write_json` gains artifact hashing and `run_pre_event` gains stage-level audit records.

**Tech Stack:** Python >=3.10, stdlib + PyYAML (the only new dependency), unittest (`python -m unittest discover -s tests`).

**Spec:** `docs/superpowers/specs/2026-08-19-geosteward-design.md` (Plan 1 of 5; later plans: Tier-1 connectors, deep cases, PWA, gateway).

## Global Constraints

- All repository content (code, comments, docs, commits) in **English**.
- `requires-python = ">=3.10"`; base dependencies limited to `pyyaml>=6.0` (geo extras unchanged).
- **Append-only history:** never delete anything under `events/`; archive means `git mv` into `events/archive/`.
- **Fail closed:** missing inputs produce recorded failures, never fabricated outputs.
- Test runner is **unittest**, not pytest: `python -m unittest discover -s tests -v`.
- Package version in this plan: `1.0.0.dev1` (v1.0.0 is tagged when the full v1 design is implemented).
- Working directory: `~/Documents/GeoSteward`. After each task's commit, push to BOTH remotes: `git push origin main && git push orgfork main`.

---

### Task 1: Rename package `disasterpilot` → `geosteward`

**Files:**
- Rename: `src/disasterpilot/` → `src/geosteward/` (git mv, all contents)
- Modify: `pyproject.toml`, `scripts/run_pre_event.py`, `scripts/close_event.py`, `scripts/fetch_bavi_track.py`, `tests/test_pipeline.py`, `tests/test_tracks.py` (import lines only)

**Interfaces:**
- Produces: importable package `geosteward` with unchanged module layout (`geosteward.agents.base`, `geosteward.pipeline`, `geosteward.sources.zj_typhoon`, `geosteward.hazards.typhoon`). All later tasks import from `geosteward.*`.

- [ ] **Step 1: Move the package directory**

```bash
cd ~/Documents/GeoSteward
git mv src/disasterpilot src/geosteward
```

- [ ] **Step 2: Rewrite all imports and module references**

```bash
grep -rl "disasterpilot" src/ tests/ scripts/ | xargs sed -i '' 's/disasterpilot/geosteward/g'
```

- [ ] **Step 3: Update `pyproject.toml` metadata**

Replace the `[project]` name/version/description lines with:

```toml
name = "geosteward"
version = "1.0.0.dev1"
description = "GeoSteward: an accountable GeoAI risk analyst for location-based resilience understanding and decision-making. OASIS @ ACM SIGSPATIAL 2026 Track A."
```

- [ ] **Step 4: Reinstall and run the full test suite**

```bash
python -m pip install -e . --quiet && python -m unittest discover -s tests -v
```

Expected: all existing tests PASS (they use synthetic tmp-dir fixtures, no path breakage). Also verify no stale references: `grep -rn "disasterpilot" src/ tests/ scripts/ pyproject.toml` returns nothing.

- [ ] **Step 5: Commit and push to both remotes**

```bash
git add -A && git commit -m "refactor: rename package disasterpilot -> geosteward (v1.0.0.dev1)"
git push origin main && git push orgfork main
```

---

### Task 2: Archive the Bavi case and retire the capture workflow

**Files:**
- Rename: `events/bavi-2026/` → `events/archive/bavi-2026/` (git mv)
- Delete: `.github/workflows/capture.yml` (Bavi is closed; its 3-hourly cron only burns CI minutes — Plan 2 introduces the new Tier-1 live workflow)
- Modify: `scripts/fetch_bavi_track.py:27` (default output dir), `README.md` (archive note)

**Interfaces:**
- Produces: `events/archive/bavi-2026/` as the permanent archived location; `events/` root is free for `milton-2024/`, `eaton-2025/` (Plan 3) and `live/` (Plan 2).

- [ ] **Step 1: Move the event directory and remove the cron workflow**

```bash
cd ~/Documents/GeoSteward
mkdir -p events/archive
git mv events/bavi-2026 events/archive/bavi-2026
git rm .github/workflows/capture.yml
```

- [ ] **Step 2: Update the archived-case default path in the legacy fetch script**

In `scripts/fetch_bavi_track.py` line 27, change:

```python
    parser.add_argument("--output-dir", type=Path, default=Path("events/archive/bavi-2026/snapshots"))
```

- [ ] **Step 3: Update the README archive note**

In `README.md`, replace the sentence "The previous Super Typhoon Bavi case study is preserved under `events/` and will move to `events/archive/` — append-only history is a core principle here." with:

```markdown
> The previous Super Typhoon Bavi case study is preserved under
> `events/archive/bavi-2026/` — append-only history is a core principle here.
```

- [ ] **Step 4: Run tests and verify no path breakage**

```bash
python -m unittest discover -s tests -v && grep -rn "events/bavi-2026" src/ tests/ scripts/ README.md docs/*.md; true
```

Expected: tests PASS; the grep may still match `docs/architecture.md`/`docs/methodology.md` prose (updated in Plan 3's narrative pass) but must match nothing in `src/`, `tests/`, `scripts/`, `README.md`.

- [ ] **Step 5: Commit and push**

```bash
git add -A && git commit -m "chore: archive Bavi case under events/archive, retire capture cron"
git push origin main && git push orgfork main
```

---

### Task 3: Steward Harness — outcome validity checks

**Files:**
- Create: `src/geosteward/harness/__init__.py`, `src/geosteward/harness/checks/__init__.py`, `src/geosteward/harness/checks/outcome.py`
- Test: `tests/test_harness_checks.py`

**Interfaces:**
- Produces (used by Tasks 6-7 and all later plans):
  - `CheckResult(check: str, passed: bool, detail: str)` frozen dataclass with `.as_row() -> dict`
  - `check_crs(declared: str | None, expected: str = "EPSG:4326") -> CheckResult`
  - `check_join_integrity(left_ids: Iterable[str], joined_ids: Iterable[str], min_coverage: float = 1.0) -> CheckResult`
  - `check_bounds(name: str, value: float, minimum: float, maximum: float) -> CheckResult`
  - `check_uncertainty_present(payload: dict, field: str = "uncertainty") -> CheckResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_harness_checks.py`:

```python
"""Outcome-validity checks: the executable spatial checks of the Steward Harness."""

import unittest

from geosteward.harness.checks.outcome import (
    CheckResult,
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)


class TestCrsCheck(unittest.TestCase):
    def test_matching_crs_passes(self) -> None:
        result = check_crs("EPSG:4326")
        self.assertTrue(result.passed)
        self.assertEqual(result.check, "crs")

    def test_mismatched_crs_fails_with_both_values_in_detail(self) -> None:
        result = check_crs("EPSG:3857", expected="EPSG:4326")
        self.assertFalse(result.passed)
        self.assertIn("EPSG:3857", result.detail)
        self.assertIn("EPSG:4326", result.detail)

    def test_undeclared_crs_fails(self) -> None:
        self.assertFalse(check_crs(None).passed)


class TestJoinIntegrity(unittest.TestCase):
    def test_full_coverage_no_orphans_passes(self) -> None:
        result = check_join_integrity(["a", "b"], ["a", "b"])
        self.assertTrue(result.passed)

    def test_orphan_join_ids_fail(self) -> None:
        result = check_join_integrity(["a"], ["a", "ghost"])
        self.assertFalse(result.passed)
        self.assertIn("ghost", result.detail)

    def test_partial_coverage_below_threshold_fails(self) -> None:
        result = check_join_integrity(["a", "b", "c", "d"], ["a", "b"], min_coverage=0.9)
        self.assertFalse(result.passed)

    def test_partial_coverage_above_threshold_passes(self) -> None:
        result = check_join_integrity(["a", "b", "c", "d"], ["a", "b", "c"], min_coverage=0.7)
        self.assertTrue(result.passed)


class TestBoundsAndUncertainty(unittest.TestCase):
    def test_value_inside_bounds_passes(self) -> None:
        self.assertTrue(check_bounds("wind_kt", 120.0, 0.0, 200.0).passed)

    def test_value_outside_bounds_fails(self) -> None:
        result = check_bounds("wind_kt", 500.0, 0.0, 200.0)
        self.assertFalse(result.passed)
        self.assertIn("wind_kt", result.detail)

    def test_missing_uncertainty_field_fails(self) -> None:
        self.assertFalse(check_uncertainty_present({"value": 1}).passed)

    def test_present_uncertainty_field_passes(self) -> None:
        self.assertTrue(check_uncertainty_present({"value": 1, "uncertainty": 0.2}).passed)

    def test_as_row_is_json_ready(self) -> None:
        row = check_crs("EPSG:4326").as_row()
        self.assertEqual(row, {"check": "crs", "passed": True, "detail": row["detail"]})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_harness_checks -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geosteward.harness'`

- [ ] **Step 3: Implement the checks**

Create `src/geosteward/harness/__init__.py`:

```python
"""Steward Harness: enforces outcome, process, and institutional validity.

The harness is the accountable layer around the agents — executable spatial
checks (outcome), append-only audit with artifact hashing (process), and a
declarative policy engine scoping what may be claimed (institutional).
"""
```

Create `src/geosteward/harness/checks/__init__.py`:

```python
from geosteward.harness.checks.outcome import (
    CheckResult,
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)

__all__ = [
    "CheckResult",
    "check_bounds",
    "check_crs",
    "check_join_integrity",
    "check_uncertainty_present",
]
```

Create `src/geosteward/harness/checks/outcome.py`:

```python
"""Outcome-validity checks: executable assertions on spatial operations.

Every check is a pure function returning a CheckResult; callers decide
whether a failed check aborts the stage (fail closed) or is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CheckResult:
    check: str
    passed: bool
    detail: str

    def as_row(self) -> dict[str, Any]:
        return {"check": self.check, "passed": self.passed, "detail": self.detail}


def check_crs(declared: str | None, expected: str = "EPSG:4326") -> CheckResult:
    if declared is None:
        return CheckResult("crs", False, f"CRS undeclared; expected {expected}")
    if declared != expected:
        return CheckResult("crs", False, f"CRS mismatch: declared {declared}, expected {expected}")
    return CheckResult("crs", True, f"CRS {declared} matches expected")


def check_join_integrity(
    left_ids: Iterable[str],
    joined_ids: Iterable[str],
    min_coverage: float = 1.0,
) -> CheckResult:
    left, joined = set(left_ids), set(joined_ids)
    orphans = sorted(joined - left)
    if orphans:
        return CheckResult("join_integrity", False, f"orphan join ids not in left side: {orphans}")
    coverage = len(joined & left) / len(left) if left else 0.0
    if coverage < min_coverage:
        return CheckResult(
            "join_integrity",
            False,
            f"coverage {coverage:.2%} below required {min_coverage:.2%}",
        )
    return CheckResult("join_integrity", True, f"coverage {coverage:.2%}, no orphans")


def check_bounds(name: str, value: float, minimum: float, maximum: float) -> CheckResult:
    if minimum <= value <= maximum:
        return CheckResult("bounds", True, f"{name}={value} within [{minimum}, {maximum}]")
    return CheckResult("bounds", False, f"{name}={value} outside [{minimum}, {maximum}]")


def check_uncertainty_present(payload: dict, field: str = "uncertainty") -> CheckResult:
    if field in payload:
        return CheckResult("uncertainty", True, f"field '{field}' present")
    return CheckResult("uncertainty", False, f"required field '{field}' missing")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_harness_checks -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/harness tests/test_harness_checks.py
git commit -m "feat: Steward Harness outcome-validity checks (CRS, join integrity, bounds, uncertainty)"
git push origin main && git push orgfork main
```

---

### Task 4: Steward Harness — audit log and artifact hashing

**Files:**
- Create: `src/geosteward/harness/audit.py`
- Modify: `src/geosteward/agents/base.py` (add `sha256` to `Artifact` + compute it in `EventContext.write_json`)
- Test: `tests/test_harness_audit.py`

**Interfaces:**
- Consumes: `Artifact`, `EventContext` from `geosteward.agents.base` (Task 1 layout).
- Produces:
  - `sha256_file(path: Path) -> str` (hex digest)
  - `AuditLog(path: Path)` with `.record(action: str, actor: str, payload: dict | None = None, rule_id: str | None = None) -> dict` — appends one JSONL row `{action, actor, utc, payload, rule_id}` and returns it
  - `Artifact.sha256: str = ""` field, included in `manifest_row()`
  - `EventContext.write_json(...)` now fills `sha256` for every artifact it writes

- [ ] **Step 1: Write the failing tests**

Create `tests/test_harness_audit.py`:

```python
"""Process validity: append-only audit log and artifact hashing."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from geosteward.agents.base import EventContext
from geosteward.harness.audit import AuditLog, sha256_file


class TestSha256File(unittest.TestCase):
    def test_hash_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            path.write_text('{"a": 1}', encoding="utf-8")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(sha256_file(path), expected)


class TestAuditLog(unittest.TestCase):
    def test_record_appends_jsonl_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = AuditLog(Path(tmp) / "audit_log.jsonl")
            log.record("stage", "watcher.test", payload={"status": "ok"})
            log.record("refusal", "gateway", rule_id="deny-outside-aoi")
            rows = [json.loads(line) for line in log.path.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["action"], "stage")
            self.assertEqual(rows[0]["payload"], {"status": "ok"})
            self.assertEqual(rows[1]["rule_id"], "deny-outside-aoi")
            self.assertTrue(rows[0]["utc"].endswith("Z"))


class TestManifestHashing(unittest.TestCase):
    def test_write_json_records_sha256_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = EventContext(
                event_id="teststorm-2026",
                event_dir=Path(tmp) / "teststorm-2026",
                hazard="hurricane",
            )
            artifact = context.write_json(
                "dossier/record.json", {"a": 1}, kind="dossier", agent="dossier.test"
            )
            self.assertEqual(artifact.sha256, sha256_file(artifact.path))
            manifest = context.event_dir / "artifact_manifest.jsonl"
            row = json.loads(manifest.read_text().splitlines()[-1])
            self.assertEqual(row["sha256"], artifact.sha256)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_harness_audit -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geosteward.harness.audit'`

- [ ] **Step 3: Implement audit module and wire hashing into base.py**

Create `src/geosteward/harness/audit.py`:

```python
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
```

In `src/geosteward/agents/base.py`, make two edits.

Edit 1 — add the `sha256` field to `Artifact` (after `notes: str = ""`) and include it in `manifest_row`:

```python
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
```

Edit 2 — in `EventContext.write_json`, compute the hash when registering (replace the final `return self.register(...)` block):

```python
        from geosteward.harness.audit import sha256_file

        return self.register(
            Artifact(
                path=path,
                kind=kind,
                agent=agent,
                created_utc=utc_stamp(),
                inputs=inputs or [],
                notes=notes,
                sha256=sha256_file(path),
            )
        )
```

(The import lives inside the method to avoid a circular import: `harness.audit` has no dependency on `agents.base`, but keeping `base.py` import-light preserves the existing zero-dependency import graph at module load.)

- [ ] **Step 4: Run the full suite (existing pipeline tests must still pass)**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — including all pre-existing tests (manifest rows gain a `sha256` key; no existing assertion checks exact row shape).

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/harness/audit.py src/geosteward/agents/base.py tests/test_harness_audit.py
git commit -m "feat: audit log and SHA-256 artifact hashing in the manifest"
git push origin main && git push orgfork main
```

---

### Task 5: Steward Harness — declarative policy engine

**Files:**
- Create: `src/geosteward/harness/policy.py`
- Modify: `pyproject.toml` (add `pyyaml>=6.0` to `dependencies`)
- Test: `tests/test_harness_policy.py`

**Interfaces:**
- Produces (used by Task 6 and the Plan-5 gateway):
  - `PolicyRequest(role: str, purpose: str, resolution: str, evidence_tier: int, in_aoi: bool)` frozen dataclass
  - `PolicyDecision(allowed: bool, rule_id: str, reason: str)` frozen dataclass
  - `PolicyEngine(rules: list[dict])` with `evaluate(request) -> PolicyDecision` (ordered, first matching rule wins, default deny with `rule_id="default-deny"`) and `PolicyEngine.from_yaml(path: Path) -> PolicyEngine`
  - Rule match keys: `role`, `purpose`, `resolution`, `in_aoi` (exact match) plus `evidence_tier_at_least`, `evidence_tier_below` (numeric comparisons)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_harness_policy.py`:

```python
"""Institutional validity: the declarative policy engine (first match wins, default deny)."""

import tempfile
import unittest
from pathlib import Path

from geosteward.harness.policy import PolicyEngine, PolicyRequest

RULES = [
    {
        "id": "deny-outside-aoi",
        "effect": "deny",
        "reason": "Damage assessment outside the event AOI is not authorized.",
        "match": {"purpose": "damage_assessment", "in_aoi": False},
    },
    {
        "id": "deny-parcel-below-tier3",
        "effect": "deny",
        "reason": "Parcel-level claims require Tier 3 evidence.",
        "match": {"resolution": "parcel", "evidence_tier_below": 3},
    },
    {
        "id": "allow-watch-anywhere",
        "effect": "allow",
        "reason": "Monitoring information is public at any location.",
        "match": {"purpose": "watch"},
    },
    {
        "id": "allow-tile-tier2",
        "effect": "allow",
        "reason": "Tile-level analysis supported by Tier 2 evidence.",
        "match": {"resolution": "tile", "evidence_tier_at_least": 2, "in_aoi": True},
    },
]


def request(**overrides) -> PolicyRequest:
    base = {
        "role": "planner",
        "purpose": "damage_assessment",
        "resolution": "tile",
        "evidence_tier": 2,
        "in_aoi": True,
    }
    base.update(overrides)
    return PolicyRequest(**base)


class TestPolicyEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine(RULES)

    def test_first_matching_rule_wins(self) -> None:
        decision = self.engine.evaluate(request(in_aoi=False))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "deny-outside-aoi")

    def test_parcel_claims_denied_below_tier3(self) -> None:
        decision = self.engine.evaluate(request(resolution="parcel", evidence_tier=2))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "deny-parcel-below-tier3")

    def test_parcel_claims_allowed_at_tier3_fall_through_to_default_deny(self) -> None:
        # Tier 3 parcel is not matched by the deny rule, and no allow rule
        # covers it in this fixture -> default deny proves fail-closed posture.
        decision = self.engine.evaluate(request(resolution="parcel", evidence_tier=3))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "default-deny")

    def test_watch_purpose_allowed_anywhere(self) -> None:
        decision = self.engine.evaluate(request(purpose="watch", in_aoi=False))
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-watch-anywhere")

    def test_tile_tier2_in_aoi_allowed(self) -> None:
        decision = self.engine.evaluate(request())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-tile-tier2")

    def test_unmatched_request_default_denied_with_reason(self) -> None:
        decision = self.engine.evaluate(request(evidence_tier=1))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "default-deny")
        self.assertTrue(decision.reason)


class TestYamlLoading(unittest.TestCase):
    def test_from_yaml_round_trip(self) -> None:
        yaml_text = (
            "rules:\n"
            "  - id: allow-watch-anywhere\n"
            "    effect: allow\n"
            "    reason: Monitoring information is public at any location.\n"
            "    match:\n"
            "      purpose: watch\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.yaml"
            path.write_text(yaml_text, encoding="utf-8")
            engine = PolicyEngine.from_yaml(path)
            decision = engine.evaluate(request(purpose="watch"))
            self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_harness_policy -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geosteward.harness.policy'`

- [ ] **Step 3: Implement the policy engine and add the PyYAML dependency**

In `pyproject.toml`, change `dependencies = []` to:

```toml
dependencies = ["pyyaml>=6.0"]
```

Create `src/geosteward/harness/policy.py`:

```python
"""Institutional validity: a declarative policy engine.

Policies are ordered rules loaded from YAML. Evaluation is first match wins;
anything unmatched is denied ('default-deny'). Duties like authorization and
candor become computable constraints: the engine returns WHICH rule decided
and WHY, so refusals are as traceable as approvals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PolicyRequest:
    role: str
    purpose: str
    resolution: str
    evidence_tier: int
    in_aoi: bool


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    rule_id: str
    reason: str


_EXACT_KEYS = ("role", "purpose", "resolution", "in_aoi")


def _matches(match: dict[str, Any], request: PolicyRequest) -> bool:
    for key in _EXACT_KEYS:
        if key in match and getattr(request, key) != match[key]:
            return False
    if "evidence_tier_at_least" in match and request.evidence_tier < match["evidence_tier_at_least"]:
        return False
    if "evidence_tier_below" in match and request.evidence_tier >= match["evidence_tier_below"]:
        return False
    return True


class PolicyEngine:
    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: Path) -> "PolicyEngine":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(payload["rules"])

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        for rule in self.rules:
            if _matches(rule.get("match", {}), request):
                return PolicyDecision(
                    allowed=rule["effect"] == "allow",
                    rule_id=rule["id"],
                    reason=rule["reason"],
                )
        return PolicyDecision(
            allowed=False,
            rule_id="default-deny",
            reason="No policy rule authorizes this request; the harness fails closed.",
        )
```

- [ ] **Step 4: Reinstall (new dependency) and run the full suite**

```bash
python -m pip install -e . --quiet && python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/harness/policy.py tests/test_harness_policy.py pyproject.toml
git commit -m "feat: declarative policy engine (ordered rules, default deny)"
git push origin main && git push orgfork main
```

---

### Task 6: Default v1 policy file + policy matrix test

**Files:**
- Create: `src/geosteward/harness/policy_v1.yaml`
- Modify: `pyproject.toml` (package data so the YAML ships with the package)
- Test: `tests/test_policy_v1_matrix.py`

**Interfaces:**
- Consumes: `PolicyEngine.from_yaml`, `PolicyRequest` (Task 5).
- Produces: `src/geosteward/harness/policy_v1.yaml` — THE canonical GeoSteward v1 policy, quotable verbatim in the paper. Roles: `resident`, `planner`. Purposes: `watch`, `exposure`, `damage_assessment`. Resolutions: `tile`, `parcel`. Tiers: 1-3.

- [ ] **Step 1: Write the policy file**

Create `src/geosteward/harness/policy_v1.yaml`:

```yaml
# GeoSteward v1 policy — institutional validity as computable constraints.
# Ordered rules; first match wins; anything unmatched is denied.
rules:
  # --- hard denials (checked first) ---
  - id: deny-outside-aoi
    effect: deny
    reason: Damage assessment outside the event AOI is not authorized.
    match: {purpose: damage_assessment, in_aoi: false}

  - id: deny-parcel-any-role
    effect: deny
    reason: Parcel-level claims are not authorized in v1; evidence supports tile level at best.
    match: {resolution: parcel}

  - id: deny-resident-damage-assessment
    effect: deny
    reason: Residents receive exposure context and guidance, not raw damage assessments.
    match: {role: resident, purpose: damage_assessment}

  # --- authorizations ---
  - id: allow-watch-anywhere
    effect: allow
    reason: Monitoring information is public at any location and any tier.
    match: {purpose: watch}

  - id: allow-exposure-in-aoi
    effect: allow
    reason: Tile-level exposure analysis is authorized inside a deep-case AOI (Tier 2+).
    match: {purpose: exposure, resolution: tile, in_aoi: true, evidence_tier_at_least: 2}

  - id: allow-planner-damage-tier3
    effect: allow
    reason: Planners may see tile-level damage assessment where Tier 3 cross-view evidence exists.
    match: {role: planner, purpose: damage_assessment, resolution: tile, in_aoi: true, evidence_tier_at_least: 3}
```

- [ ] **Step 2: Write the failing matrix test**

Create `tests/test_policy_v1_matrix.py`:

```python
"""The v1 policy matrix, verified cell by cell (role x purpose x tier x resolution)."""

import unittest
from pathlib import Path

from geosteward.harness.policy import PolicyEngine, PolicyRequest

POLICY = Path(__file__).resolve().parents[1] / "src" / "geosteward" / "harness" / "policy_v1.yaml"

# (role, purpose, resolution, tier, in_aoi) -> (allowed, rule_id)
MATRIX = [
    (("resident", "watch", "tile", 1, False), (True, "allow-watch-anywhere")),
    (("planner", "watch", "tile", 1, True), (True, "allow-watch-anywhere")),
    (("resident", "exposure", "tile", 2, True), (True, "allow-exposure-in-aoi")),
    (("planner", "exposure", "tile", 2, True), (True, "allow-exposure-in-aoi")),
    (("planner", "exposure", "tile", 1, True), (False, "default-deny")),
    (("planner", "damage_assessment", "tile", 3, True), (True, "allow-planner-damage-tier3")),
    (("planner", "damage_assessment", "tile", 2, True), (False, "default-deny")),
    (("planner", "damage_assessment", "tile", 3, False), (False, "deny-outside-aoi")),
    (("resident", "damage_assessment", "tile", 3, True), (False, "deny-resident-damage-assessment")),
    (("planner", "damage_assessment", "parcel", 3, True), (False, "deny-parcel-any-role")),
    (("resident", "exposure", "parcel", 3, True), (False, "deny-parcel-any-role")),
]


class TestPolicyV1Matrix(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.from_yaml(POLICY)

    def test_matrix(self) -> None:
        for (role, purpose, resolution, tier, in_aoi), (allowed, rule_id) in MATRIX:
            with self.subTest(role=role, purpose=purpose, resolution=resolution, tier=tier, in_aoi=in_aoi):
                decision = self.engine.evaluate(
                    PolicyRequest(
                        role=role,
                        purpose=purpose,
                        resolution=resolution,
                        evidence_tier=tier,
                        in_aoi=in_aoi,
                    )
                )
                self.assertEqual(decision.allowed, allowed)
                self.assertEqual(decision.rule_id, rule_id)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the matrix test**

Run: `python -m unittest tests.test_policy_v1_matrix -v`
Expected: PASS (the policy file and engine both exist by now; if any cell fails, fix the YAML rule order — denials before authorizations).

- [ ] **Step 4: Ship the YAML with the package**

In `pyproject.toml`, add after the `[tool.setuptools.packages.find]` table:

```toml
[tool.setuptools.package-data]
geosteward = ["harness/*.yaml"]
```

Then verify: `python -m pip install -e . --quiet && python -m unittest discover -s tests -v` — PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/harness/policy_v1.yaml tests/test_policy_v1_matrix.py pyproject.toml
git commit -m "feat: canonical v1 policy file with cell-by-cell matrix test"
git push origin main && git push orgfork main
```

---

### Task 7: Wire the harness into the pipeline (stage audit records)

**Files:**
- Modify: `src/geosteward/pipeline.py` (`run_pre_event` records every stage in the event audit log)
- Test: `tests/test_pipeline_audit.py`

**Interfaces:**
- Consumes: `AuditLog` (Task 4), existing `run_pre_event(event_id, tfid, events_root, skip_watcher)`.
- Produces: every `run_pre_event` call writes `events/<event_id>/audit_log.jsonl` with one `action="stage"` row per attempted stage (`payload={"status": ...}`), including failed stages — refusal/failure is as traceable as success.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_audit.py`:

```python
"""Every pipeline stage — including failures — leaves an audit row."""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.pipeline import run_pre_event


class TestPipelineAudit(unittest.TestCase):
    def test_failed_offline_run_still_writes_stage_audit_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_root = Path(tmp)
            report = run_pre_event(
                event_id="teststorm-2026",
                tfid="000000",
                events_root=events_root,
                skip_watcher=True,
            )
            audit_path = events_root / "teststorm-2026" / "audit_log.jsonl"
            self.assertTrue(audit_path.exists())
            rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
            self.assertEqual(len(rows), len(report["stages"]))
            self.assertTrue(all(row["action"] == "stage" for row in rows))
            statuses = [row["payload"]["status"] for row in rows]
            self.assertTrue(any(status.startswith("failed") for status in statuses))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pipeline_audit -v`
Expected: FAIL — `audit_log.jsonl` does not exist yet (`AssertionError: False is not true`).

- [ ] **Step 3: Wire the audit log into `run_pre_event`**

In `src/geosteward/pipeline.py`, add the import at the top with the other imports:

```python
from geosteward.harness.audit import AuditLog
```

Inside `run_pre_event`, after `report` is initialized, create the log:

```python
    audit = AuditLog(context.event_dir / "audit_log.jsonl")
```

Then add one audit line after each of the three places a stage entry is appended to `report["stages"]` (skipped, ok, failed). Each `report["stages"].append({...})` is followed by:

```python
        audit.record("stage", agent.name, payload=report["stages"][-1])
```

(For the skipped-watcher branch, `agent.name` is available because `agent = agent_cls()` runs before the skip check.)

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — new test green, existing offline e2e tests unaffected (they may now also produce `audit_log.jsonl`; no existing assertion forbids extra files).

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/pipeline.py tests/test_pipeline_audit.py
git commit -m "feat: pipeline stages write append-only audit records via the harness"
git push origin main && git push orgfork main
```

---

## Completion Criteria

- `grep -rn "disasterpilot" src/ tests/ scripts/ pyproject.toml` → no matches.
- `python -m unittest discover -s tests -v` → all green (existing + ~20 new harness tests).
- `events/archive/bavi-2026/` exists with full history; `.github/workflows/capture.yml` gone.
- Both remotes (`origin`, `orgfork`) at the same head.
- Next: Plan 2 (Tier-1 US hazard connectors + live publishing).
