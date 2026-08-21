"""The gateway under the non-retainable regime.

Three properties, in descending order of how much they matter:

  1. **Policy decides before anything is fetched.** An unauthorized question
     must never reach a third party. It is not only a privacy point: a keyed
     API in a public demo is a billing surface, and "we checked afterwards" is
     not a control.
  2. **A lookup is attested before it is used.** The record is written before
     the result reaches the model, so no cited fact can exist without a row
     saying where it came from — including when the answer is ultimately
     refused.
  3. **Cited-only cannot stand alone.** A non-retainable source may add to an
     answer grounded in hashed evidence. It may not be the only thing holding
     one up.
"""

import json
import unittest
from pathlib import Path

from geosteward.gateway.llm import LLMUnavailable
from geosteward.gateway.steward import Steward, check_claims, classify
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import (
    CITED_ONLY,
    RE_DERIVABLE,
    RETAINED,
    PolicyEngine,
    PolicyRequest,
    weakest,
)
from geosteward.live.base import response_digest
from geosteward.live.fake import POISON_PAYLOAD, POISON_STRINGS, FakeLiveSource
from geosteward.live.record import LiveEvidenceRecorder

from tests.test_gateway_steward import (
    GRID_ID,
    IN_AOI,
    OUTSIDE,
    POLICY,
    GatewayTestCase,
    MockLLM,
)

#: The id the fake's response digests to, so a draft can cite it correctly.
LIVE_ID = response_digest(POISON_PAYLOAD)[:12]


class TestClassifyFacilityContext(unittest.TestCase):
    def test_facility_question_is_facility_context(self) -> None:
        self.assertEqual(classify("What hospitals are near here?")[0], "facility_context")
        self.assertEqual(classify("Where is the nearest shelter?")[0], "facility_context")
        self.assertEqual(classify("Are there schools in this area?")[0], "facility_context")

    def test_damage_still_wins_over_facilities(self) -> None:
        # The heaviest claim keeps priority; it is also the one the new denial
        # rule constrains.
        self.assertEqual(classify("Was the hospital damaged?")[0], "damage_assessment")

    def test_exposure_wins_over_facilities(self) -> None:
        # Ambiguity resolves toward the stronger verifiability: answer from the
        # retained grids rather than reaching for a live lookup.
        self.assertEqual(classify("Is the area around the hospital vulnerable?")[0], "exposure")


class TestWeakestLink(unittest.TestCase):
    def test_a_claim_is_no_more_verifiable_than_its_weakest_support(self) -> None:
        self.assertEqual(weakest([RETAINED, RE_DERIVABLE]), RE_DERIVABLE)
        self.assertEqual(weakest([RETAINED, RE_DERIVABLE, CITED_ONLY]), CITED_ONLY)
        self.assertEqual(weakest([RETAINED, RETAINED]), RETAINED)

    def test_no_support_is_the_floor_not_the_ceiling(self) -> None:
        self.assertEqual(weakest([]), CITED_ONLY)

    def test_unknown_verifiability_raises(self) -> None:
        with self.assertRaises(ValueError):
            weakest([RETAINED, "probably-fine"])


class TestVerifiabilityPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PolicyEngine.from_yaml(POLICY)

    def request(self, **overrides) -> PolicyRequest:
        parameters = {
            "role": "planner",
            "purpose": "damage_assessment",
            "resolution": "tile",
            "evidence_tier": 3,
            "in_aoi": True,
        }
        parameters.update(overrides)
        return PolicyRequest(**parameters)

    def test_damage_assessment_on_live_support_alone_is_denied(self) -> None:
        decision = self.policy.evaluate(self.request(verifiability=RE_DERIVABLE))
        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.rule_id, "deny-damage-assessment-without-retained-evidence"
        )

    def test_damage_assessment_on_retained_evidence_is_still_allowed(self) -> None:
        decision = self.policy.evaluate(self.request())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-planner-damage-tier3")

    def test_facility_context_on_a_re_derivable_source_is_allowed(self) -> None:
        decision = self.policy.evaluate(
            self.request(purpose="facility_context", verifiability=RE_DERIVABLE)
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule_id, "allow-facility-context-re-derivable")

    def test_facility_context_on_grounded_prose_falls_through_to_default_deny(self) -> None:
        # No rule mentions cited-only. The fail-closed default carries the
        # non-deterministic regime, which is the behaviour to want: nobody had
        # to anticipate it correctly.
        decision = self.policy.evaluate(
            self.request(purpose="facility_context", verifiability=CITED_ONLY)
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule_id, "default-deny")

    def test_facility_context_outside_an_aoi_is_denied(self) -> None:
        decision = self.policy.evaluate(
            self.request(purpose="facility_context", verifiability=RE_DERIVABLE, in_aoi=False)
        )
        self.assertFalse(decision.allowed)

    def test_unknown_verifiability_in_a_rule_fails_at_load(self) -> None:
        # A typo would match nothing and therefore deny nothing, so it raises
        # rather than silently widening the rule.
        with self.assertRaises(ValueError) as ctx:
            PolicyEngine([
                {
                    "id": "typo-verifiability",
                    "effect": "deny",
                    "reason": "Should never construct.",
                    "match": {"verifiability_below": "retianed"},
                }
            ])
        self.assertIn("typo-verifiability", str(ctx.exception))


class TestCheckClaimsLiveForm(unittest.TestCase):
    IDS = {GRID_ID}
    LIVE_IDS = {LIVE_ID}

    def test_live_citation_alone_is_refused(self) -> None:
        text = f"One hospital sits within 1.2 km of this tile [live:{LIVE_ID}]."
        violations = check_claims(text, self.IDS, self.LIVE_IDS)
        self.assertTrue(any("cannot be the only support" in v for v in violations))

    def test_live_citation_beside_a_retained_one_passes(self) -> None:
        text = (
            f"About 10 structures were assessed in this tile [artifact:{GRID_ID}]. "
            f"One hospital sits within 1.2 km [live:{LIVE_ID}]."
        )
        self.assertEqual(check_claims(text, self.IDS, self.LIVE_IDS), [])

    def test_fabricated_live_id_is_caught(self) -> None:
        text = (
            f"About 10 structures were assessed [artifact:{GRID_ID}]. "
            "A hospital is nearby [live:0123456789ab]."
        )
        violations = check_claims(text, self.IDS, self.LIVE_IDS)
        self.assertTrue(any("fabricated live citation" in v for v in violations))

    def test_a_live_citation_satisfies_its_own_sentence(self) -> None:
        # Otherwise the sentence would be flagged uncited AND the answer would
        # be flagged live-only, which reads as two problems instead of one.
        text = (
            f"About 10 structures were assessed [artifact:{GRID_ID}]. "
            f"Two schools are within 1.2 km [live:{LIVE_ID}]."
        )
        self.assertNotIn(
            True, [v.startswith("uncited assertion") for v in check_claims(text, self.IDS, self.LIVE_IDS)]
        )

    def test_live_ids_are_not_accepted_when_no_lookup_happened(self) -> None:
        text = f"Structures were assessed [artifact:{GRID_ID}]. A hospital is near [live:{LIVE_ID}]."
        violations = check_claims(text, self.IDS)
        self.assertTrue(any("fabricated live citation" in v for v in violations))


class LiveGatewayTestCase(GatewayTestCase):
    def make_live_steward(self, llm, source=None, with_recorder=True):
        self.live_path = self.root / "live_evidence.jsonl"
        self.source = source if source is not None else FakeLiveSource()
        return Steward(
            events_root=self.root / "events",
            policy=PolicyEngine.from_yaml(POLICY),
            audit=AuditLog(self.audit_path),
            llm=llm,
            live_source=self.source,
            live_recorder=(
                LiveEvidenceRecorder(self.live_path) if with_recorder else None
            ),
        )

    def live_rows(self):
        if not self.live_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.live_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def compliant_draft() -> str:
        return (
            f"About 10 structures were assessed in this tile [artifact:{GRID_ID}]. "
            f"One hospital and one fire station are within 1.2 km [live:{LIVE_ID}]."
        )


class TestPolicyGatesBeforeSpending(LiveGatewayTestCase):
    def test_no_live_call_is_made_for_an_unauthorized_location(self) -> None:
        # The property that matters most here. Outside every AOI, the facility
        # allow rule cannot match, so the request is refused — and the third
        # party is never contacted, so an unauthorized question costs nothing
        # and discloses nothing.
        steward = self.make_live_steward(MockLLM([]))
        response = steward.answer("resident", *OUTSIDE, "What hospitals are near here?")

        self.assertEqual(response["type"], "refusal")
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.live_rows(), [])

    def test_the_refusal_names_a_rule(self) -> None:
        steward = self.make_live_steward(MockLLM([]))
        response = steward.answer("resident", *OUTSIDE, "What hospitals are near here?")
        self.assertTrue(response["rule_id"])


class TestDeclaredCapabilityGaps(LiveGatewayTestCase):
    def test_no_live_source_is_declared_not_approximated(self) -> None:
        steward = Steward(
            events_root=self.root / "events",
            policy=PolicyEngine.from_yaml(POLICY),
            audit=AuditLog(self.audit_path),
            llm=MockLLM([]),
        )
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        self.assertEqual(response["type"], "live_source_unavailable")
        self.assertIn("No substitute", response["reason"])

    def test_a_source_without_a_recorder_is_refused(self) -> None:
        # Accountability is not the optional half. A lookup nothing records
        # would produce a cited fact with no provenance, which is the failure
        # this whole design exists to avoid.
        steward = self.make_live_steward(MockLLM([]), with_recorder=False)
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        self.assertEqual(response["type"], "live_source_unavailable")
        self.assertEqual(self.source.calls, [])

    def test_an_outage_is_declared_rather_than_cached(self) -> None:
        steward = self.make_live_steward(MockLLM([]), source=FakeLiveSource(unavailable=True))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        self.assertEqual(response["type"], "live_source_unavailable")
        self.assertIn("no cached or approximated", response["reason"])
        self.assertEqual(self.live_rows(), [])


class TestLiveAnswer(LiveGatewayTestCase):
    def test_authorized_facility_answer_carries_both_citation_forms(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        self.assertEqual(response["type"], "answer")
        self.assertEqual(response["rule_id"], "allow-facility-context-re-derivable")
        self.assertEqual(response["citations"], [GRID_ID])
        self.assertEqual(response["live_citations"], [LIVE_ID])

    def test_the_answer_reports_its_own_verifiability(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        # Weakest link: most of this answer rests on hashed grids, and it is
        # still only re-derivable, because one part of it is.
        self.assertEqual(response["verifiability"], RE_DERIVABLE)

    def test_attribution_travels_with_the_answer(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        self.assertEqual(response["attribution"], "Fake Maps Provider")

    def test_retained_only_answers_do_not_claim_an_attribution(self) -> None:
        draft = f"About 10 structures were assessed in this tile [artifact:{GRID_ID}]."
        steward = self.make_live_steward(MockLLM([draft]))
        response = steward.answer("planner", *IN_AOI, "How vulnerable is this area?")
        self.assertEqual(response["type"], "answer")
        self.assertEqual(response["verifiability"], RETAINED)
        self.assertNotIn("attribution", response)

    def test_the_model_is_given_counts_not_names(self) -> None:
        llm = MockLLM([self.compliant_draft()])
        steward = self.make_live_steward(llm)
        steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        sent = json.dumps(llm.last_messages)
        self.assertIn("hospital=1", sent)
        self.assertIn("fire_station=1", sent)
        for poison in POISON_STRINGS:
            with self.subTest(poison=poison):
                self.assertNotIn(poison, sent)


class TestAttestationOrdering(LiveGatewayTestCase):
    def test_the_lookup_is_recorded(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        rows = self.live_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "live_lookup")
        self.assertEqual(rows[0]["payload"]["response_sha256"][:12], LIVE_ID)
        self.assertEqual(rows[0]["payload"]["verifiability"], RE_DERIVABLE)

    def test_the_record_survives_a_refused_answer(self) -> None:
        # The lookup happened, so it is on the record, even though nothing was
        # served. The reverse — using a result and recording it afterwards —
        # would let a crash leave a cited fact with no provenance.
        uncited = ["The area is fine." for _ in range(3)]
        steward = self.make_live_steward(MockLLM(uncited))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        self.assertEqual(response["type"], "refusal")
        self.assertEqual(response["rule_id"], "claim-post-check")
        self.assertEqual(len(self.live_rows()), 1)

    def test_the_record_holds_no_third_party_content(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        written = self.live_path.read_text(encoding="utf-8")
        for poison in POISON_STRINGS:
            with self.subTest(poison=poison):
                self.assertNotIn(poison, written)

    def test_the_request_is_recorded_at_tile_resolution(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        recorded = self.live_rows()[0]["payload"]["request"]
        self.assertIn("h3_cell", recorded)
        self.assertNotIn(str(IN_AOI[0]), json.dumps(recorded))

    def test_the_audit_log_records_the_verifiability_of_the_request(self) -> None:
        steward = self.make_live_steward(MockLLM([self.compliant_draft()]))
        steward.answer("resident", *IN_AOI, "What hospitals are near here?")

        requests = [r for r in self.audit_rows() if r["action"] == "gateway_request"]
        self.assertEqual(requests[-1]["payload"]["verifiability"], RE_DERIVABLE)


class TestLiveAndModelOutagesAreDistinct(LiveGatewayTestCase):
    def test_model_outage_after_a_successful_lookup_is_reported_as_a_model_outage(self) -> None:
        steward = self.make_live_steward(MockLLM([LLMUnavailable("no model")]))
        response = steward.answer("resident", *IN_AOI, "What hospitals are near here?")
        self.assertEqual(response["type"], "agent_unavailable")
        # The lookup still happened, so it is still attested.
        self.assertEqual(len(self.live_rows()), 1)


if __name__ == "__main__":
    unittest.main()
