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
_KNOWN_MATCH_KEYS = frozenset(
    {"role", "purpose", "resolution", "in_aoi", "evidence_tier_at_least", "evidence_tier_below"}
)
_KNOWN_EFFECTS = frozenset({"allow", "deny"})


def _matches(match: dict[str, Any], request: PolicyRequest) -> bool:
    for key in _EXACT_KEYS:
        if key in match and getattr(request, key) != match[key]:
            return False
    if "evidence_tier_at_least" in match and request.evidence_tier < match["evidence_tier_at_least"]:
        return False
    if "evidence_tier_below" in match and request.evidence_tier >= match["evidence_tier_below"]:
        return False
    return True


def _validate_rules(rules: Any) -> list[dict[str, Any]]:
    if not isinstance(rules, list):
        raise ValueError("Policy document's 'rules' must be a list of rule mappings.")
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError(f"Policy rule must be a mapping, got: {rule!r}")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"Policy rule is missing a valid string 'id': {rule!r}")
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
            if key not in _KNOWN_MATCH_KEYS:
                raise ValueError(
                    f"Rule '{rule_id}' has unknown match key '{key}'; "
                    f"expected one of {sorted(_KNOWN_MATCH_KEYS)}."
                )
    return rules


class PolicyEngine:
    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = _validate_rules(rules)

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
        return PolicyDecision(
            allowed=False,
            rule_id="default-deny",
            reason="No policy rule authorizes this request; the harness fails closed.",
        )
