# GeoSteward v1 — Project Status

**Updated:** 2026-08-23 · **Target:** [OASIS @ ACM SIGSPATIAL 2026](https://rsvp.withgoogle.com/events/oasis-2026/) Track A
**Key dates (AoE):** Short Paper & Code Submission **2026-09-04** · Finalist Notification 09-20 · Camera-Ready 10-09 · Finalist Presentation & Demo 11-03
**Event portal:** https://rsvp.withgoogle.com/events/oasis-2026/ — the authoritative source for
dates, the Track A brief, and the code-submission mechanism (login required; see blocked item 5).

Roadmap: five sequential plans under [`docs/design/plans/`](design/plans/), all derived from the
[design spec](design/specs/2026-08-19-geosteward-design.md).

## ✅ Done

### Plan 1 — Foundation (2026-08-19)
- Package renamed `disasterpilot` → `geosteward` (v1.0.0.dev1); Bavi case archived under
  `events/archive/` (append-only, full git history preserved).
- **Steward Harness core** landed: outcome-validity checks (CRS assertions, join
  integrity, bounds, mandatory uncertainty), append-only audit log + SHA-256 hashing of
  every registered artifact, and a declarative policy engine (ordered rules, first match
  wins, default deny) with **construction-time validation** — an unknown match key or a
  malformed rule fails loudly at load, never silently broadens authorization.
- Canonical [`policy_v1.yaml`](../src/geosteward/harness/policy_v1.yaml) with a
  cell-by-cell matrix test; pipeline stages (including failures) write audit records.

### Plan 2 — Tier-1 Watch (2026-08-19)
- Four keyless US connectors: USGS earthquakes, NWS alerts (paginated, fail-closed on
  page-cap overflow), NHC tropical cyclones, NIFC/WFIGS wildfires (fails closed on
  ArcGIS error envelopes instead of reporting "zero hazards").
- Fail-closed national watch product with harness checks and declared unknowns; per-source
  audit; gzip append-only snapshots.
- **Live loop is running:** hourly GitHub Actions publish to the
  [`live-data`](https://github.com/rayford295/GeoSteward/tree/live-data) branch —
  `live/products/national_watch.geojson` + `watch_status.json`. Verified end-to-end in CI
  (4/4 sources ok; ~970 live features at last run).
- Test suite: **71 tests green**; every task independently reviewed, final whole-branch
  review + fix wave applied.

### Plan 3 — Eaton deep case, first cut (2026-08-20)
- **Dataset registry built** on the owner's workstation
  (`disaster-dataset-Yifan-all/_registry/`): unified profiles for all 8 local disaster
  datasets, canonical `human_damage_perception` label crosswalk, and SHA-256 checksums
  for **134,272 files (~33 GB)** — full provenance for every image the deep cases touch.
- **`events/eaton-2025/` committed**, built by `scripts/build_eaton_case.py` through the
  Steward Harness (all checks pass on real data, fail-closed, audited):
  - Tier-2 exposure: 18,428 CAL FIRE DINS structure points → **265-cell H3 r9 damage
    grid** with per-severity counts, destroyed rates, and mandatory uncertainty
    (`n_unassessed`, `low_n`); parcel-level source registered as a
    resolution-capped lineage artifact, **never served — enforced by the
    distribution plane and a CI gate on the assembled site**, after it reached
    the public site on 2026-08-20 (see
    [`incidents/2026-08-20-publication-boundary.md`](incidents/2026-08-20-publication-boundary.md)).
  - Tier-3 evidence: 2,244 cross-view matched samples → **109-cell reliability-gated
    coverage grid** (`match_quality ∈ {good, usable}`); the `damaged_repairable`
    class (n=30) is declared as lacking statistical power, not hidden.
  - Dossier `event_record.json` with declared unknowns; registry profiles frozen under
    `snapshots/registry/` so every cell traces to a hashed dataset state.
- Test suite now **81 tests green** (new `test_deepcase_dins.py`); CI installs the
  `deepcase` extra (`h3`).

### Plan 3 — Milton deep case + Eaton SVI join (2026-08-20)
- **`events/milton-2024/` committed** (`scripts/build_milton_case.py`), two AOIs, one
  harness — the cross-hazard-transfer claim in working code:
  - Evidence: 2,556 Bi-Temporal labeled pairs → 15-cell H3 r9 grid at Horseshoe Beach,
    with the honest attribution caveat **declared per feature**: post imagery is
    2024-season cumulative (Debby + Helene + Milton) — damage is NOT attributable to
    Milton alone.
  - Exposure: 5,618 Pinellas County H3 r9 cells with county debris volumes
    (VolCD/VolVG) + Milton wind/rain covariates from `Rayford-AI/debris-estimate`;
    upstream CSV frozen (gzip) with sha256.
  - GenDisasterSVI exclusion is now **auditable**: its registry profile
    (`generated_excluded`) is frozen into the event's snapshots, and the dossier lists
    it under `excluded_sources` with the evidence.
- **Eaton SVI × exposure join** (`scripts/build_eaton_svi.py`): 265 damage-grid cells
  → 20 Census 2020 tracts (TIGERweb captured) → CDC SVI 2022 ranks attached, 0 cells
  missing; downscaling approximation declared per feature. The audit log also preserves
  a **real fail-closed catch**: an over-strict join assertion (envelope tracts vs. burn
  tracts) was rejected by the harness and corrected — quotable in the paper.
- Test suite **89 tests green** (new `test_deepcase_grids_svi.py`).

### Plan 4 — PWA first cut (2026-08-20)
- **`app/` committed**: React + Vite + MapLibre GL + `vite-plugin-pwa` (installable,
  offline-caching), OpenFreeMap basemap (no keys). `npm run dev` / `npm run build`;
  deep-case artifacts are vendored from `events/` at build time (`sync-artifacts`),
  so the app always serves exactly the committed, hashed products.
- **Both deep cases fully displayed**: 5 layers — Eaton damage grid, Damage × SVI
  priority, cross-view evidence coverage; Milton street-view evidence (Horseshoe
  Beach) and Pinellas debris volumes.
- **Planner mode**: damage ↔ social-vulnerability trade-off slider re-weights tile
  priorities client-side (feature-state, instant); top-10 priority list; every slider
  move is audit-logged (locally until the gateway ships, and it says so).
- **Resident mode**: Census-geocoder address search → plain-language dossier card;
  outside the deep-case AOIs it answers "outside the evaluated competence"; declared
  unknowns render with the same prominence as findings.
- **Accountability in the UI**: validity badges (live check counts from the committed
  audit logs), lineage viewer (manifest rows with agents/hashes/inputs), mandatory
  uncertainty shown per tile; Tier-1 live watch renders a declared-unavailable badge
  while the repo is private (graceful degradation, not a fake layer).
- CI: new `app-build` job (Node 22, `npm ci && npm run build`).
- Not yet: PMTiles/vector-tile pipeline (debris layer ships as 5.8 MB GeoJSON — fine
  for now), Playwright smoke tests, agent chat (Plan 5).

### Plan 4 — deployment + third deep case (2026-08-20)
- **Live site:** https://rayford295.github.io/GeoSteward/ — landing page at root
  (content refreshed from the Bavi narrative to the current three-case state), PWA at
  `/app/`, and `/live/` republished hourly (`:40`, trailing `live.yml` at `:23`) via
  the new `deploy-pages` workflow — the Tier-1 national watch layer works publicly
  while the repo stays private. Pages switched from legacy (main/docs) to workflow.
- **Hurricane Ian 2022 deep case** (`events/ian-2022/`, `scripts/build_ian_case.py`):
  886 reliability-gated matched samples → 190-cell evidence grid (Fort Myers AOI) +
  4,121 CVIAN street-view positions → 413-cell **density-only** layer (no verifiable
  per-point severity link exists, so no damage labels are claimed — candor over
  coverage). Third event, second hazard, same harness; in the app's layer catalog.

### Plan 5 — agent gateway, first cut (2026-08-20)
- **Steward middleware** (`src/geosteward/gateway/`): policy pre-check (reusing
  `policy_v1.yaml`, first-match-wins, default-deny) → evidence retrieval from
  manifest-listed artifacts only (each fact tagged with its SHA-256-derived artifact
  ID) → LLM generation → **claim post-check** (≥1 citation, no fabricated IDs, every
  numeric sentence cited, no parcel statements; up to 3 attempts then fail-closed
  refusal) → full audit. Deterministic code classifies purpose/resolution — the LLM
  never decides its own authorization.
- **Provider-agnostic LLM client** (stdlib, OpenAI-compatible): local **Ollama +
  gpt-oss:20b** by default (verified on the owner's RTX 3090: 100% GPU, ~154 tok/s);
  any hosted provider is a `STEWARD_LLM_*` env-var change. No Gemini key required for
  development or adversarial evaluation.
- **Live verification against the real model** (`scripts/ask_steward.py`): planner
  damage question on a hot Eaton tile → fully cited quantitative answer (3 artifacts);
  resident safety question → plain-language cited answer via `allow-exposure-in-aoi`;
  resident damage question → `deny-resident-damage-assessment`; parcel question →
  `deny-parcel-any-role`; post-check caught and refused uncited drafts in testing —
  live fail-closed catches, preserved in the audit log.
- **Adversarial test suite** (`tests/test_gateway_steward.py`, 20 tests): out-of-AOI,
  fabricated citations, uncited numerics, parcel elicitation, LLM outage, retry
  repair, audit completeness. Suite total: **109 tests green**.
- Thin FastAPI skin (`gateway/main.py`, `.[gateway]` extra) for Cloud Run later;
  Gemini/GCP now needed only for the hosted judge-facing deployment, not for Plan 5
  functionality.
- **PWA chat panel wired to the gateway** ("Ask the steward", both modes): role
  follows the mode switch, location follows the map center, citations render as
  artifact chips, and all four gateway response types render as themselves —
  cited answer, rule-ID refusal, declared no-evidence, declared outage (with the
  command to start the gateway). Endpoint configurable (default
  `http://localhost:8080` — browsers treat localhost as a trustworthy origin, so
  even the deployed Pages app can talk to a locally running gateway). Verified
  end-to-end over HTTP: health, CORS preflight, refusal, and a cited quantitative
  answer through gpt-oss:20b.

### Correctness pass (2026-08-20)

Four defects that made the system state something untrue, found by auditing the
deployed site rather than the code:

- **Publication boundary.** A parcel-level DINS source was live on Pages. The harness
  had a claim plane and no distribution plane, so the file was published without
  violating a rule — nothing ever claimed it. Full account in
  [`incidents/2026-08-20-publication-boundary.md`](incidents/2026-08-20-publication-boundary.md).
  Public surface went from 30 files to 16.
- **Validity badge.** Rendered "✓ 9 checks passed" for a stage whose successful run had
  six checks and whose earlier run failed one. Now reports the latest run and keeps
  superseded runs visible; `AuditLog` stamps a `run_id` so new logs carry their own
  grouping.
- **Claim post-check.** Required citations only on sentences containing a digit, so
  "Your neighborhood was not significantly affected." passed uncited. Inverted to
  citation-by-default with a closed exemption set; acceptance over 13 representative
  drafts went 9/13 → 7/13 (three uncited assertions closed, one false positive fixed).
- **Resident lookup.** 156 of Eaton's 265 evaluated tiles were reported as "outside the
  evaluated deep-case areas" because the grid map was keyed by event and the narrowest
  layer won. Coverage is now the union across layers, and `not_covered` is distinguished
  from `unknown` — an unreadable layer no longer produces a confident negative.

A fifth, found on 2026-08-21 while regenerating the allowlist on the maintainer's
workstation:

- **Publication plan order depended on the filesystem, not the policy.** The allowlist is
  generated and CI regenerates it to diff against the commit, so its bytes must be a
  function of the distribution policy alone. They were not: `plan_publication` sorted
  `Path` objects, and `PurePath` ordering case-folds on Windows and does not on POSIX. Two
  registry profiles differing only in case swapped places between the workstation and CI,
  so regenerating on Windows failed the `plan --check` gate on a difference that meant
  nothing — and a gate that fails for cosmetic reasons is a gate people learn to
  override. Ordering is now by the POSIX relative path string everywhere an ordering
  reaches a committed file.

### Accountability for non-retainable evidence (2026-08-21)

Design: [`design/specs/2026-08-20-non-retainable-evidence-design.md`](design/specs/2026-08-20-non-retainable-evidence-design.md)
(§11 rulings and §13 implementation notes). Investigating Google Maps Platform surfaced
a structural problem worth more than the capabilities: GMP terms forbid retaining Maps
Content, while GeoSteward proves traceability by hashing and freezing every input. So —
**when you are contractually forbidden from retaining the evidence, what makes a claim
derived from it accountable?**

- **`verifiability`, a third axis in the claim plane**, orthogonal to the tier ladder.
  Tier encodes how fresh and deep the evidence is; verifiability encodes what a *reader*
  can do to check it: `retained` > `re-derivable` > `cited-only`, totally ordered, with
  **weakest-link** semantics — a claim is no more verifiable than its weakest support.
  Damage assessment now requires retained evidence by rule. Tile-level
  `facility_context` inside an AOI may use a re-derivable source. Nothing permits
  `cited-only`: it matches no allow rule and the fail-closed default carries the
  non-deterministic regime without a rule being written for it.
- **`license`, a third attribute in the distribution plane**, required on every artifact
  class. The other two record what *this project* judges safe to serve, and a third
  party's terms are not ours to judge. `third-party-restricted` is denied publication
  ahead of every other rule; the value set is validated at load, because
  `third-party-restrcited` would match no deny rule and publish the file.
- **The core result: `events/live_evidence.jsonl` is publishable because it holds no
  content.** It carries the request — entirely ours, since we chose the cell, the radius
  and the field mask — plus a response sha256, a count, and the source's own licence and
  retention declarations. A reader with their own key replays the request and compares
  digests; drift is reported as drift (the provider's data moved), not as failure. Place
  IDs are deliberately absent (owner ruling, §11.2). The payload is built from a named
  key list and asserted against it on every write, and the request must name an
  `h3_cell` — a record classified at tile resolution cannot carry a point.
- **`src/geosteward/live/`**: `base.py` contracts (content quarantined from attestation;
  `GroundedResult` has no digest field, because hashing non-reproducible prose would
  look like an anchor and hold nothing), `places.py`, `grounded.py`, `fake.py`,
  `record.py`.
- **The gateway serves it**: policy decides before anything is fetched, so an
  unauthorized question never reaches a third party — no billing surface, no disclosure.
  The lookup is attested before it is used. A source configured without a recorder is
  refused outright. `[live:HASH12]` is a second citation form, and an answer citing one
  must also cite an `[artifact:]` — "cited-only cannot stand alone", made computable.
- **The model is given counts, not names** (`hospital=1, fire_station=1 within 1200 m`).
  Retention and onward disclosure are different questions, and a hosted model endpoint is
  onward disclosure. Not in the original design; see §13.2.
- **The app renders the difference**: a live chip is visually distinct and says
  "re-derivable, not retained"; the answer reports its own weakest-link verifiability;
  attribution comes from the gateway's field so the app cannot show the content while
  forgetting the credit.
- Test suite **212 Python tests + 37 app tests green**, led by a containment property
  test: a fake source is seeded with content of exactly the kinds the licence forbids
  warehousing, the recorder is driven for real, and the bytes on disk are searched for
  every one of those strings. After the publication-boundary incident, "the record cannot
  contain restricted content" is not left as an intention.
- **Not done, and load-bearing:** neither live API call has ever run — there is no GMP
  key, so both adapters are tested against an in-process stub, which establishes this
  code's behaviour and nothing about Google's. `events/live_evidence.jsonl` therefore
  does not exist yet outside tests.

### Documentation — design landed, content not written (2026-08-23)

- **Design records moved** from `docs/superpowers/{specs,plans}/` to
  [`docs/design/`](design/). The old segment was named after the authoring toolchain,
  which means nothing to a reader and reads as a vendor artifact in a submission. Two of
  the nine references fixed were in *code* — a docstring in
  [`src/geosteward/live/__init__.py`](../src/geosteward/live/__init__.py) and a comment in
  [`policy_v1.yaml`](../src/geosteward/harness/policy_v1.yaml) — the same decay that left
  `docs/architecture.md` pointing at `src/disasterpilot/`.
- **OASIS event portal linked** from this file, `README.md`, and
  [`track_a_alignment.md`](track_a_alignment.md). It was previously a bare unlinked string
  in one place.
- **Bilingual manual: spec and plan committed, no content yet.**
  [Spec](design/specs/2026-08-23-bilingual-manual-design.md) ·
  [plan](design/plans/2026-08-23-bilingual-manual.md). Thirteen files under `docs/manual/`,
  English with a Chinese restatement per subsection, plus `scripts/manual_anchors.py` to
  make cited paths checkable in CI. Fourteen tasks; **none executed**. Tasks 1–4 form a
  coherent stopping point if the work is interrupted.
- The manual's purpose is partly remedial: `docs/architecture.md` and
  `docs/methodology.md` contradict the current architecture, and the plan retires both
  (Task 14) *after* their surviving content is absorbed into chapters 02 and 06. Until
  that task runs, the contradiction below stands.

## 🔜 Next (not blocked)

- **Execute the bilingual-manual plan** ([plan](design/plans/2026-08-23-bilingual-manual.md)).
  Start with Task 1 — the anchor gate has to exist before the content it gates.

- Surface `watch_status.json` in the map UI: source health, staleness, and the skipped
  features it already declares. The product is published; the app does not read it.
- Citation click-through: resolve an answer's `[artifact:…]` id to its manifest row,
  inputs, and check results.
- Gateway hardening before any hosted deployment — origin allowlist, rate limiting,
  and coordinate/question redaction in the audit (`gateway/main.py` defaults CORS to
  `*`, and `steward.py` records exact lat/lon and the verbatim question). **Now also a
  prerequisite** for the Google Maps Platform work below: a keyed API in a public demo
  is the same class of billing-abuse surface, and the live-evidence audit record has to
  be written server-side.
- Persist planner adjustments past the session.
- Deferred from that design and worth doing for the 2026-11-03 demo rather than the
  paper: **Routes API for budget-constrained inspection routing** (the README lists
  inspection routing as not implemented, and Track A asks for decision relevance), plus
  **Air Quality** (wildfire smoke, Eaton) and **Elevation** (surge and flood, Ian and
  Milton) — two real hazard dimensions currently absent, both fitting the `re-derivable`
  regime once it exists.

## 🚧 Blocked / needs the project owner

| # | Item | Needed for | Notes |
|---|------|-----------|-------|
| 1 | **Hosted LLM endpoint** | Public chat demo | The gateway is provider-agnostic over the OpenAI-compatible shape (`STEWARD_LLM_BASE_URL`/`_MODEL`/`_API_KEY`); local Ollama works today. A hosted endpoint is needed only for a public demo, and not before the gateway hardening above. |
| 2 | **Google Cloud project** (Cloud Run enabled) | Gateway deployment | Free tier sufficient; needed before the 11-03 finalist demo, not necessarily before 09-04. |
| 3 | ~~**Raw imagery transfer**~~ **RESOLVED 2026-08-20** | Plan 3 evidence tier (full depth) | The full collection was located on the owner's workstation (`Desktop/disaster-dataset-Yifan-all`, ~33 GB): DINS points + 19,780 attachment photos, NOAA Altadena orthoimagery, EATON/IAN matched sets, Bi-Temporal pairs. All registered and SHA-256-hashed in `_registry/`; image-level evidence demos are now possible. Remaining sub-question: where to host raw imagery for judges (HF datasets, following the Bi-Temporal precedent). |
| 4 | ~~**GenDisasterSVI provenance ruling**~~ **RESOLVED 2026-08-20** | Whether Milton GenDisasterSVI may be used as evidence | Street imagery: **excluded** — `dataset.csv` source paths reference `experiment2_ip2p` (InstructPix2Pix), confirming model-generated. The 2,555 `post_sat` satellite images: **owner confirmed real acquisitions (2026-08-20)** — usable as evidence, recorded in the registry profile (`component_tiers`) and the Milton dossier. The Bi-Temporal set remains the street-view evidence source. |
| 5 | **OASIS submission portal details** | 09-04 submission | Exact paper format/page limit and code-submission mechanism from the event portal. |
| 6 | **Repository visibility decision** | Judge access + PWA data path | Both repos are currently **private**. Judges reviewing the code, and the PWA fetching `live-data` via `raw.githubusercontent.com`, require public visibility. The timing of flipping to public is the owner's call (it also interacts with prior-disclosure considerations the owner is managing); the fallback for a private demo is token-gated access or copying products into the Pages tree. |

## Known limitations (tracked, not blocking)

- NWS zone/county alerts without polygon geometry are counted but not displayed
  (declared in `watch_status.json`); zone-centroid resolution is a Plan 4 candidate.
- Legacy typhoon modules (`sources/zj_typhoon.py`, `hazards/typhoon.py`) remain until
  Plan 3 rewires the pipeline agents to the US connectors, then retire to the archive.
- `docs/architecture.md` still describes the pre-rework pipeline.
- Run grouping in logs written before `run_id` existed is recovered from the check
  sequence (a repeat of a run's first check marks a restart). Those logs are
  append-only and are not rewritten to suit the reader.
- The published manifests redact absolute workstation paths to `<workstation>`; the
  sha256 remains the verifiable anchor. The repository copy keeps the full paths.
- Live snapshot growth is mitigated by gzip; an archive/rotate policy will be decided in
  the Plan 4 design before consumer URLs freeze.
