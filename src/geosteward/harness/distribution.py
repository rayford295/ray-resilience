"""Distribution validity: what the project is authorized to publish.

`policy.py` governs what the agent may *claim*. This module governs what a
build may *serve*. The distinction is not academic: on 2026-08-20 a
parcel-level DINS source reached the public Pages site without violating a
single claim-plane rule, because it was never claimed — it was copied. The
institutional constraint existed in prose (`dins.py`, `STATUS.md`) and in the
manifest (`kind: damage_points_restricted`) but nothing read it.

Two declarations, one grammar:

  * `artifact_classes` maps each artifact `kind` to publication attributes.
    A kind with no entry is denied. Adding a product to `events/` therefore
    cannot widen the public surface until somebody classifies it.
  * `distribution` is an ordered rule list over those attributes, evaluated
    first-match-wins with a fail-closed default, exactly like the claim plane.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from geosteward.harness.policy import PolicyDecision, default_deny, validate_rules

#: Publication attributes a kind may declare. Kept deliberately small: each
#: one must be answerable about any artifact without opening the file.
#:
#: `license` answers a question the other two cannot: `resolution_cap` and
#: `audience` are both about what *this project* judges safe to serve, and a
#: third party's terms are not ours to judge. It was suggested in the review
#: that produced this plane and left out because nothing needed it; live
#: third-party lookups are what need it.
KNOWN_CLASS_ATTRIBUTES = frozenset({"resolution_cap", "audience", "license"})

KNOWN_MATCH_KEYS = KNOWN_CLASS_ATTRIBUTES

#: A closed set, validated at load. Unlike `resolution_cap` and `audience`,
#: whose values are only ever compared against rules in the same file, a
#: license names an external constraint — and `third-party-restrcited` would
#: match no deny rule and publish the file. Same reasoning as the unknown-key
#: check in `validate_rules`: a typo must narrow or fail, never widen.
#:
#:   project                  Produced by this project from sources it may
#:                            redistribute; the public evidence surface.
#:   public-domain-source     Frozen upstream state from a public-domain
#:                            provider (US government APIs and datasets).
#:   third-party-restricted   Content under third-party terms that forbid
#:                            redistribution. Never published, by rule.
KNOWN_LICENSES = frozenset({"project", "public-domain-source", "third-party-restricted"})


@dataclass(frozen=True)
class ArtifactRef:
    """One artifact considered for publication."""

    path: str
    kind: str


def _validate_classes(classes: Any) -> dict[str, dict[str, str]]:
    if not isinstance(classes, dict):
        raise ValueError("'artifact_classes' must be a mapping of kind -> attributes.")
    for kind, attributes in classes.items():
        if not isinstance(attributes, dict):
            raise ValueError(f"Artifact class '{kind}' must be a mapping, got: {attributes!r}")
        for key in attributes:
            if key not in KNOWN_CLASS_ATTRIBUTES:
                raise ValueError(
                    f"Artifact class '{kind}' has unknown attribute '{key}'; "
                    f"expected one of {sorted(KNOWN_CLASS_ATTRIBUTES)}."
                )
        for required in sorted(KNOWN_CLASS_ATTRIBUTES):
            if required not in attributes:
                raise ValueError(
                    f"Artifact class '{kind}' is missing required attribute '{required}'."
                )
        if attributes["license"] not in KNOWN_LICENSES:
            raise ValueError(
                f"Artifact class '{kind}' has unknown license "
                f"{attributes['license']!r}; expected one of {sorted(KNOWN_LICENSES)}."
            )
    return classes


class DistributionPolicy:
    def __init__(
        self,
        artifact_classes: dict[str, dict[str, str]],
        rules: list[dict[str, Any]],
        published_events: list[str] | None = None,
    ):
        self.artifact_classes = _validate_classes(artifact_classes)
        self.rules = validate_rules(rules, KNOWN_MATCH_KEYS, section="distribution")
        self.published_events = list(published_events or [])

    @classmethod
    def from_yaml(cls, path: Path) -> "DistributionPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Policy file {path} must be a mapping.")
        for section in ("artifact_classes", "distribution", "published_events"):
            if section not in payload:
                raise ValueError(
                    f"Policy file {path} is missing the '{section}' section; "
                    "the distribution plane cannot fail closed without it."
                )
        events = payload["published_events"]
        if not isinstance(events, list) or not all(isinstance(e, str) for e in events):
            raise ValueError(f"Policy file {path} 'published_events' must be a list of event ids.")
        return cls(payload["artifact_classes"], payload["distribution"], events)

    def evaluate(self, artifact: ArtifactRef) -> PolicyDecision:
        attributes = self.artifact_classes.get(artifact.kind)
        if attributes is None:
            return default_deny(
                f"Artifact kind '{artifact.kind}' is not classified for distribution; "
                "classify it in policy 'artifact_classes' before publishing.",
                rule_id="default-deny-unclassified",
            )
        for rule in self.rules:
            match = rule.get("match", {})
            if all(attributes.get(key) == value for key, value in match.items()):
                return PolicyDecision(
                    allowed=rule["effect"] == "allow",
                    rule_id=rule["id"],
                    reason=rule["reason"],
                )
        return default_deny(
            f"No distribution rule authorizes publishing kind '{artifact.kind}'; "
            "the harness fails closed."
        )

    @staticmethod
    def kinds_in_manifest(manifest: Path) -> list[str]:
        """Distinct artifact kinds recorded in one `artifact_manifest.jsonl`."""
        kinds: dict[str, None] = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                kinds[json.loads(line)["kind"]] = None
        return list(kinds)
