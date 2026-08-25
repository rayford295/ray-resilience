"""Evidence agent: post-event cross-view damage assessment (interface).

Methodology comes from the CrossViewGate research line: street-level and
overhead views are witnesses with different competence; a reliability gate
arbitrates per sample, and units neither view can attest get an explicit
abstain + acquisition flag instead of a forced label.

This agent activates in the post-event phase once imagery manifests exist.
It deliberately fails closed until then — no synthetic damage numbers.
"""

from __future__ import annotations

from geosteward.agents.base import Agent, Artifact, EventContext


class CrossViewEvidence:
    name = "evidence.crossview"

    def run(self, context: EventContext) -> list[Artifact]:
        imagery_manifest = context.event_dir / "evidence" / "imagery_manifest.csv"
        if not imagery_manifest.exists():
            raise FileNotFoundError(
                "Post-event imagery manifest not found "
                f"({imagery_manifest}). The evidence agent fails closed rather "
                "than emitting damage estimates without imagery."
            )
        raise NotImplementedError(
            "Cross-view assessment activates in the post-event phase; "
            "see docs/manual/06-data-and-evidence.md and the CrossViewGate "
            "research line."
        )
