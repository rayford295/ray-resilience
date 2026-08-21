"""Institutional validity: a declarative policy engine.

Policies are ordered rules loaded from YAML. Evaluation is first match wins;
anything unmatched is denied ('default-deny'). Duties like authorization and
candor become computable constraints: the engine returns WHICH rule decided
and WHY, so refusals are as traceable as approvals.

This module owns the *claim* plane: what the agent may assert. The parallel
*distribution* plane — what a build may publish — lives in `distribution.py`
and reuses `PolicyDecision` and `validate_rules` from here, so both planes
share one grammar and one fail-closed default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


#: The `verifiability` axis, weakest first — so a list index IS the strength
#: rank and comparisons are ordinary integer comparisons.
#:
#: This axis is orthogonal to the tier ladder. Tier encodes freshness and depth
#: of evidence; verifiability encodes *what a reader can do to check it*: open a
#: hashed copy in this repository (`retained`), re-issue the request with their
#: own key and compare digests (`re-derivable`), or check only that the cited
#: references exist (`cited-only`). Third-party content does not fail on tier —
#: a live facility lookup can be perfectly current and still be uncheckable by
#: a reader without a key. Folding the two axes together would erase that.
VERIFIABILITY_ORDER = ("cited-only", "re-derivable", "retained")

RETAINED, RE_DERIVABLE, CITED_ONLY = "retained", "re-derivable", "cited-only"


def verifiability_rank(value: str) -> int:
    """Strength rank; raises on an unknown value rather than guessing one."""
    try:
        return VERIFIABILITY_ORDER.index(value)
    except ValueError:
        raise ValueError(
            f"Unknown verifiability {value!r}; expected one of {list(VERIFIABILITY_ORDER)}."
        ) from None


def weakest(values: Any) -> str:
    """The weakest-link verifiability over several supporting sources.

    A claim is no more verifiable than its weakest support, so an answer drawing
    on both a hashed grid and a live lookup is `re-derivable` — not `retained`
    because most of it happens to be. Taking the maximum here, or averaging,
    would let strong evidence launder weak evidence into the same standing.
    """
    ranked = [(verifiability_rank(v), v) for v in values]
    if not ranked:
        # No supporting source is not "perfectly verifiable"; it is the floor.
        return CITED_ONLY
    return min(ranked)[1]


@dataclass(frozen=True)
class PolicyRequest:
    role: str
    purpose: str
    resolution: str
    evidence_tier: int
    in_aoi: bool
    #: Defaults to `retained`: every product built before this axis existed has
    #: a hashed copy in the repository, so the default states a fact rather than
    #: waving the field through.
    verifiability: str = RETAINED


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    rule_id: str
    reason: str


_EXACT_KEYS = ("role", "purpose", "resolution", "in_aoi", "verifiability")
_KNOWN_MATCH_KEYS = frozenset(
    {
        "role",
        "purpose",
        "resolution",
        "in_aoi",
        "evidence_tier_at_least",
        "evidence_tier_below",
        "verifiability",
        "verifiability_below",
    }
)
#: Match keys whose value names a point on the verifiability order. Checked at
#: construction time: a typo here would silently widen a rule, which is the
#: failure mode `validate_rules` exists to prevent.
_VERIFIABILITY_VALUE_KEYS = ("verifiability", "verifiability_below")
_KNOWN_EFFECTS = frozenset({"allow", "deny"})


def _matches(match: dict[str, Any], request: PolicyRequest) -> bool:
    for key in _EXACT_KEYS:
        if key in match and getattr(request, key) != match[key]:
            return False
    if "evidence_tier_at_least" in match and request.evidence_tier < match["evidence_tier_at_least"]:
        return False
    if "evidence_tier_below" in match and request.evidence_tier >= match["evidence_tier_below"]:
        return False
    if "verifiability_below" in match and verifiability_rank(
        request.verifiability
    ) >= verifiability_rank(match["verifiability_below"]):
        return False
    return True


def validate_rules(
    rules: Any,
    known_match_keys: frozenset[str],
    section: str = "rules",
) -> list[dict[str, Any]]:
    """Shape-check an ordered rule list; shared by every policy plane.

    Typos are the realistic failure mode for a hand-edited YAML policy, and a
    misspelled match key would silently widen a rule instead of narrowing it.
    So unknown keys raise here rather than being ignored at evaluation time.
    """
    if not isinstance(rules, list):
        raise ValueError(f"Policy document's '{section}' must be a list of rule mappings.")
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError(f"Policy rule in '{section}' must be a mapping, got: {rule!r}")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"Policy rule in '{section}' is missing a valid string 'id': {rule!r}")
        effect = rule.get("effect")
        if effect not in _KNOWN_EFFECTS:
            raise ValueError(
                f"Rule '{rule_id}' has unknown effect {effect!r}; "
                f"expected one of {sorted(_KNOWN_EFFECTS)}."
            )
        reason = rule.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"Rule '{rule_id}' is missing a valid string 'reason'.")
        match = rule.get("match", {})
        if not isinstance(match, dict):
            raise ValueError(f"Rule '{rule_id}' has a 'match' that is not a mapping: {match!r}")
        for key in match:
            if key not in known_match_keys:
                raise ValueError(
                    f"Rule '{rule_id}' has unknown match key '{key}'; "
                    f"expected one of {sorted(known_match_keys)}."
                )
    return rules


def default_deny(reason: str, rule_id: str = "default-deny") -> PolicyDecision:
    """The decision every plane falls back to when no rule matches."""
    return PolicyDecision(allowed=False, rule_id=rule_id, reason=reason)


def _validate_verifiability_values(rules: list[dict[str, Any]]) -> None:
    """Reject an unknown point on the verifiability order at load time.

    `validate_rules` checks that match *keys* are known; it says nothing about
    values, because most values are free-form strings. Verifiability is not:
    it is a closed, ordered set, and a rule matching `verifiability: retianed`
    would match nothing and therefore never deny anything.
    """
    for rule in rules:
        match = rule.get("match", {})
        for key in _VERIFIABILITY_VALUE_KEYS:
            if key in match:
                try:
                    verifiability_rank(match[key])
                except ValueError as error:
                    raise ValueError(f"Rule '{rule['id']}' {error}") from None


class PolicyEngine:
    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = validate_rules(rules, _KNOWN_MATCH_KEYS)
        _validate_verifiability_values(self.rules)

    @classmethod
    def from_yaml(cls, path: Path) -> "PolicyEngine":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            raise ValueError(
                f"Policy file {path} must be a mapping containing a 'rules' list."
            )
        return cls(payload["rules"])

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        for rule in self.rules:
            if _matches(rule.get("match", {}), request):
                return PolicyDecision(
                    allowed=rule["effect"] == "allow",
                    rule_id=rule["id"],
                    reason=rule["reason"],
                )
        return default_deny(
            "No policy rule authorizes this request; the harness fails closed."
        )
