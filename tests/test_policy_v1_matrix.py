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
    # Spec 2026-08-25 area-query design, section 3.1's load-bearing claim: an
    # area-shaped request needs no new policy rule. `PolicyRequest` gains no
    # `area` field -- `in_aoi` just widens from "contains the point" to
    # "intersects the rectangle" before it ever reaches this engine (that
    # widening happens in `EvidenceStore.evidence_for_area`, not here) -- so
    # these two rows are mechanically identical to the point rows for the
    # same (role, purpose, resolution, tier, in_aoi) above. That identity is
    # exactly what is being pinned: if `PolicyRequest` or `policy_v1.yaml`
    # ever grew an area-specific field or rule, one of these two would be the
    # first thing to start disagreeing with its point-shaped twin.
    (("planner", "damage_assessment", "tile", 3, True), (True, "allow-planner-damage-tier3")),  # area request, in an AOI
    (("planner", "damage_assessment", "tile", 3, False), (False, "deny-outside-aoi")),  # area request, outside every AOI
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
