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

from geosteward.gateway.context import EvidenceStore, EventEvidence
from geosteward.gateway.llm import LLMUnavailable, chat_completion
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import PolicyEngine, PolicyRequest

# --- deterministic request classification (auditable, testable) -----------

_PARCEL_PATTERNS = (
    re.compile(r"\b\d{1,5}\s+[A-Z][A-Za-z]+\s+(Ave|Avenue|St|Street|Rd|Road|Dr|Drive|Blvd|Boulevard|Ln|Lane|Way|Ct|Court)\b", re.I),
    re.compile(r"\b(my|this|that)\s+(house|home|property|parcel|building|apartment)\b", re.I),
)
_DAMAGE_KEYWORDS = re.compile(r"\b(damage|damaged|destroyed|destruction|burned|burnt|ruined|loss(es)?)\b", re.I)
_EXPOSURE_KEYWORDS = re.compile(r"\b(exposure|exposed|vulnerab\w*|svi|risk|safe|safety|priorit\w*|resilien\w*)\b", re.I)

_CITATION = re.compile(r"\[artifact:([0-9a-f]{12})\]")
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
    the LLM must never decide what the request is authorized to be."""
    resolution = "tile"
    for pattern in _PARCEL_PATTERNS:
        if pattern.search(question):
            resolution = "parcel"
            break
    if _DAMAGE_KEYWORDS.search(question):
        purpose = "damage_assessment"
    elif _EXPOSURE_KEYWORDS.search(question):
        purpose = "exposure"
    else:
        purpose = "watch"
    return purpose, resolution


# --- claim post-check ------------------------------------------------------

def check_claims(text: str, allowed_ids: set[str]) -> list[str]:
    """Violations found in a draft answer; empty list means it passes."""
    violations: list[str] = []
    cited = set(_CITATION.findall(text))
    if not cited:
        violations.append("no artifact citations at all")
    fabricated = cited - allowed_ids
    if fabricated:
        violations.append(f"fabricated citation ids: {sorted(fabricated)}")
    stripped = _CITATION.sub("", text)
    for sentence in _SENTENCE_SPLIT.split(text):
        if _CITATION.search(sentence):
            continue
        bare = _CITATION.sub("", sentence).strip()
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
3. Never make statements about a specific parcel, house, or street address. Your resolution limit is the tile (H3 r9, roughly 0.1 km^2).
4. State uncertainty and declared unknowns as prominently as findings.
5. If the evidence does not answer the question, say so plainly.
6. Output ONLY the final answer prose. No preamble, no analysis of these rules, no lists of which sentences contain numbers — just the answer a {role} should read.
Audience: {role}. For residents use plain, calm language; for planners be precise and quantitative."""


@dataclass
class Steward:
    events_root: Path
    policy: PolicyEngine
    audit: AuditLog
    llm: Callable[[list[dict[str, str]]], str] = chat_completion
    max_attempts: int = 3

    def __post_init__(self) -> None:
        self.store = EvidenceStore(self.events_root)

    def answer(self, role: str, lat: float, lon: float, question: str) -> dict[str, Any]:
        purpose, resolution = classify(question)
        evidence = self.store.evidence_for(lat, lon)
        request = PolicyRequest(
            role=role,
            purpose=purpose,
            resolution=resolution,
            evidence_tier=evidence.evidence_tier,
            in_aoi=evidence.in_aoi,
        )
        self.audit.record(
            "gateway_request", "steward",
            payload={"role": role, "lat": lat, "lon": lon, "question": question,
                     "purpose": purpose, "resolution": resolution,
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

        evidence_block = "\n".join(f.as_evidence_line() for f in evidence.facts)
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
            violations = check_claims(draft, evidence.artifact_ids)
            self.audit.record(
                "gateway_post_check", "steward",
                payload={"attempt": attempt + 1, "violations": violations},
            )
            if not violations:
                self.audit.record("gateway_response", "steward",
                                  payload={"citations": sorted(set(_CITATION.findall(draft)))},
                                  rule_id=decision.rule_id)
                return {
                    "type": "answer",
                    "text": draft,
                    "rule_id": decision.rule_id,
                    "event": evidence.event_id,
                    "n_facts": len(evidence.facts),
                    "citations": sorted(set(_CITATION.findall(draft))),
                }
            messages.append({"role": "assistant", "content": draft})
            messages.append({
                "role": "user",
                "content": "Your draft violated claim rules: "
                           + "; ".join(violations)
                           + ". Rewrite it so every factual sentence carries a valid "
                             "[artifact:ID] tag from the evidence and no parcel-level "
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
