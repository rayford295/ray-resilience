# Ray Resilience

**Resilience intelligence for every place.** An accountable GeoAI system for
place-based disaster intelligence, by Rayford AI. The assistant you talk to is **Ray**;
the accountability engine underneath is the **Steward Harness**.

AI-powered WebGIS / smartphone app (PWA) for understanding a place's resilience —
what hazards threaten it now, how exposed and vulnerable it is, and what decisions
the evidence actually supports. Entry for
[**OASIS @ ACM SIGSPATIAL 2026**](https://rsvp.withgoogle.com/events/oasis-2026/)
· **Track A: Disaster Resilience & Vulnerability Analysis**.

**Live:** [rayford295.github.io/ray-resilience](https://rayford295.github.io/ray-resilience/)
· [the app](https://rayford295.github.io/ray-resilience/app/)

**Event portal:** [rsvp.withgoogle.com/events/oasis-2026](https://rsvp.withgoogle.com/events/oasis-2026/)
— submission dates, Track A brief, and the code-submission mechanism live behind the
event login. Key dates and their current status are tracked in
[`docs/STATUS.md`](docs/STATUS.md).

**What "a place" means here, precisely.** Hazard monitoring is nationwide: any US
location gets the current Tier-1 watch layer. Exposure, vulnerability, and damage
analysis exist only inside the three deep-case AOIs below, and the app says so
rather than extrapolating — an address outside them is told the location is outside
the evaluated areas, and an address the app cannot yet resolve is told that instead
of being guessed at. Competence is conditional on place, and saying where it ends is
part of the design.

**Where this is going.** The accountability machinery — the two policy planes, the
`verifiability` axis, the hashed append-only manifests — is general; only the coverage
is not. The project's core direction is a **global, cross-region, cross-hazard,
multi-source disaster catalog**: an event-level accountability record that lets the
agent answer *is this place covered, by what evidence, to what depth, and may I keep
it* for somewhere it has never been asked about before. The field does not lack
disaster data — EM-DAT, GDACS, Copernicus EMS, ReliefWeb and the national agencies all
hold it. What none of them carries in the row itself is the thing this project already
computes per artifact: at what resolution a statement is authorised, whether a reader
can check the support, and whether the evidence is ours to redistribute. That gap is
the design in
[`docs/design/specs/2026-08-30-global-disaster-catalog-design.md`](docs/design/specs/2026-08-30-global-disaster-catalog-design.md).
**It is a design, not a capability:** the schema is global from the first row, the
coverage today is four events.

> 🚧 **Rework in progress.** This repository (formerly *DisasterPilot*) is being
> rebuilt around the design in
> [`docs/design/specs/2026-08-19-geosteward-design.md`](docs/design/specs/2026-08-19-geosteward-design.md).
> The previous Super Typhoon Bavi case study is preserved under
> `events/archive/bavi-2026/` — append-only history is a core principle here.

## What works today, and what does not

| | State |
|---|---|
| Tier-1 nationwide watch (USGS, NWS, NHC, NIFC) | Working; refreshed hourly by CI, per-source failures declared not hidden; rendered per hazard type with NWS advisories drawn hollow — an advisory about what may come never looks like an occurrence |
| Day-1 flash-flood outlook (NOAA/WPC Excessive Rainfall Outlook) | Working — the project's first forward-looking layer, kept as a separate product from the watch (polygons and a forecast, never merged into the point layer); carries its own declared boundary: outlook only, not observed flooding, no damage conclusions, does not replace NWS warnings |
| Three deep cases (Eaton 2025, Milton 2024, Ian 2022) | Working; tile-level exposure, SVI, and cross-view evidence |
| Global disaster catalog (cross-region, cross-hazard, multi-source) | **Design only** — record schema, hazard vocabulary, region/time conventions, and the source-conflict rule are fixed in [the spec](docs/design/specs/2026-08-30-global-disaster-catalog-design.md); no `catalog.jsonl`, no schema file, and no global connector exists yet. The seed set is the four events already in `events/` — three US deep cases plus the archived non-US Bavi case |
| PWA, installable, offline-caching | Working |
| Steward Harness: outcome checks, append-only audit, policy pre-check, claim post-check | Working |
| Publication boundary (distribution plane + CI gate) | Working |
| Agent gateway | Working locally against any OpenAI-compatible endpoint (Ollama by default), **hardened but not hosted**: fail-closed auth (no token configured → loopback callers only; `STEWARD_API_TOKEN` gates network clients), per-client rate limiting, CORS defaulting to local dev origins (never `*`), and a redacted audit — a point is recorded as its H3 r9 cell, an area's corners rounded to ~110 m, the question as sha256 + length, never verbatim. The public demo still has no chat backend: hosting waits on a GCP project and an LLM endpoint |
| Area query — shift-drag a rectangle in planner mode and ask about it | Working; split by what needs a backend. Drawing the rectangle and the header's count of evaluated tiles inside it are client-side and work in the public demo. The **answer** goes through the gateway, so it needs the row above: an answer covers only the evaluated tiles the selection actually contains, declares the rest rather than extrapolating, never merges statistics across two events, and highlights the tiles it cited |
| Accountability for non-retainable evidence (`verifiability` axis, `license` attribute, content-free lookup record) | Working and policed in code; **never run against a live API** — there is no Google Maps Platform key, so both adapters are tested against an in-process stub and `events/live_evidence.jsonl` does not exist outside tests. [Design and implementation notes](docs/design/specs/2026-08-20-non-retainable-evidence-design.md) |
| Live-watch source health surfaced in the map UI | Working — the badge reports mapped-of-total, features it could not map, failed sources, and product generation time from `watch_status.json` |
| Citation click-through from an answer to its artifact | Working — a citation chip resolves against every event's manifest and shows the artifact's provenance (path, agent, timestamp, full hash, inputs); "no manifests loaded" and "searched and absent" stay distinct answers, and a live citation explains its content-free lookup record instead |
| Population exposure inside the three AOIs (2020 Census blocks → H3 r9 tiles) | Working — harness-built per-tile resident counts (Eaton 46,341 · Ian 5,428 · Milton 772,293 assigned), centroid allocation and pre-event vintage declared per feature, envelope population outside evaluated tiles declared as a total; a choropleth view per event, a resident-dossier stat, and an area-selection population sum in planner mode |
| Critical-facility context inside the three AOIs (hospitals, clinics, fire stations, police from OpenStreetMap) | Working — harness-built points with frozen Overpass snapshots; declares OSM *presence, never operational status*, carries its ODbL attribution in the artifact, and the resident dossier lists facilities within 1 km of a covered address. The agent makes no facility claims: no claim-plane rule authorizes them, so they default-deny |
| Planner slider adjustments persisted | **Not done** — recorded in session memory only |
| Releases, CHANGELOG, contributor docs | **Not done** — `CITATION.cff` exists; the rest does not |

## Why "Steward"?

Most agent submissions demonstrate autonomy: an LLM that runs a GIS pipeline.
Ray Resilience demonstrates **accountability**: a risk-analyst agent that operates inside
the **Steward Harness** — a technical layer that enforces three validity conditions
during operation, following *From Autonomous GIS to Accountable GeoAI Agents:
Verifiable Evaluation Environments and Geospatial Harness Engineering* (Yang & Zou):

| Validity layer | What the harness enforces |
|---|---|
| **Outcome** | Executable spatial checks — CRS assertions, multiscale raster×vector join integrity, sanity bounds, mandatory uncertainty fields |
| **Process** | Append-only provenance for every artifact; fail-closed stages; clickable lineage from any map layer back to timestamped source snapshots |
| **Institutional** | Two declarative policy planes in one file. The **claim** plane scopes what the agent may assert, by role, evidence tier, resolution, and geographic authority — tile-level evidence never yields parcel-level claims. The **distribution** plane scopes what a build may publish, by artifact resolution cap and audience; CI verifies the assembled site against it and fails the deploy on a violation. The second plane exists because the first was not enough: see [the 2026-08-20 incident](docs/incidents/2026-08-20-publication-boundary.md) |
| **Verifiability** | Both planes answer questions about what *this project* does. A third question comes from outside it — what may be retained at all, and can a reader check it? The `verifiability` axis (`retained` > `re-derivable` > `cited-only`, weakest-link) and the `license` attribute carry it, so a claim resting partly on evidence nobody is allowed to keep says so instead of borrowing the standing of the hashed evidence beside it |

Every factual sentence the agent produces must cite an artifact ID. Sentences that
cannot be cited are refused, not softened — the exemptions are a closed set
(questions, general safety advice, and statements about what the answer cannot say),
so a form nobody anticipated costs a refusal rather than an uncited claim.

## Architecture

```
Data plane (GitHub Actions)      Presentation plane (PWA)       Agent plane (local today)
USGS / NIFC / NHC / NWS          React + Vite + MapLibre GL     Any OpenAI-compatible
→ append-only snapshots          Resident mode: address →       endpoint (Ollama by
→ pipeline through the           resilience dossier             default) wrapped in the
  Steward Harness                Planner mode: HITL trade-off   Steward Harness: policy
→ artifacts + manifest, gated    sliders, priority tiles,       pre-check → grounded
  by the distribution plane      lineage viewer                 generation → claim
  (GitHub Pages)                                                post-check → audit
```

Three loosely coupled planes: if the agent gateway goes down, the maps and analysis
products keep working — graceful degradation is fail-closed design made visible.

## Hazard coverage (tiered)

- **Tier 1 — Watch:** all active US hazards, near-real-time (earthquakes, wildfires,
  tropical cyclones, flood alerts).
- **Tier 2 — Analysis:** three deep cases — the **Eaton Fire (2025)**, **Hurricane
  Milton (2024)**, and **Hurricane Ian (2022)** — tile-level exposure × social-
  vulnerability analysis with stakeholder-adjustable value trade-offs. Analysis
  exists inside these AOIs and nowhere else.
- **Tier 3 — Evidence:** reliability-gated cross-view damage assessment from the
  [CrossViewGate](https://github.com/rayford295/CrossViewGate) research line, using
  the org's [disaster-crossview-datasets](https://github.com/Rayford-AI/disaster-crossview-datasets).

**Live watch data** is refreshed hourly by CI onto the
[`live-data`](https://github.com/rayford295/ray-resilience/tree/live-data) branch:
`live/products/national_watch.geojson` (all active US hazards) and
`live/products/watch_status.json` (per-source health, declared unknowns), with
append-only raw snapshots under `live/snapshots/`.

Events with only Tier-1 data get an explicit "monitoring data only — no damage
conclusions supported." Declared unknowns are rendered with the same prominence as
findings.

The three tiers describe **evidence depth**. A global catalog needs a second, orthogonal
axis — `verifiability` (`retained` > `re-derivable` > `cited-only`, weakest-link) — because
an event can be well-established and still rest on evidence no reader can check and this
repository may not keep. The two axes together type a bare global registration honestly
(`evidence_tier: 1`, `verifiability: cited-only`) without inventing a field for it, and they
keep a restrictively-licensed high-quality product from borrowing the standing of the hashed
evidence beside it.

## Quick start

```bash
git clone https://github.com/rayford295/ray-resilience && cd ray-resilience
python -m pip install -e ".[deepcase]"
python -m unittest discover -s tests          # 297 pass; 301 with the [gateway] extra (CI installs it)

python scripts/publication_boundary.py plan   # which artifacts may be published
cd app && npm ci && npm test && npm run dev   # PWA at http://localhost:5173
```

The app serves the committed deep-case artifacts, so it works with no keys and no
services. To run the agent gateway too:

```bash
ollama pull gpt-oss:20b
python -m pip install -e ".[deepcase,gateway]"
uvicorn gateway.main:app --port 8080
```

## Repository map

[`docs/manual/`](docs/manual/) is the authority on architecture and mechanism —
this README is the entry point, not the reference.

```
├── app/                 # PWA frontend (WebGIS + smartphone)
├── gateway/             # FastAPI agent gateway (LLM-agnostic + harness middleware)
├── src/geosteward/      # pipeline, agents, sources, hazards, harness/, live/
├── events/              # eaton-2025/, milton-2024/, ian-2022/, archive/bavi-2026/
├── docs/                # STATUS.md, Track-A alignment, incidents/, design/
│   ├── manual/          # the bilingual technical manual — 11 chapters + glossary
│   └── design/          # specs (decision records) and plans (execution)
└── tests/               # doubles as a verifiable evaluation environment
```

## Team

Yifan Yang (Texas A&M University, Geography). MIT License.

Ray Resilience is a research prototype. It is not an official forecasting or warning
service — always follow official emergency guidance.
