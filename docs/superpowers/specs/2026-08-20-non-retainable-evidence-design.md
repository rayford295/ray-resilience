# Accountability for non-retainable evidence — Design Document

**Date:** 2026-08-20
**Status:** Design agreed in brainstorming; three decisions still open (§11). Not yet implemented.
**Motivating context:** The author is a Google Maps Platform Innovator, and OASIS 2026 is
Google-hosted, so Google Maps Platform (GMP) is a natural capability source. Investigating
how to add it surfaced a structural problem worth more than the capabilities themselves.

## 1. The collision

GeoSteward's process validity works one way: hash every input, freeze it, commit it, publish
the chain. `artifact_manifest.jsonl` records a sha256 for every artifact; the app fetches the
manifest so any number on the map traces back to a hashed file.

Google Maps Platform's terms forbid exactly that. Customers may not "export, extract, or
otherwise scrape Google Maps Content for use outside the Services." Place IDs may be stored
indefinitely; latitude/longitude from Geocoding may be cached for at most 30 consecutive days;
names, ratings, reviews, photos, and phone numbers are to be requested live and displayed with
attribution, not warehoused.

> **GeoSteward's mechanism for proving traceability is structurally incompatible with the
> licensing terms of the data it would most like to use.**

This is not a blocker. It is a research question the project is unusually well placed to
answer:

> **When you are contractually forbidden from retaining the evidence, what makes a claim
> derived from it accountable?**

Sources (re-verify before implementation; terms change):
[Geocoding API policies](https://developers.google.com/maps/documentation/geocoding/policies) ·
[Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies) ·
[Maps Platform Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms) ·
[Grounding with Google Maps](https://mapsplatform.google.com/resources/blog/powering-the-next-era-of-agentic-experiences-announcing-new-grounding-capabilities/)

## 2. Relation to the 2026-08-20 publication-boundary incident

Both findings are about **enforcement surfaces**, and they are the same lesson twice.

The incident showed a constraint stated in prose and encoded in a manifest field that nothing
read, because the harness modelled claims and not distribution
(`docs/incidents/2026-08-20-publication-boundary.md`).

This design addresses the surface one step further out: a constraint imposed by a **third
party** on data the project does not own. The distribution plane already asks "may this be
published?" It cannot yet ask "may this be *kept*?" — and for third-party content that is the
binding question.

The two planes and the axis this design adds compose as:

| Question | Where it is answered |
|---|---|
| What may the agent assert? | claim plane (`rules:`) |
| What may a build publish? | distribution plane (`distribution:`) |
| What may be retained at all, and can a reader check it? | **`verifiability` axis + `license` attribute (this design)** |

## 3. Two regimes, not one

The naive framing — "third-party data is unretainable, handle it specially" — hides the
distinction that matters. Re-derivation verification requires **determinism**, and Google
returns two kinds of thing:

| Regime | Example | Determinism | Verifiable anchor |
|---|---|---|---|
| Non-retainable but **re-derivable** | Places, Elevation, Air Quality — structured responses | Stable for the same request, modulo genuine data updates | Request parameters + response sha256. A third party with their own key re-issues the request and compares. Drift is meaningful signal, not noise. |
| Non-retainable and **non-deterministic** | Grounding with Google Maps — model-generated prose | None. Varies across model versions even at temperature 0. | The grounding **citations**, not the text. Hashing the prose is worthless. |

The second regime is the harder and more interesting one:

> **When evidence can be neither retained nor reproduced, the smallest accountable unit is the
> citation, not the content.**

Both regimes are defined in this design. The first is implemented against a live API; the
second gets its contract, its policy rules, and a fake adapter, with the real integration
behind a switch (§10).

## 4. `verifiability` — a third axis, orthogonal to tier

The existing tier ladder (1 watch / 2 analysis / 3 evidence) encodes **freshness and depth of
evidence**. Third-party data does not fail on that axis: a Places fact can be current and
accurate and still be **uncheckable by a reader without a key**.

Verifiability and tier are orthogonal. Folding one into the other erases the distinction, so
`PolicyRequest` gains a field:

| Value | Meaning |
|---|---|
| `retained` | A hashed copy exists in the repository. Every product built to date. |
| `re-derivable` | Structured third-party response; request and response hash recorded; a reader with their own key re-issues and compares. |
| `cited-only` | Generated or grounded content; only the citations are checkable, the text is not reproducible. |

**Ordering.** The three values are totally ordered, strongest first:

```
retained  >  re-derivable  >  cited-only
```

The order is by *what a reader can do*: check a hashed copy in the repository; re-issue a
request with their own key and compare; check only that the cited references exist. Comparisons
like `verifiability_below: retained` are defined against this order, matching how
`evidence_tier_below` reads against the tier ladder.

**Semantics: weakest link.** Where an answer draws on several sources, the request carries the
**minimum** of their verifiability. A claim is no more verifiable than its weakest support.
This is the property the policy reasons about and the sentence the paper states.

`PolicyRequest` currently takes `role, purpose, resolution, evidence_tier, in_aoi`. The new
field takes a default of `retained`, so all 149 existing tests keep constructing it unchanged.
`_KNOWN_MATCH_KEYS` gains `verifiability` and `verifiability_below`, matching the existing
`evidence_tier_at_least` / `evidence_tier_below` pattern.

New rules in the claim plane. Evaluation is first-match-wins, so **position is semantic**: the
denial joins the existing hard-denial block (after `deny-resident-damage-assessment`, before
the authorizations), and the authorization goes at the end of the allow block.

```yaml
# --- hard denials ---
- id: deny-damage-assessment-without-retained-evidence
  effect: deny
  reason: Damage assessment requires retained, hashed cross-view evidence; a live third-party lookup cannot support it.
  match: {purpose: damage_assessment, verifiability_below: retained}

# --- authorizations ---
- id: allow-facility-context-re-derivable
  effect: allow
  reason: Tile-level facility context may come from a re-derivable live source when paired with retained exposure.
  match: {purpose: facility_context, resolution: tile, in_aoi: true, verifiability: re-derivable}
```

Note what the second rule does *not* say: it does not permit `cited-only`. A grounded answer
about facilities falls through every allow rule to `default-deny`. The fail-closed default
carries the second regime without a rule being written for it, which is the behaviour to want.

`facility_context` is a new purpose; `classify()` in `gateway/steward.py` must recognise
questions of the form "what hospitals / shelters / schools are near here". Whether this purpose
should exist at all is open — see §11.1.

## 5. `license` — the distribution plane's third attribute

The distribution plane landed with `resolution_cap` and `audience`. The external review that
prompted it also suggested `license`, which was left unimplemented because nothing yet needed
it. Third-party content is what needs it.

```yaml
artifact_classes:
  damage_grid:         {resolution_cap: tile,   audience: public,   license: project}
  source_snapshot:     {resolution_cap: source, audience: internal, license: public-domain-source}
  live_lookup_record:  {resolution_cap: tile,   audience: public,   license: project}

distribution:
  - id: deny-publish-third-party-restricted
    effect: deny
    reason: Third-party licensed content may not be redistributed in the public site.
    match: {license: third-party-restricted}
```

This rule is structural rather than advisory. Any Google-derived file that reaches `events/` —
however it got there, whether or not anyone recorded it in a manifest — cannot be published.
Combined with `verify`'s existing set-difference over the assembled site, that is two
independent defences: one that denies a *classified* artifact, one that denies an
*unrecognised* file.

## 6. The core result: the audit record is publishable because it holds no content

`events/live_evidence.jsonl`, append-only, containing **no Maps Content**:

```json
{"action":"live_lookup","actor":"live.places","utc":"20260820T231500Z","run_id":"a1b2c3d4e5f6",
 "payload":{
   "provider":"google-maps-platform","api":"places.searchNearby",
   "request":{"h3_cell":"8929a1b2c3dffff","radius_m":1200,
              "included_types":["hospital","school","fire_station"],
              "fields":["id","displayName","location","primaryType"]},
   "response_sha256":"4f3a…","n_results":7,
   "license":"third-party-restricted","verifiability":"re-derivable",
   "retention":"not-retained","attribution":"Google"}}
```

Re-derivation needs two things, and the project owns both: the **request**, which is entirely
ours, and the **response hash**, which is a digest and not content.

**Place IDs are deliberately absent from this record.** Two reasons, in order of weight:

1. *Legal caution.* The terms permit storing place IDs indefinitely. Permission to **store** is
   not obviously permission to **redistribute** in a public artifact, and that is not a
   judgment this design should make silently. The safer side is the default until the owner
   confirms otherwise (§11.2).
2. *They are unnecessary.* Re-derivation replays the **request**; place IDs are part of the
   **response**. Omitting them costs the verification story nothing.

Place IDs are still stored locally, which the terms permit, because the project's own joins
need them. They simply do not enter the published record.

Taking the licence seriously produced a smaller, cleaner design than ignoring it would have.
That is the paper's point, and it is worth stating in exactly that order: the constraint
improved the mechanism.

## 7. Adapter boundary

New package `src/geosteward/live/`, following the repository's existing convention of logic in
`src/geosteward/` and entry points in `scripts/`, and `gateway/llm.py`'s stdlib-only,
no-SDK-lock-in style:

| File | Responsibility |
|---|---|
| `base.py` | `LiveSource` protocol and `LiveResult(reference_ids, response_sha256, display_payload, n_results)`. Each source declares `license`, `verifiability`, `attribution`, `retention`. |
| `places.py` | Real Places adapter over `urllib`. |
| `grounded.py` | `GroundedSource` protocol and `GroundedResult(text, citations)`, classified `cited-only`. Real Gemini adapter behind an env var. |
| `fake.py` | Deterministic fakes for both protocols. |
| `record.py` | Recorder that reads **only** the non-content fields of a result. |

`display_payload` is returned to the caller for immediate rendering and **never written to
disk**. The recorder enforces this by construction: it accepts a `LiveResult` and reads only
the fields listed in the record schema. §9 makes that a tested property rather than a promise.

## 8. Claim post-check: a second citation form

Answers currently cite `[artifact:HASH]`. Non-retainable sources get `[live:REFID]`, and the
post-check gains one rule:

> An answer containing any `[live:…]` citation must also contain at least one `[artifact:…]`
> citation.

That is "cited-only cannot stand alone" in computable form, and it composes with the
citation-by-default rule already in `check_claims`. In the UI a `[live:]` chip renders
distinctly — "re-derivable, not retained" — with Google attribution attached.

## 9. Testing

The load-bearing test is a **property test on the recorder**: seed a fake source with poison
strings in `display_payload` (fabricated place names, phone numbers, ratings) and assert none
of them appear anywhere in the written record. This converts "the audit record cannot contain
restricted content" from an intention into an enforced property — which, after the
publication-boundary incident, is the distinction this project cares about most.

Also:

- `license: third-party-restricted` can never be published; `verify` catches a planted
  Google-derived file under `events/`.
- Re-derivation: the same request twice against the fake yields the same hash; a changed
  response yields a different hash and is reported as drift, not as an error.
- Post-check: `[live:]` alone is refused; `[live:]` alongside `[artifact:]` passes.
- Policy: `damage_assessment` with only `re-derivable` support is denied; `facility_context`
  at tile resolution with `re-derivable` support inside an AOI is allowed.
- Attribution: any surface rendering Google content carries the required attribution.

## 10. Dependencies and blockers

| # | Item | Effect |
|---|---|---|
| 1 | **GMP API key and billing project** | Owner has none yet but expects to obtain one. Everything except the live call is buildable and testable now; the real call sits behind an env var, and the measured numbers go into this document once it runs. Keys never enter the repository or a public build. |
| 2 | **Gateway hardening becomes a prerequisite** | A keyed API in a public demo is a billing-abuse surface, the same class of risk as the unhardened gateway. The audit record also requires writing a file, which a browser cannot do. So the mechanism lives in the gateway, and the public demo cannot carry it until the gateway has an origin allowlist, rate limiting, and log redaction. Until then the app declares the panel unavailable rather than substituting something keyless. |
| 3 | **Grounding availability** | Place, area, and review summaries are Generally Available. Routing and Search-Along-Route are Private Preview and require application. The Maps Agentic UI Toolkit is Experimental and requires application. This design depends on none of the gated features. |

Blocker 2 is a real change of ordering: gateway hardening was the one deferred item carrying
genuine risk, and it is now also on the critical path for this work.

## 11. Open decisions

Recorded rather than decided, because each changes the work materially.

**11.1 Should `facility_context` be an agent purpose at all?**
The alternative is to keep Places strictly as a planner-side map overlay and out of the
question-answering path. That is narrower and lowers the surface where a live source could
influence a claim, at the cost of the resident-facing "what critical facilities are near me"
answer, which is one of the more genuinely useful things this data enables. *Recommendation:*
include it, because the policy rules constrain it properly and the resident use case is real.

**11.2 Should place IDs appear in the published record?**
§6 omits them out of caution. Including them would let a reader see which facilities were
found without holding a key, which is a real gain in transparency. This needs a reading of the
terms on redistribution, not a technical decision. *Recommendation:* leave them out until
confirmed; the verification story does not need them.

**11.3 Gateway-first, or an interim in-memory browser version?**
Gateway-first is coherent and matches every other stance in the project, but delivers nothing
demonstrable before 2026-09-04. An interim browser-side version with a referrer-restricted key
and an explicitly session-only, non-persistent record would show the idea sooner — at the cost
of the audit record not persisting, which is the mechanism's whole point. *Recommendation:*
gateway-first; the paper can describe and test the mechanism without a public demo of it.

## 12. Out of scope

- **The basemap stays MapLibre GL + OpenFreeMap.** Keyless and offline-capable is a design
  property the paper claims; trading it for a keyed basemap would spend a real virtue on
  cosmetics. Swapping it is the most conspicuous possible Google integration and close to the
  least valuable.
- Photorealistic 3D Tiles, Aerial View, and the Maps Agentic UI Toolkit. The Toolkit is
  interesting but would generate map views that do not trace to hashed artifacts, which cuts
  against the property the app exists to demonstrate.
- **Street View** as a substitute for Mapillary. The CrossViewGate line uses Mapillary because
  it is redistributable; Street View imagery cannot be retained. Street View can only ever be a
  live viewer beside the retained evidence, never in place of it. Deferred, and worth stating
  plainly when it lands.
- **Routes API for budget-constrained inspection routing.** Genuinely valuable — the README
  lists inspection routing as not implemented, and Track A asks for decision relevance — but it
  is a decision-support feature, not a traceability mechanism. Deferred to the 2026-11-03
  finalist-demo push and tracked in `STATUS.md`.
- Air Quality (wildfire smoke, relevant to Eaton) and Elevation (surge and flood, relevant to
  Ian and Milton). Both are real missing hazard dimensions and both fit the `re-derivable`
  regime this design establishes, so they are cheap follow-ons rather than part of the first
  spec.
