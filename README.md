# GeoSteward

**An accountable GeoAI risk analyst for location-based resilience understanding
and decision-making.**

AI-powered WebGIS / smartphone app (PWA) for understanding a place's resilience —
what hazards threaten it now, how exposed and vulnerable it is, and what decisions
the evidence actually supports. Entry for **OASIS @ ACM SIGSPATIAL 2026 · Track A:
Disaster Resilience & Vulnerability Analysis**.

**Live:** [rayford295.github.io/GeoSteward](https://rayford295.github.io/GeoSteward/)
· [the app](https://rayford295.github.io/GeoSteward/app/)

**What "a place" means here, precisely.** Hazard monitoring is nationwide: any US
location gets the current Tier-1 watch layer. Exposure, vulnerability, and damage
analysis exist only inside the three deep-case AOIs below, and the app says so
rather than extrapolating — an address outside them is told the location is outside
the evaluated areas, and an address the app cannot yet resolve is told that instead
of being guessed at. Competence is conditional on place, and saying where it ends is
part of the design.

> 🚧 **Rework in progress.** This repository (formerly *DisasterPilot*) is being
> rebuilt around the design in
> [`docs/superpowers/specs/2026-08-19-geosteward-design.md`](docs/superpowers/specs/2026-08-19-geosteward-design.md).
> The previous Super Typhoon Bavi case study is preserved under
> `events/archive/bavi-2026/` — append-only history is a core principle here.

## What works today, and what does not

| | State |
|---|---|
| Tier-1 nationwide watch (USGS, NWS, NHC, NIFC) | Working; refreshed hourly by CI, per-source failures declared not hidden |
| Three deep cases (Eaton 2025, Milton 2024, Ian 2022) | Working; tile-level exposure, SVI, and cross-view evidence |
| PWA, installable, offline-caching | Working |
| Steward Harness: outcome checks, append-only audit, policy pre-check, claim post-check | Working |
| Publication boundary (distribution plane + CI gate) | Working |
| Agent gateway | Working locally against any OpenAI-compatible endpoint (Ollama by default). **Not hosted** — the public demo has no chat backend, and the gateway has no auth, rate limiting, or log redaction yet, so it should not be exposed as-is |
| Accountability for non-retainable evidence (`verifiability` axis, `license` attribute, content-free lookup record) | Working and policed in code; **never run against a live API** — there is no Google Maps Platform key, so both adapters are tested against an in-process stub and `events/live_evidence.jsonl` does not exist outside tests. [Design and implementation notes](docs/superpowers/specs/2026-08-20-non-retainable-evidence-design.md) |
| Live-watch source health surfaced in the map UI | Working — the badge reports mapped-of-total, features it could not map, failed sources, and product generation time from `watch_status.json` |
| Citation click-through from an answer to its artifact | **Not done** — answers carry artifact IDs; the UI does not yet resolve them |
| Planner slider adjustments persisted | **Not done** — recorded in session memory only |
| Releases, CHANGELOG, CITATION.cff, contributor docs | **Not done** |

## Why "Steward"?

Most agent submissions demonstrate autonomy: an LLM that runs a GIS pipeline.
GeoSteward demonstrates **accountability**: a risk-analyst agent that operates inside
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
[`live-data`](https://github.com/rayford295/GeoSteward/tree/live-data) branch:
`live/products/national_watch.geojson` (all active US hazards) and
`live/products/watch_status.json` (per-source health, declared unknowns), with
append-only raw snapshots under `live/snapshots/`.

Events with only Tier-1 data get an explicit "monitoring data only — no damage
conclusions supported." Declared unknowns are rendered with the same prominence as
findings.

## Quick start

```bash
git clone https://github.com/rayford295/GeoSteward && cd GeoSteward
python -m pip install -e ".[deepcase]"
python -m unittest discover -s tests          # 212 tests

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

```
├── app/                 # PWA frontend (WebGIS + smartphone)
├── gateway/             # FastAPI agent gateway (LLM-agnostic + harness middleware)
├── src/geosteward/      # pipeline, agents, sources, hazards, harness/, live/
├── events/              # eaton-2025/, milton-2024/, ian-2022/, archive/bavi-2026/
├── docs/                # design spec, methodology, Track-A alignment
└── tests/               # doubles as a verifiable evaluation environment
```

## Team

Yifan Yang (Texas A&M University, Geography). MIT License.

GeoSteward is a research prototype. It is not an official forecasting or warning
service — always follow official emergency guidance.
