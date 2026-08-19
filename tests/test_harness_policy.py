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
