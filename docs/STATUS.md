# Ray Resilience v0.1 — Project Status

**Updated:** 2026-09-03 · **Target:** [OASIS @ ACM SIGSPATIAL 2026](https://rsvp.withgoogle.com/events/oasis-2026/) Track A
**Key dates (AoE):** Short Paper & Code Submission **2026-09-04** · Finalist Notification 09-20 · Camera-Ready 10-09 · Finalist Presentation & Demo 11-03
**Event portal:** https://rsvp.withgoogle.com/events/oasis-2026/ — the authoritative source for
dates, the Track A brief, and the code-submission mechanism (login required; see blocked item 5).

Roadmap: five sequential plans under [`docs/design/plans/`](design/plans/), all derived from the
[design spec](design/specs/2026-08-19-geosteward-design.md).

## ✅ Done

### Rename: GeoSteward → Ray Resilience (2026-09-03)
- Product display name is **Ray Resilience** ("Resilience intelligence for every place." /
  面向每一个地点的灾害韧性智能), the assistant is **Ray** ("Ask Ray"), the accountability
  engine keeps its name, **Steward Harness**. Brand hierarchy: Rayford AI → Ray Resilience →
  Ray; repository `rayford295/ray-resilience`. Version renumbered to v0.1 (`0.1.0.dev1`):
  the system is a v0, and v0 is not part of the brand name.
- Renamed in README, CITATION, landing page, PWA (title, header, manifest, chat panel),
  gateway system prompt, user-agent strings, manual, and the paper (now
  `paper/ray-resilience-oasis2026.tex`, title *RAY: Resilience Assistant for You — An Accountable
  GeoAI System for Place-Based Disaster Intelligence*; RAY is the paper's acronym, Ray Resilience the product). The Python package stays `geosteward`
  to avoid a v0 code migration; dated design records and the incident report keep their
  historical wording; hashed artifacts under `events/` are untouched.

### Plan 1 — Foundation (2026-08-19)
- Package renamed `disasterpilot` → `geosteward` (then v1.0.0.dev1; renumbered 0.1.0.dev1 with the 2026-09-03 rename to Ray Resilience); Bavi case archived under
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
  [`live-data`](https://github.com/rayford295/ray-resilience/tree/live-data) branch —
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
- **Live site:** https://rayford295.github.io/ray-resilience/ — landing page at root
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
- **PWA chat panel wired to the gateway** ("Ask Ray", both modes): role
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
Content, while Ray Resilience proves traceability by hashing and freezing every input. So —
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

### Documentation — design landed, then written and closed out (2026-08-23 → 2026-08-24)

- **Design records moved** from `docs/superpowers/{specs,plans}/` to
  [`docs/design/`](design/). The old segment was named after the authoring toolchain,
  which means nothing to a reader and reads as a vendor artifact in a submission. Two of
  the nine references fixed were in *code* — a docstring in
  [`src/geosteward/live/__init__.py`](../src/geosteward/live/__init__.py) and a comment in
  [`policy_v1.yaml`](../src/geosteward/harness/policy_v1.yaml) — the same decay that had
  left docs/architecture.md pointing at src/disasterpilot/.
- **OASIS event portal linked** from this file, `README.md`, and
  [`track_a_alignment.md`](track_a_alignment.md). It was previously a bare unlinked string
  in one place.
- **Bilingual manual written: thirteen files, 4,726 lines** (`wc -l docs/manual/*.md`).
  [Spec](design/specs/2026-08-23-bilingual-manual-design.md) ·
  [plan](design/plans/2026-08-23-bilingual-manual.md). [`docs/manual/`](manual/), English
  with a Chinese restatement per subsection, gated by
  [`scripts/manual_anchors.py`](../scripts/manual_anchors.py) in CI so a cited path that
  stops resolving fails the build instead of aging silently. All fourteen tasks executed.
- **The two documents the manual superseded are now retired** (Task 14, 2026-08-24):
  docs/architecture.md and docs/methodology.md contradicted the current architecture.
  The former is deleted outright; the latter is archived at
  [`docs/archive/methodology-bavi.md`](archive/methodology-bavi.md) with a superseded-by
  header — both only after their surviving content was absorbed into
  [`02`](manual/02-harness-outcome-audit.md) and
  [`06`](manual/06-data-and-evidence.md). The contradiction this previously left under
  Known limitations no longer applies and has been removed from that section.

### Area query — draw a rectangle and ask about it (2026-08-26)

Design: [`design/specs/2026-08-25-area-query-design.md`](design/specs/2026-08-25-area-query-design.md) ·
plan: [`design/plans/2026-08-25-area-query.md`](design/plans/2026-08-25-area-query.md).
Prompted by `terraquery.ai` and a Frankfurt chat-with-your-map demonstration; only the second
was a fit, because TerraQuery is an ingestion product whose answers cite nothing.

A planner shift-drags a rectangle, sees how many evaluated tiles it contains **before** asking,
and gets an answer that covers the selection and says which parts of it were evaluated.
`EvidenceStore.evidence_for_area` walks the committed grids across every intersecting event;
`Steward.answer` takes a point **or** an area, exactly one, and returns the tiles it used;
`/ask` enforces the same either-or at the transport. The app highlights what comes back.

Four decisions shaped it, and the reasoning is the part worth keeping:

- **Coverage fraction stays out of the claim plane.** A match key like `aoi_coverage_at_least`
  would invent a threshold somebody has to defend, and would confuse the two questions the
  planes exist to separate. `in_aoi` stays boolean and widens to "intersects";
  [`policy_v1.yaml`](../src/geosteward/harness/policy_v1.yaml), `PolicyRequest`, and
  `_KNOWN_MATCH_KEYS` are untouched. A selection intersecting nothing is still refused by
  `deny-outside-aoi` — no new rule was needed, and two policy-matrix rows now pin that.
- **Enumerate the grids, not the polygon.** `h3.polygon_to_cells` over a continent-sized
  rectangle would force a maximum-selection-area cap. Iterating the 6,875 committed cells and
  testing each centre removes the problem instead of capping it, and the bound is structural:
  a selection cannot match more cells than exist. A subset property test pins it.
- **An area sees every intersecting event, and statistics are never merged across them.**
  Eaton damage and Milton debris measure different things; one count spanning both would be a
  fabricated quantity.
- **A `facility_context` question over an area is a declared capability gap**, not a
  centre-of-the-rectangle approximation — folding a selection into a point rewrites the
  question. It fires on request shape, not on whether a live source is configured.

Suite: **266 Python tests** (262 with `.[deepcase]` alone — four need the optional
`gateway` extra and skip without it, which is why CI now installs it), **44 app tests**.
No new dependencies.

**Known issues, recorded not fixed — the owner's call:**

- **Planner mode now eagerly fetches every view on first paint.** This is the fix for a real
  defect: the header's pre-ask count and the answer's cells walked different input sets, so a
  Milton-AOI selection showed **0** evaluated tiles and returned **5,618**. Loading every view
  closes it, mirroring what resident mode already did for the same reason. The cost went
  unnamed in the prose that argued for it: the default page load goes from roughly 312 KB to
  **~6.7 MB**, dominated by the 5.5 MB Pinellas debris grid. Planner is the default mode, so
  this is every first visit. The PMTiles item under Known limitations is the standing fix.
- **[`11-limits-and-gaps.md`](manual/11-limits-and-gaps.md) names the wrong class**: it
  attributes a path to `EventContext.evidence_for()`, but `evidence_for` belongs to
  `EvidenceStore` ([`context.py`](../src/geosteward/gateway/context.py)); `EventContext` is a
  different class in [`agents/base.py`](../src/geosteward/agents/base.py). Pre-existing.
- **The box-select gesture has no automated coverage.** The drag handling, click suppression,
  and blur cleanup are reasoned, not tested — this repository has no browser interaction
  harness and adding one means dependencies the design forbids. What *is* covered: the
  geometry in [`area.js`](../app/src/lib/area.js) and the suppression predicate in
  [`clickSuppression.js`](../app/src/lib/clickSuppression.js).
- **The audit row now carries the drawn area unredacted**, alongside the exact coordinates and
  verbatim question it already stored. Deliberate: redacting one field of a row already
  recorded here as unsafe to host would make it inconsistent without making it safe. It makes
  the gateway-hardening item below slightly larger.

### Design record — global disaster catalog (2026-08-30)
- **Documentation only, no code.**
  [`design/specs/2026-08-30-global-disaster-catalog-design.md`](design/specs/2026-08-30-global-disaster-catalog-design.md)
  fixes the record schema, hazard vocabulary, region/time conventions, and source-conflict
  rule for a **global, cross-region, cross-hazard, multi-source** catalog over `events/` —
  positioned as the project's core direction rather than a sixth plan, because the harness
  is already general and only the coverage is not.
- Three decisions: identity carries **GLIDE** as a foreign key with `null` where none is
  assigned (never a constructed one); `evidence_tier` and `verifiability` stay **orthogonal**,
  so a bare global registration types honestly as `tier 1 / cited-only` with no new field;
  and the catalog **never merges conflicting source values** — each is kept with its source,
  and the row either names the policy rule that selected one or declares the conflict.
- Consumes the claim plane without amending it: `policy_v1.yaml`, `PolicyRequest`, and
  `_KNOWN_MATCH_KEYS` are untouched. Publication would require a new `event_catalog`
  artifact class, which does not exist yet — so the catalog is fail-closed by absence.
- **Structure global, coverage four events.** Stated in the spec's §3 and in the README's
  what-works table.

### PWA light-theme restyle (2026-09-01)
- The app moved from the dark ops-console palette to a light professional theme
  (off-white ground, white cards, teal accent), prompted by the TDIS portal review
  below. Styling layer only: design tokens in the app's stylesheet plus one
  presentational change — the resident dossier's numeric facts now render as
  stat callouts, each number keeping its qualifier in the same card.
- Every semantic encoding survives in light-tinted form: refusal red, declared-unknown
  amber, validity green, the dashed live-citation chip, the three `verifiability` hues.
  No new fonts and no external requests — the PWA stays keyless and offline-cacheable.
- Verified with headless-browser screenshots at desktop and phone widths, both modes,
  with the geocoder mocked to exercise the dossier; 44 JS tests and the production
  build pass unchanged.
- The landing page followed: teal is now the action/identity color on both surfaces,
  with amber reserved for caution semantics (matching what amber means inside the app),
  a Launch-the-app button in the nav that survives phone widths, and two content
  corrections — the pipeline section no longer describes its five stages as five
  *agents* (the same misdescription that retired the old architecture doc), and the
  stale test count is corrected to the verified 266 in both the landing page and the
  README quickstart.

### App usability pass (2026-09-01)
- Three additions aimed at a first-time visitor, requested by the owner after the
  TDIS review: a **getting-started card** (three one-click steps; dismissal remembered
  per browser, best-effort, reopenable from a header "?"), **example chips** (an example
  address that runs the exact lookup a typed address gets, and role-appropriate example
  questions that fill the ask box), and a **color legend** for the active layer.
- The legend's scale is computed by the same function the map paint now imports
  (a shared lib module), so the legend cannot drift from the fill — a volume layer's
  p95 cap is labeled "N+" and says it is capped.
- **Citation click-through** (previously listed as not done in the README): citation
  chips in an answer are now buttons; clicking one resolves the 12-hex id against every
  event's manifest (backfilled on demand, kept out of the lineage panel's `meta` triple)
  and shows the artifact's provenance — path, event, agent, timestamp, full sha256,
  inputs, notes, with every manifest row shown for a rebuilt artifact. The two empty
  outcomes stay distinct claims: "no manifests loaded" vs "searched and absent"; a live
  citation explains the content-free lookup record instead of pretending to a manifest
  row. App tests 44 → **57** (legend scale, citation resolution); verified end-to-end
  in a headless browser with the gateway and geocoder mocked.

### Dossier reissue — a declared unknown that outlived its resolution (2026-09-03)
- Fixes the most consequential of the ten 2026-08-24 manual findings (below, now
  struck through). Eaton's dossier kept declaring *"social-vulnerability join (SVI x
  exposure) pending"* after `scripts/build_eaton_svi.py` landed the SVI grid on
  2026-08-20, and the gateway fed that line to users as evidence.
- Mechanism, not a hand edit: `src/geosteward/deepcase/dossier.py` `retire_unknown()`
  moves the line to a new `resolved_unknowns` list (resolver path + sha256 + time +
  stage — the record keeps saying what it once could not support and why that
  changed), refuses resolvers that are not registered in the manifest and lines that
  were never declared, and reissues `event_record.json` through `EventContext.write_json`
  so the manifest gains a new row while the old one stays. Readers already take the
  latest row per path. Idempotent on re-run. Manifest and audit log remain append-only.
- `scripts/build_eaton_svi.py` now retires the line itself when it lands the grid, so a
  full rebuild cannot recreate the staleness. `scripts/retire_dossier_unknown.py` is the
  retroactive form for artifacts that landed before that behaviour did and cannot be
  rebuilt on this machine; it was run once, on `events/eaton-2025/` (new dossier sha256
  `bd2c7996a7f9…`, stage `dossier.retire_unknown`).
- Regression guard over the committed events in `tests/test_deepcase_dossier.py`: an
  event with a registered `svi_context_grid` must not declare the join pending, and
  every `resolved_unknowns` entry must point at a registered, on-disk artifact whose
  sha256 matches. Milton's and Ian's "pending" lines stay — both are still true.
- Not changed: the gateway loop in `src/geosteward/gateway/context.py` still cannot tell
  a stale unknown from a current one by itself; the guarantee now rests on stages
  retiring what they resolve plus the guard, and the manual (`11`) says so.
- Also today: `npm audit fix` (one transitive `fast-uri` high, `package-lock.json` only);
  the README and landing quickstart now quote the count the plain
  `python -m unittest discover -s tests` actually produces without the gateway extra.
  Python tests 295 → **301**; app tests 67.

### Paper synced to the shipped system; repo-wide consistency pass (2026-09-02)
- The short paper now describes what is actually deployed: population and facility
  numbers in all three deep cases, the exercised `open-license-attribution` value,
  the one-rule audit redaction, the typed watch and the separate Day-1 outlook
  product, the hardened-but-not-hosted gateway, and the verified counts (295 Python +
  67 app = 362 tests). Still 3 pages + references; owner decisions at the top of the
  `.tex` remain open (authors, emails, format vs. the Track A brief).
- Test counts synced everywhere they are quoted (README quickstart, landing page,
  `track_a_alignment.md`); the README quickstart's skip note now describes the
  gateway-extra dependency instead of pinning a count that drifts.
- `CITATION.cff` added for the software (Yifan Yang; the paper's author list is a
  separate, still-open owner decision). The README's not-done row shrinks to
  releases/CHANGELOG/contributor docs.

### Typed live watch + Day-1 flash-flood outlook (2026-09-02)
- The remaining implementable halves of the TDIS review's tabs, prompted by the owner's
  screenshot walkthrough. Live Weather: the watch layer now renders **per hazard type**
  (color per source class) with one distinction that outranks color — **NWS alerts are
  drawn hollow**, because an advisory about what may come must never look like an
  occurrence; sidebar chips filter types and carry live counts. Infrastructure Status
  and the HSI severity index remain non-adoptions (commercial/partner data; recorded).
- **WPC Excessive Rainfall Outlook connector** (`wpc_ero` — NOAA public domain, keyless,
  same fail-closed ArcGIS pattern as NIFC): Day-1 polygons with the four WPC ordinal
  categories; an unrecognized outlook label is skipped and counted, never guessed into
  a level. Published as a **separate product**, `flood_outlook.geojson`, beside the
  watch — polygons and a forecast, never merged into the point layer, so neither
  borrows the other's meaning. Status lands under its own `flood_outlook` key; a
  failure is recorded and never blocks the watch (injectable connector keeps the
  orchestration tests hermetic). The product carries its own declared boundary:
  outlook only, not observed flooding, no damage conclusions, does not replace NWS
  warnings — and the app renders that sentence beside the legend.
- App: outlook polygons under every point layer (amber → fuchsia by level; not
  starting at green, which under a flood outlook would read as "safe"), a toggle with
  per-level counts and the issue time, and the live-hazards chip row. Verified against
  the real products end-to-end: 864 live features, 7 Day-1 ERO areas including the
  Texas Moderate. Python tests 288 → **295**; app tests 61 → **67**.

### Gateway hardening (2026-09-02)
- The four items the roadmap gated hosting on, landed as code (hosting itself still
  waits on blocked items 1–2):
  - **Fail-closed authorization**: with no `STEWARD_API_TOKEN` configured the gateway
    serves loopback callers only — local dev works out of the box, and network
    exposure can only happen by an explicit decision, never by forgetting one. With a
    token set, `Authorization: Bearer` gates every caller (constant-time comparison).
  - **Per-client rate limiting**: in-memory sliding window (`STEWARD_RATE_LIMIT`,
    default 20/60s), 429 + Retry-After; `X-Forwarded-For` is honored only when
    `STEWARD_TRUST_PROXY=1`, because that header is attacker-writable without a proxy.
  - **CORS** defaults to the local dev origins, never `*`; a public deploy sets
    `STEWARD_CORS_ORIGINS` to the Pages origin.
  - **Audit redaction**, applied as the one-rule whole-audit change the old
    in-code comment insisted on: the `gateway_request` row now stores a point as its
    **H3 r9 cell** (the exact resolution the claim plane caps tile answers at), an
    area's corners rounded to 3 decimals (~110 m), and the question as **sha256 +
    length** — the same verifiable-anchor pattern as the manifests, so a caller can
    prove their question produced a row without the log keeping what a resident
    typed about their own home. Raw coordinates and verbatim text no longer appear.
- Pure-logic policies live in `src/geosteward/gateway/hardening.py` (importable
  without FastAPI); Python tests 279 → **288**. Verified live over HTTP: loopback
  default, 401 without/200 with bearer, 429 with Retry-After, and a redacted
  `gateway_request` row.

### Population exposure layer (2026-09-01)
- Adoption #1 from the TDIS review, pulled forward with the facility layer: the watch
  question TDIS answers per forecast run — *how many people* — answered inside the
  three deep-case AOIs from **2020 Census blocks via TIGERweb** (public domain,
  already in this repo's lineage from the Eaton SVI join). Chosen over Kontur: exact
  decennial counts, no license burden, attributes-only queries (POP100 + block
  centroid), no polygon downloads.
- `scripts/build_population.py` allocates blocks to evaluated H3 r9 tiles by centroid
  containment. **Eaton 46,341 · Ian 5,428 · Milton 772,293** residents assigned; the
  envelope population landing outside evaluated tiles is declared as a total (never
  dropped, never mapped into tiles the event has no evidence for). Fails closed on
  ArcGIS error envelopes and on `exceededTransferLimit` truncation — a partial block
  set would silently undercount. Two declared boundaries per feature: centroid
  allocation, and 2020 vintage = *pre-event population, not presence at event time*.
- Shared `deepcase/aoi.py` now holds the event→grids mapping both the facility and
  population builders import — one AOI definition, no drift.
- App: a "Population (2020 Census)" choropleth per event; a Residents stat card in
  the dossier; and the planner's area selection header now reads
  "N evaluated cells · ~M residents (2020)" from the same tile values the layer
  shows. New artifact class `population_grid` (tile/public/project); allowlist
  19 → 22. Python tests 273 → **279**.

### Critical-facility context layer (2026-09-01)
- Adoption #5 from the TDIS review below, pulled forward at the owner's request. TDIS's
  Infrastructure Status tab shows *live* facility status from commercial feeds; this
  layer deliberately claims the opposite and weaker thing — **presence in OpenStreetMap,
  never operational status** — because that is what open data can support, and every
  feature carries that boundary in its own uncertainty field.
- Pipeline: `scripts/build_facilities.py` derives each event's AOI envelope(s) from grids
  the event has already committed (Milton's two AOIs stay two bboxes — their union would
  cover open gulf), freezes the raw Overpass response (gzip, hashed), fails closed on
  Overpass `remark` truncations and on any point outside its envelope, and emits
  `critical_facilities.geojson` per event: Eaton 27, Ian 79, Milton 200 facilities
  (hospital / clinic / fire_station / police; shelters and schools excluded in v1 —
  OSM tagging for them is inconsistent enough that an extract would understate).
- Governance: `KNOWN_LICENSES` gained a fourth value, **`open-license-attribution`** —
  third-party content whose license *permits* redistribution with attribution (ODbL).
  Two new artifact classes: `facility_context_points` (tile / public) and
  `source_snapshot_odbl` (internal — same audience as `source_snapshot`, separate kind
  so the license attribute never lies even where it is unread). Allowlist 16 → 19 files;
  the Overpass snapshots are correctly denied. No claim-plane change: the agent still
  has no rule authorizing facility claims, so they default-deny.
- App: facility points with per-category colors and a popup carrying name, the
  presence-not-status line, and the ODbL attribution (DOM-built — OSM names are
  third-party text); a layer toggle with attribution; the resident dossier lists
  facilities within 1 km, nearest first, with "layer unreadable", "none recorded"
  (plus "absence from OSM is not evidence of absence"), and results as three distinct
  renderings.
- Tests: Python 266 → **273** (bbox/query/conversion/fail-closed fixtures), app 57 →
  **61** (haversine, proximity, null-vs-empty). Verified headless end-to-end.

### OASIS short-paper draft (2026-09-01)
- **First full draft committed** under `paper/` (ACM `sigconf`, builds locally with the
  repository's TinyTeX via the bundled build script; currently 3 pages + references).
  Structure follows `track_a_alignment.md`: harness (three validity layers +
  `verifiability`), system and the three deep cases, the two self-caught incidents as
  evidence the mechanism works, the test suite as the verifiable evaluation
  environment, related work (autonomous-GIS agents, TDIS, EM-DAT/GDACS), limitations.
  Every number was verified against the repository this session (suite re-run: 266
  Python + 44 app tests; stale counts in the README, landing page, and
  `track_a_alignment.md` corrected to match).
- **Owner decisions before submission** (also flagged at the top of the `.tex`):
  author list and order (Lei Zou is listed from the Yang & Zou abstract — confirm),
  both email addresses are placeholders, and the assumed format (sigconf, 4 pages)
  must be reconciled with the Track A brief behind the event login (blocked item 5).

## 🔜 Next (not blocked)

- **Gateway hosting** (Cloud Run) — the hardening that used to sit here landed
  2026-09-02 (see Done); what remains is the deployment itself, blocked on the GCP
  project and a hosted LLM endpoint (blocked items 1–2). Still the prerequisite for
  the Google Maps Platform work below: a keyed API in a public demo is the same class
  of billing-abuse surface, and the live-evidence audit record has to be written
  server-side.
- Persist planner adjustments past the session.
- **Catalog S0** (from the 2026-08-30 spec): a JSON Schema, a catalog build script under
  `scripts/`, a generated catalog JSONL under `events/` covering the four existing events,
  the `event_catalog` distribution class in `src/geosteward/harness/policy_v1.yaml`, and a
  test asserting a row's `claims_supported` never exceeds what its `evidence_tier` and
  `verifiability` permit. Not started; sequenced after 09-04. (Paths deliberately unwritten
  here: `scripts/manual_anchors.py` resolves every path-shaped span against disk, and a
  roadmap entry must not be spelled like a file that already exists.)
- Deferred from that design and worth doing for the 2026-11-03 demo rather than the
  paper: **Routes API for budget-constrained inspection routing** (the README lists
  inspection routing as not implemented, and Track A asks for decision relevance), plus
  **Air Quality** (wildfire smoke, Eaton) and **Elevation** (surge and flood, Ian and
  Milton) — two real hazard dimensions currently absent, both fitting the `re-derivable`
  regime once it exists.

### Competitive review: TDIS portal (2026-09-01)

Reviewed the [Texas Disaster Information System portal](https://portal.cloud.tdis.io/)
(Texas A&M IDRT / GLO), an operational state platform whose "Impact Forecast" tab is the
closest fielded analogue to our watch layer: flash-flood outlook on H3 hexes, an ordinal
1–5 severity scale, per-run population-exposure estimates, and a county roll-up that
lists only the top two severity classes. Candidate adoptions, all sequenced **after
09-04** and to be re-prioritized against the GMP items above for the 11-03 demo:

1. **Population exposure on the watch layer** — the most decision-relevant gap. Join
   hazard footprints against a static population layer (Kontur Population is CC BY and
   already H3-gridded) at watch-product build time, with declared uncertainty. Fits
   `verifiability: retained`; no key, no service. Ranks **ahead of** the GMP demo items:
   it answers Track A's vulnerability question directly.
2. **A forward-looking outlook layer** — NOAA WPC Excessive Rainfall Outlook is public
   domain and keyless: a Tier-1 connector away from a flash-flood outlook of our own,
   carrying the declared boundary "outlook only — no damage conclusions supported."
   Cheaper first step: render NWS *warnings/watches* (already collected) visually
   distinct from hazards *occurring now*.
3. **High-severity roll-up list** — a client-side "most affected counties/areas now"
   ranking from the existing watch product, with name/FIPS search. TDIS lists only the
   top severities to reduce noise; the same editing choice applies here.
4. **Plain-language ordinal severity labels** in resident mode ("potentially high"
   rather than a bare index), consistent with declared-unknowns phrasing.
5. **Critical-facility exposure context** — HIFLD open data (hospitals, schools) as a
   static, retainable exposure layer inside deep-case AOIs; context, not live status.

Deliberately **not** adopted: real-time infrastructure status (the open data does not
exist; TDIS relies on commercial outage feeds, incompatible with the keyless/verifiable
positioning), and a hosted conversational assistant (TDIS AI confirms the auth + quota
pattern, which is exactly the gateway hardening this roadmap already sequences first).

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
- Run grouping in logs written before `run_id` existed is recovered from the check
  sequence (a repeat of a run's first check marks a restart). Those logs are
  append-only and are not rewritten to suit the reader.
- The published manifests redact absolute workstation paths to `<workstation>`; the
  sha256 remains the verifiable anchor. The repository copy keeps the full paths.
- Live snapshot growth is mitigated by gzip; an archive/rotate policy will be decided in
  the Plan 4 design before consumer URLs freeze.

### Found while writing the manual (2026-08-24)

Ten defects surfaced during the bilingual-manual effort (implementer- and
reviewer-verified, one independently). Recorded here, not fixed here — that
call belongs to the project owner.

- ~~Eaton's `events/eaton-2025/dossier/event_record.json` declares a stale
  unknown — *"social-vulnerability join (SVI x exposure) pending: no
  vulnerability claims yet"* — while
  `events/eaton-2025/exposure/svi_h3_r9_context.geojson` exists with 265
  cells and full `RPL_THEME1`–`RPL_THEME4`.~~ **Fixed 2026-09-03** (see
  "Dossier reissue" under Done): the line now sits in `resolved_unknowns`
  with its resolver's sha256, and a regression test guards every event.
  Milton's and Ian's identical lines are still true (neither has an SVI
  grid) — the fix deliberately does not generalise to them.
- **Most consequential:** `src/geosteward/gateway/context.py:183` feeds
  `record["declared_unknowns"]` into the agent's evidence context, so the
  stale line above ~~is~~ was spoken to real users while the SVI layer is
  published and rendered. The error is conservative — the agent under-reports
  competence rather than fabricating data — but it corrodes the
  declared-unknowns mechanism: if the list can go stale, "not listed as
  unknown" stops meaning "confirmed." **Mitigated 2026-09-03:** the instance
  is gone and stages now retire what they resolve; the loop itself still has
  no freshness check of its own (recorded in the manual's `11`).
- `src/geosteward/harness/publication.py:191`'s `redact()` has no callers
  anywhere, including its own test file. Redaction is performed by
  `app/scripts/sync-artifacts.mjs` from the `redact_workstation_paths` flag
  `publication.py` sets.
- `scripts/manual_anchors.py` misses any path inside a code span that also
  contains whitespace — `_looks_like_path` rejects the whole span on the
  no-whitespace rule, so command-shaped spans silently escape the gate.
- The 134,272-file corpus figure this document and `06` both cite cannot be
  reconciled from committed artifacts: the seven frozen registry profiles
  sum to 130,111 (`n_files_hashed` under `checksums`, summed across
  `events/*/snapshots/registry/*_profile.json`), a gap of 4,161.
- `events/ian-2022/evidence/svi_density_h3_r9_grid.geojson` uses a `content`
  key in `uncertainty`, a shape no other grid uses;
  `check_uncertainty_present` asserts only that the field exists, not its
  shape.
- `src/geosteward/agents/evidence.py`'s `CrossViewEvidence` is instantiated
  only in `tests/test_pipeline.py`; its `.name` `"evidence.crossview"` has
  zero audit-log occurrences. Not to be confused with
  `evidence.crossview_grid` / `evidence.crossview_coverage`, separate
  build-script-local implementations.
- `check_uncertainty_present` passes when `uncertainty` is `None`.
- `docs/design/specs/2026-08-20-non-retainable-evidence-design.md` cites
  gateway/steward.py and gateway/llm.py; the real paths are under
  `src/geosteward/gateway/`. Inside `docs/design/`, which is in
  `SKIP_PATHS`, so the anchor gate does not catch it.
- The anchor-gate CLI tests print to stdout during the suite; this
  repository's convention is pristine test output.
