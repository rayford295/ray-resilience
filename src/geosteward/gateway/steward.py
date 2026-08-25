"""The Steward: policy pre-check → evidence retrieval → LLM → claim
post-check → audit. Every path through this module — approval, refusal,
outage, post-check rejection — produces one structured, audited response.

Deterministic code classifies the request and verifies the output; the LLM
never decides its own authorization and never gets the last word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import h3

from geosteward.gateway.context import RESOLUTION, EvidenceStore, EventEvidence
from geosteward.gateway.llm import LLMUnavailable, chat_completion
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import (
    RE_DERIVABLE,
    RETAINED,
    PolicyEngine,
    PolicyRequest,
    weakest,
)
from geosteward.live.base import LiveSource, LiveUnavailable
from geosteward.live.record import LiveEvidenceRecorder

# --- deterministic request classification (auditable, testable) -----------

_PARCEL_PATTERNS = (
    re.compile(r"\b\d{1,5}\s+[A-Z][A-Za-z]+\s+(Ave|Avenue|St|Street|Rd|Road|Dr|Drive|Blvd|Boulevard|Ln|Lane|Way|Ct|Court)\b", re.I),
    re.compile(r"\b(my|this|that)\s+(house|home|property|parcel|building|apartment)\b", re.I),
)
_DAMAGE_KEYWORDS = re.compile(r"\b(damage|damaged|destroyed|destruction|burned|burnt|ruined|loss(es)?)\b", re.I)
_EXPOSURE_KEYWORDS = re.compile(r"\b(exposure|exposed|vulnerab\w*|svi|risk|safe|safety|priorit\w*|resilien\w*)\b", re.I)
_FACILITY_KEYWORDS = re.compile(
    r"\b(hospitals?|clinics?|shelters?|schools?|police|pharmac\w*|"
    r"fire\s+stations?|urgent\s+care|evacuation\s+cent\w*|facilit\w*)\b",
    re.I,
)

_CITATION = re.compile(r"\[artifact:([0-9a-f]{12})\]")
#: The second citation form. Same 12-hex shape as an artifact id, because it is
#: the same kind of thing — the head of a sha256 — except the digest is over a
#: response this project never kept rather than over a file it did. It resolves
#: to a row in `events/live_evidence.jsonl`.
_LIVE_CITATION = re.compile(r"\[live:([0-9a-f]{12})\]")
_ANY_CITATION = re.compile(r"\[(?:artifact|live):[0-9a-f]{12}\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# --- non-assertive sentence forms ------------------------------------------
#
# Every sentence needs a citation unless it appears here. The direction matters
# more than the contents: the previous rule required citations on sentences
# containing a digit, which is a blocklist — it named the dangerous shape and
# let every other shape through, so "Your neighborhood was not significantly
# affected." passed with no evidence behind it.
#
# Inverting it makes the exemptions a closed set. A sentence form nobody
# anticipated is now refused rather than published, so the failure mode of
# getting this list wrong is an over-strict refusal instead of an uncited
# claim. That is the direction the rest of the harness fails in.

_QUESTION = re.compile(r"\?\s*$")

#: Advice asserts nothing about the location, so a citation requirement would
#: only push the model toward attaching an unrelated one. Matched at the head
#: of the sentence — optionally behind a leading conditional or "please" — so
#: "Inspectors will check every home" stays an assertion.
_IMPERATIVE_ADVICE = re.compile(
    r"^(?:if\s+[^,]{1,80},\s*)?(?:please\s+)?"
    r"(?:contact|call|check|consider|follow|monitor|review|see|visit|ask|keep|"
    r"avoid|report|register|apply|document|photograph|save|bring|wear|stay|"
    r"do not|don't|never)\b",
    re.I,
)

#: Statements about the answer's own limits. These are metadiscourse — they
#: describe what the system will not say, which the harness itself decided.
_DECLARED_LIMIT = re.compile(
    r"\b(?:makes? no claim|no claim (?:is|can be)|not authoriz|"
    r"(?:evidence|record|data|analysis)\s+(?:here\s+)?does not\s+"
    r"(?:answer|cover|include|support|extend)|"
    r"outside the evaluated|not (?:been )?evaluated|"
    r"i cannot|i can't|i do not have|i don't have|"
    r"geosteward (?:does not|cannot|makes no))\b",
    re.I,
)


def is_non_assertive(sentence: str) -> bool:
    """True when a sentence states no fact about the world, so needs no cite."""
    stripped = sentence.strip()
    if not stripped:
        return True
    return bool(
        _QUESTION.search(stripped)
        or _IMPERATIVE_ADVICE.match(stripped)
        or _DECLARED_LIMIT.search(stripped)
    )


def classify(question: str) -> tuple[str, str]:
    """(purpose, resolution) from the question text — rule-based on purpose:
    the LLM must never decide what the request is authorized to be.

    The order is the policy. `damage_assessment` stays first because it is the
    heaviest claim and the most constrained. `exposure` precedes
    `facility_context` deliberately: a question that mentions both vulnerability
    and hospitals is routed to the retained grids rather than to a live lookup,
    so ambiguity resolves toward the stronger verifiability. The cost is that
    such a question is answered from retained evidence only and simply does not
    address the facility half — which the answer then has to say.
    """
    resolution = "tile"
    for pattern in _PARCEL_PATTERNS:
        if pattern.search(question):
            resolution = "parcel"
            break
    if _DAMAGE_KEYWORDS.search(question):
        purpose = "damage_assessment"
    elif _EXPOSURE_KEYWORDS.search(question):
        purpose = "exposure"
    elif _FACILITY_KEYWORDS.search(question):
        purpose = "facility_context"
    else:
        purpose = "watch"
    return purpose, resolution


# --- claim post-check ------------------------------------------------------

def check_claims(
    text: str,
    allowed_ids: set[str],
    allowed_live_ids: set[str] | None = None,
) -> list[str]:
    """Violations found in a draft answer; empty list means it passes.

    Two citation forms, and one rule relating them: an answer that cites a
    non-retained source must ALSO cite a retained one. That is "cited-only
    cannot stand alone" in computable form — a live lookup may add facility
    context to a finding grounded in hashed evidence, but it may not be the
    only thing holding an answer up.
    """
    allowed_live_ids = allowed_live_ids or set()
    violations: list[str] = []
    cited = set(_CITATION.findall(text))
    live_cited = set(_LIVE_CITATION.findall(text))

    if not cited and not live_cited:
        violations.append("no citations at all")
    fabricated = cited - allowed_ids
    if fabricated:
        violations.append(f"fabricated citation ids: {sorted(fabricated)}")
    fabricated_live = live_cited - allowed_live_ids
    if fabricated_live:
        violations.append(f"fabricated live citation ids: {sorted(fabricated_live)}")
    if live_cited and not cited:
        violations.append(
            "live citations with no retained citation: a non-retainable source "
            "cannot be the only support for an answer"
        )

    stripped = _ANY_CITATION.sub("", text)
    for sentence in _SENTENCE_SPLIT.split(text):
        if _ANY_CITATION.search(sentence):
            continue
        bare = _ANY_CITATION.sub("", sentence).strip()
        if bare and not is_non_assertive(bare):
            violations.append(f"uncited assertion: {bare[:80]!r}")
    for pattern in _PARCEL_PATTERNS:
        if pattern.search(stripped):
            violations.append("parcel-level statement in the answer")
            break
    return violations


# --- the steward ------------------------------------------------------------

_SYSTEM_PROMPT = """You are GeoSteward, an accountable GeoAI risk analyst.
Rules you MUST follow:
1. Use ONLY the facts in the EVIDENCE block. Never use outside knowledge for factual claims.
2. EVERY sentence that states a fact about this place — counts, rates, comparisons, severity, safety, vulnerability, whether somewhere was affected — MUST end with the citation tag of the fact it came from, in the exact form [artifact:XXXXXXXXXXXX], copied verbatim from the evidence. This includes sentences with no numbers in them, and sentences about declared unknowns: cite the record they come from. Only three kinds of sentence may omit a citation: a question, general safety advice addressed to the reader ("Contact your county emergency management office."), and a statement about what you cannot say ("The evidence does not answer that."). If you cannot cite a factual sentence, delete the sentence.
3. Some evidence lines carry a [live:XXXXXXXXXXXX] tag instead. Those come from a live third-party lookup that was NOT retained: it can be re-checked by re-issuing the request, but no stored copy exists. Cite them the same way, verbatim. One extra rule: an answer that uses a [live:] fact MUST also use at least one [artifact:] fact. Never build an answer out of live facts alone.
4. Never make statements about a specific parcel, house, or street address. Your resolution limit is the tile (H3 r9, roughly 0.1 km^2).
5. State uncertainty and declared unknowns as prominently as findings.
6. If the evidence does not answer the question, say so plainly.
7. Output ONLY the final answer prose. No preamble, no analysis of these rules, no lists of which sentences contain numbers — just the answer a {role} should read.
Audience: {role}. For residents use plain, calm language; for planners be precise and quantitative."""


#: Purposes that can only be served by a non-retainable live source, mapped to
#: the verifiability such a source supplies.
#:
#: The mapping exists so the policy can still answer the LOCATION question when
#: no source is configured. Without it the request would carry `retained`, match
#: no allow rule, and be refused with "no policy rule authorizes this request" —
#: which is not why it failed. A request for facility context inside an AOI is
#: authorized; the capability is simply absent, and saying the wrong one of
#: those two things is the defect class the 2026-08-20 correctness pass was
#: about. Asking the policy what it would decide if the capability existed keeps
#: both answers honest: an out-of-AOI request still gets its real rule ID, and
#: an in-AOI one gets "not configured".
LIVE_PURPOSES: dict[str, str] = {"facility_context": RE_DERIVABLE}


@dataclass
class Steward:
    events_root: Path
    policy: PolicyEngine
    audit: AuditLog
    llm: Callable[[list[dict[str, str]]], str] = chat_completion
    max_attempts: int = 3
    #: Optional non-retainable source for `facility_context`. Absent by
    #: default: the public build ships without a key, and the honest response to
    #: "what hospitals are near me" with no source configured is a declared
    #: capability gap, not a keyless approximation from some other dataset.
    live_source: LiveSource | None = None
    #: Where live lookups are attested. Without it the lookup still happens and
    #: is still cited, but nothing durable records that it did — so the gateway
    #: declares the capability unavailable instead. Accountability is not the
    #: optional part.
    live_recorder: LiveEvidenceRecorder | None = None

    def __post_init__(self) -> None:
        self.store = EvidenceStore(self.events_root)

    def _live_unavailable(self, reason: str, detail: str | None = None) -> dict[str, Any]:
        self.audit.record(
            "gateway_live_unavailable", "steward", payload={"reason": reason, "detail": detail}
        )
        return {"type": "live_source_unavailable", "reason": reason}

    def _lookup(
        self, source: LiveSource, evidence: EventEvidence, lat: float, lon: float
    ) -> dict[str, Any]:
        """One live lookup: attest to it, then reduce it to a citable line.

        The order is load-bearing. The record is written BEFORE the result is
        used, so a lookup cannot influence an answer without having been
        attested — the reverse order would let a crash between the two leave a
        cited fact with no record of where it came from.

        What reaches the evidence block is the summary, not the response:
        counts by category, which this project derived, rather than the names
        the provider returned. That keeps the answer useful — "one hospital and
        one fire station within 1.2 km" is what a resident asked for — while no
        third-party content string is sent on to the model. Retention and
        onward disclosure are different questions, and a hosted model endpoint
        is onward disclosure.
        """
        cell = h3.latlng_to_cell(lat, lon, RESOLUTION)
        request = source.request_for_cell(cell)
        result = source.lookup(request)

        assert self.live_recorder is not None  # guarded by `live_ready`
        self.live_recorder.record(source, request, result)

        live_id = result.response_sha256[:12]
        counts = source.summarize(result)
        rendered = ", ".join(f"{category}={n}" for category, n in counts.items()) or "none"
        radius = request.parameters.get("radius_m")
        return {
            "live_id": live_id,
            "attribution": source.attribution,
            "line": (
                f"[live {source.provider} / {source.api} / tile {cell}] "
                f"facility counts within {radius} m: {rendered}; "
                f"n_results={result.n_results} | verifiability: {source.verifiability} "
                f"(re-check by re-issuing the recorded request; no copy is retained) "
                f"| attribution: {source.attribution} [live:{live_id}]"
            ),
        }

    def answer(
        self,
        role: str,
        question: str,
        *,
        lat: float | None = None,
        lon: float | None = None,
        area: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        #: A lone coordinate does not make a point, so `has_point` needs both
        #: -- but it is still a coordinate, and a coordinate given alongside
        #: an area is "both", not "neither". The old check compared
        #: `has_point == (area is not None)`, so `lat=5.0, lon=None,
        #: area=BOX` read as `False == True`, i.e. "neither", and passed.
        #: Checking `has_any_coord` against `area` first catches that shape
        #: before it can hide behind `has_point` being `False`; the second
        #: check then handles the ordinary neither-given and lone-coordinate
        #: cases. The check is here rather than only in the endpoint so a
        #: direct caller cannot skip it.
        has_area = area is not None
        has_any_coord = lat is not None or lon is not None
        has_point = lat is not None and lon is not None
        if has_area and has_any_coord:
            raise ValueError("give either lat/lon or area, not both and not neither")
        if not has_area and not has_point:
            raise ValueError("give either lat/lon or area, not both and not neither")

        purpose, resolution = classify(question)
        evidence = (
            self.store.evidence_for_area(area)
            if area is not None
            else self.store.evidence_for(lat, lon)
        )

        # Verifiability is decided before anything is fetched, from what the
        # configured sources DECLARE — so the policy gates the request before a
        # keyed, billable call is made, and an unauthorized question never
        # spends money or touches a third party.
        uses_live = purpose in LIVE_PURPOSES
        live_ready = self.live_source is not None and self.live_recorder is not None
        if not uses_live:
            verifiability = RETAINED
        elif self.live_source is not None:
            verifiability = weakest([RETAINED, self.live_source.verifiability])
        else:
            verifiability = LIVE_PURPOSES[purpose]

        request = PolicyRequest(
            role=role,
            purpose=purpose,
            resolution=resolution,
            evidence_tier=evidence.evidence_tier,
            in_aoi=evidence.in_aoi,
            verifiability=verifiability,
        )
        self.audit.record(
            "gateway_request", "steward",
            #: `area` is an addition alongside `lat`/`lon`, not a replacement:
            #: this project's product is a defensible record of why it said
            #: what it said, and a record that cannot answer "about where"
            #: for an area query is not that. Recorded exactly as received --
            #: full precision, not redacted or coarsened -- matching the
            #: exact coordinates and verbatim question this row already
            #: stores; redaction is a separately tracked, whole-audit concern
            #: (docs/STATUS.md), and solving half of it here would make the
            #: record inconsistent without making it safe.
            payload={"role": role, "lat": lat, "lon": lon, "area": area, "question": question,
                     "purpose": purpose, "resolution": resolution,
                     "verifiability": verifiability,
                     "event": evidence.event_id, "tier": evidence.evidence_tier},
        )

        decision = self.policy.evaluate(request)
        if not decision.allowed:
            self.audit.record("gateway_refusal", "steward",
                              payload={"reason": decision.reason}, rule_id=decision.rule_id)
            return {
                "type": "refusal",
                "rule_id": decision.rule_id,
                "reason": decision.reason,
                "purpose": purpose,
                "resolution": resolution,
            }

        if not evidence.facts:
            self.audit.record("gateway_no_evidence", "steward",
                              payload={"event": evidence.event_id}, rule_id=decision.rule_id)
            return {
                "type": "no_evidence",
                "rule_id": decision.rule_id,
                "reason": "The request is authorized, but no committed artifact covers "
                          "this location — monitoring data only, no conclusions supported.",
            }

        live_lines: list[str] = []
        allowed_live_ids: set[str] = set()
        attribution: str | None = None
        if uses_live:
            if area is not None:
                # Decided from the request shape, not from whether a source is
                # configured -- this branch must fire even when live_source is
                # None. Checked first so the gap is never latent behind a
                # capability check: the day a key is added, an area-shaped
                # facility question must still get this declared gap rather
                # than reaching `_lookup` and crashing on `lat=None`.
                return self._live_unavailable(
                    "Facility context needs a live point lookup; a drawn area "
                    "selection is not a point, and no centroid or other "
                    "substitute is used in its place."
                )
            if not live_ready:
                return self._live_unavailable(
                    "Facility context needs a live third-party lookup, and no live source "
                    "with an audit record is configured. No substitute is served in its "
                    "place."
                )
            try:
                live = self._lookup(self.live_source, evidence, lat, lon)
            except LiveUnavailable as error:
                return self._live_unavailable(
                    "The live facility source is unreachable; no cached or approximated "
                    "facility answer is served in its place.",
                    detail=str(error),
                )
            live_lines.append(live["line"])
            allowed_live_ids.add(live["live_id"])
            attribution = live["attribution"]

        evidence_block = "\n".join(
            [f.as_evidence_line() for f in evidence.facts] + live_lines
        )
        example_id = evidence.facts[0].artifact_id
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT.format(role=role)},
            {"role": "user",
             "content": f"EVIDENCE:\n{evidence_block}\n\n"
                        f"CITATION FORMAT (this example uses a real id from the evidence — "
                        f"attach the id of whichever fact each sentence uses): "
                        f"\"Surveyors assessed 82 structures in this tile "
                        f"[artifact:{example_id}].\"\n\n"
                        f"QUESTION ({role}): {question}"},
        ]

        violations: list[str] = []
        for attempt in range(self.max_attempts):
            try:
                draft = self.llm(messages)
            except LLMUnavailable as error:
                self.audit.record("gateway_llm_unavailable", "steward",
                                  payload={"error": str(error)})
                return {
                    "type": "agent_unavailable",
                    "reason": "The language model is unreachable; no cached or fabricated "
                              "answer is served in its place.",
                }
            violations = check_claims(draft, evidence.artifact_ids, allowed_live_ids)
            self.audit.record(
                "gateway_post_check", "steward",
                payload={"attempt": attempt + 1, "violations": violations},
            )
            if not violations:
                live_citations = sorted(set(_LIVE_CITATION.findall(draft)))
                self.audit.record(
                    "gateway_response", "steward",
                    payload={"citations": sorted(set(_CITATION.findall(draft))),
                             "live_citations": live_citations,
                             "verifiability": verifiability},
                    rule_id=decision.rule_id,
                )
                response = {
                    "type": "answer",
                    "text": draft,
                    "rule_id": decision.rule_id,
                    "event": evidence.event_id,
                    "n_facts": len(evidence.facts),
                    #: The tiles this answer drew on, so the map can show what
                    #: it is about. r9 identifiers only, the resolution already
                    #: published in the grids the app renders.
                    "cells": evidence.cells,
                    "citations": sorted(set(_CITATION.findall(draft))),
                    "live_citations": live_citations,
                    #: The reader's standing, not a quality score: what they can
                    #: do to check this answer. `re-derivable` means part of it
                    #: rests on something no copy of exists here.
                    "verifiability": verifiability,
                }
                if attribution and live_citations:
                    # Required wherever the content is surfaced, and carried in
                    # the response so the client cannot render the answer
                    # without also receiving the attribution it owes.
                    response["attribution"] = attribution
                return response
            messages.append({"role": "assistant", "content": draft})
            messages.append({
                "role": "user",
                "content": "Your draft violated claim rules: "
                           + "; ".join(violations)
                           + ". Rewrite it so every factual sentence carries a valid "
                             "[artifact:ID] or [live:ID] tag from the evidence, at least "
                             "one [artifact:ID] tag is present, and no parcel-level "
                             "statement remains.",
            })

        self.audit.record("gateway_refusal", "steward",
                          payload={"violations": violations}, rule_id="claim-post-check")
        return {
            "type": "refusal",
            "rule_id": "claim-post-check",
            "reason": "The model's draft failed the claim post-check "
                      f"({'; '.join(violations)}); the harness fails closed rather than "
                      "serving unverifiable prose.",
        }
