"""Distribution validity: which artifacts the project is authorized to publish.

The claim plane (`policy.rules`) governs what the agent may *say*. This plane
governs what a build may *serve*. Both fail closed: an artifact kind nobody
has classified cannot be published, so adding a new product to `events/`
cannot silently widen the public surface.
"""

import tempfile
import unittest
from pathlib import Path

from geosteward.harness.distribution import ArtifactRef, DistributionPolicy

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_V1 = REPO_ROOT / "src" / "geosteward" / "harness" / "policy_v1.yaml"

CLASSES = {
    "damage_points_restricted": {
        "resolution_cap": "parcel", "audience": "lineage", "license": "public-domain-source",
    },
    "damage_grid": {"resolution_cap": "tile", "audience": "public", "license": "project"},
    "event_record": {"resolution_cap": "event", "audience": "public", "license": "project"},
    "source_snapshot": {
        "resolution_cap": "source", "audience": "internal", "license": "public-domain-source",
    },
    "google_places_response": {
        "resolution_cap": "tile", "audience": "public", "license": "third-party-restricted",
    },
}

RULES = [
    {
        "id": "deny-publish-third-party-restricted",
        "effect": "deny",
        "reason": "Third-party licensed content may not be redistributed in the public site.",
        "match": {"license": "third-party-restricted"},
    },
    {
        "id": "deny-publish-parcel-resolution",
        "effect": "deny",
        "reason": "Parcel-resolution artifacts are lineage-only and are never served.",
        "match": {"resolution_cap": "parcel"},
    },
    {
        "id": "deny-publish-internal-audience",
        "effect": "deny",
        "reason": "Internal snapshots support reproduction, not publication.",
        "match": {"audience": "internal"},
    },
    {
        "id": "allow-publish-tile-products",
        "effect": "allow",
        "reason": "Tile-resolution products are the public evidence surface.",
        "match": {"resolution_cap": "tile", "audience": "public"},
    },
    {
        "id": "allow-publish-event-dossier",
        "effect": "allow",
        "reason": "Event dossiers carry the declared unknowns and must be public.",
        "match": {"resolution_cap": "event", "audience": "public"},
    },
]


def ref(kind: str, path: str = "events/e/x.bin") -> ArtifactRef:
    return ArtifactRef(path=path, kind=kind)


class TestDistributionPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = DistributionPolicy(artifact_classes=CLASSES, rules=RULES)

    def test_parcel_resolution_artifact_is_denied(self) -> None:
        decision = self.policy.evaluate(ref("damage_points_restricted"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "deny-publish-parcel-resolution")

    def test_internal_audience_artifact_is_denied(self) -> None:
        decision = self.policy.evaluate(ref("source_snapshot"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "deny-publish-internal-audience")

    def test_public_tile_product_is_allowed(self) -> None:
        decision = self.policy.evaluate(ref("damage_grid"))
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-publish-tile-products")

    def test_public_event_dossier_is_allowed(self) -> None:
        decision = self.policy.evaluate(ref("event_record"))
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-publish-event-dossier")

    def test_unclassified_kind_is_denied_naming_the_kind(self) -> None:
        # The fail-closed property that matters: a new artifact kind cannot be
        # published until somebody classifies it in the policy file.
        decision = self.policy.evaluate(ref("brand_new_kind"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "default-deny-unclassified")
        self.assertIn("brand_new_kind", decision.reason)

    def test_classified_kind_matching_no_rule_is_denied(self) -> None:
        policy = DistributionPolicy(
            artifact_classes={
                "orphan": {
                    "resolution_cap": "block", "audience": "public", "license": "project",
                }
            },
            rules=RULES,
        )
        decision = policy.evaluate(ref("orphan"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "default-deny")

    def test_third_party_restricted_content_is_denied_even_at_tile_resolution(self) -> None:
        # The tile-product allow rule would otherwise authorize this: it is
        # public, tile-capped, and classified. The licence is the only thing
        # standing between it and the public site, which is why it needs an
        # attribute of its own rather than a note in a docstring.
        decision = self.policy.evaluate(ref("google_places_response"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "deny-publish-third-party-restricted")


class TestDistributionValidation(unittest.TestCase):
    def test_unknown_match_key_raises_value_error_naming_rule_and_key(self) -> None:
        rules = [
            {
                "id": "typo-audience",
                "effect": "allow",
                "reason": "Should never construct.",
                "match": {"audeince": "public"},
            }
        ]
        with self.assertRaises(ValueError) as ctx:
            DistributionPolicy(artifact_classes=CLASSES, rules=rules)
        message = str(ctx.exception)
        self.assertIn("typo-audience", message)
        self.assertIn("audeince", message)

    def test_artifact_class_with_unknown_attribute_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            DistributionPolicy(
                artifact_classes={"damage_grid": {"resolution_cap": "tile", "licence": "public"}},
                rules=RULES,
            )
        self.assertIn("damage_grid", str(ctx.exception))
        self.assertIn("licence", str(ctx.exception))

    def test_from_yaml_requires_both_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.yaml"
            path.write_text("rules: []\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                DistributionPolicy.from_yaml(path)


class TestShippedPolicyV1(unittest.TestCase):
    """The committed policy must deny the parcel-level DINS source outright.

    This is the artifact that reached the public Pages site on 2026-08-20;
    the test exists so it can never be reintroduced by a policy edit.
    """

    def setUp(self) -> None:
        self.policy = DistributionPolicy.from_yaml(POLICY_V1)

    def test_dins_parcel_points_are_denied(self) -> None:
        decision = self.policy.evaluate(
            ArtifactRef(
                path="events/eaton-2025/exposure/dins_points_restricted.csv.gz",
                kind="damage_points_restricted",
            )
        )
        self.assertFalse(decision.allowed)

    def test_every_kind_in_every_committed_manifest_is_classified(self) -> None:
        # An unclassified kind is not an error here — it is a denial. This test
        # asserts the weaker, useful property: the policy has an opinion about
        # every kind the repository actually produces, so denials are chosen
        # rather than accidental.
        for manifest in sorted((REPO_ROOT / "events").glob("*/artifact_manifest.jsonl")):
            for kind in DistributionPolicy.kinds_in_manifest(manifest):
                with self.subTest(manifest=manifest.parent.name, kind=kind):
                    self.assertIn(kind, self.policy.artifact_classes)


if __name__ == "__main__":
    unittest.main()
