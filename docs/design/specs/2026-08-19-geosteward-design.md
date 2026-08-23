# GeoSteward — Design Document

**Date:** 2026-08-19
**Version:** 1 — this design defines GeoSteward v1, the OASIS 2026 submission line; the v1.0.0 tag is cut when this design is fully implemented
**Status:** Approved by project owner (design review completed in brainstorming session)
**Supersedes:** DisasterPilot's current positioning (multi-agent pipeline, Bavi case study)

## 1. Vision and Positioning

**GeoSteward: an accountable GeoAI risk analyst for location-based resilience understanding and decision-making.**

GeoSteward reworks the DisasterPilot repository into an AI-powered WebGIS / smartphone
app (PWA) entered in **OASIS @ ACM SIGSPATIAL 2026 · Track A: Disaster Resilience &
Vulnerability Analysis**. Both deliverables are in scope: a working, judge-clickable
demo (repo + app) and a paper.

The differentiator is **accountability, not autonomy**. Track A explicitly warns
against "repeating generic pipeline steps." GeoSteward answers with the framework from
the companion paper *From Autonomous GIS to Accountable GeoAI Agents: Verifiable
Evaluation Environments and Geospatial Harness Engineering* (Yang & Zou):

| Track A requirement | Paper concept | GeoSteward implementation |
|---|---|---|
| Multiscale spatial joins, dynamic CRS resolution | Outcome validity | Executable spatial checks on every operation; validity badges on map layers |
| Automated risk-analyst agent | Process validity | Append-only provenance, fail-closed stages, clickable lineage viewer |
| Value trade-offs (economic loss vs. social marginalization vs. life safety) | Institutional validity + harness | Policy-scoped agent claims; resolution caps; review gates |
| HITL stakeholder interaction | Harness review gates / human takeover | Trade-off sliders in the planner mode; every human adjustment is audited |

One-sentence pitch: *others submit agents that run pipelines; GeoSteward submits a
risk-analyst agent wearing a verifiable harness, plus a WebGIS/smartphone app where
stakeholders adjust the trade-offs with their own hands.*

### Naming

- Repository: `rayford295/DisasterPilot` → renamed **`rayford295/GeoSteward`**
  (GitHub auto-redirects old URLs). The org fork `Rayford-AI/DisasterPilot` is
  re-synced after the rename.
- Python package: `src/disasterpilot/` → **`src/geosteward/`**.
- The harness implementation is branded **Steward Harness** — the paper and the code
  refer to each other by the same name.
- All repository content (README, code, comments, docs, commit messages) is in
  **English**.

## 2. Hazard and Case-Study Scope

Tiered depth reconciles "the more hazards the better" with feasibility. The harness is
hazard-agnostic; hazards differ only in connectors and geometry modules.

| Tier | Coverage | Content |
|---|---|---|
| **Tier 1 — Watch** | All active US hazards, near-real-time | USGS earthquakes, NASA FIRMS + NIFC wildfires, NOAA NHC tropical cyclones, NWS flood alerts. One connector per source; hourly refresh via GitHub Actions. |
| **Tier 2 — Analysis** | Two flagship deep cases | **Hurricane Milton (2024)** and **Eaton Fire (2025)**: full pipeline — exposure × SVI, multi-objective tile scores, HITL sliders, decision products. Same harness across both hazards demonstrates cross-hazard transfer. |
| **Tier 3 — Evidence** | Events with cross-view imagery | Reliability-gated cross-view damage assessment reusing the CrossViewGate research line and org datasets (`disaster-crossview-datasets`, `debris-estimate` for Milton debris volumes). |

Honesty is a feature of the tiering: clicking a Tier-1-only event yields an explicit
"monitoring data only — no damage conclusions are supported," which is *declared
unknowns* and *institutional validity* demonstrated live.

**Super Typhoon Bavi (2026)** is archived under `events/archive/bavi-2026/`, never
deleted — the project's own append-only principle forbids deleting history. The README
mentions it in one sentence; the narrative focus moves entirely to the US cases.

## 3. Architecture (Approach 1: static-first PWA + artifact-driven WebGIS + serverless agent gateway)

```
┌─ Data plane (GitHub Actions, scheduled) ─────────────────────────┐
│ connectors: USGS / FIRMS+NIFC / NHC / NWS                        │
│   ↓ append-only snapshots (capture_index.jsonl, Bavi pattern)     │
│ pipeline: watcher → dossier → exposure → evidence → decision      │
│   every stage passes through the Steward Harness                  │
│   ↓                                                               │
│ artifacts: GeoJSON / PMTiles / JSON + artifact_manifest.jsonl     │
└──────────────┬───────────────────────────────────────────────────┘
               ↓ static hosting (GitHub Pages)
┌─ Presentation plane: PWA (React + Vite + MapLibre GL JS) ────────┐
│ Resident mode: address search → location resilience dossier       │
│ Planner mode: trade-off sliders / priority tiles / routes /       │
│               lineage viewer / validity badges                    │
└──────────────┬───────────────────────────────────────────────────┘
               ↓ conversational features only
┌─ Agent plane: Cloud Run gateway (the only server) ───────────────┐
│ harness middleware: policy pre-check → Gemini → claim post-check  │
│                     → audit log                                   │
└───────────────────────────────────────────────────────────────────┘
```

The three planes are loosely coupled and independently survivable: if the data plane
stalls, the app shows stale-data badges with timestamps; if the agent plane dies, maps
and analysis products keep working. Graceful degradation is itself a live
demonstration of fail-closed design.

Strategic stack choices for a Google-hosted event: **Gemini API** for agent reasoning,
**Cloud Run** (free tier) for the gateway. Frontend: React + Vite + `vite-plugin-pwa`,
MapLibre GL JS, PMTiles/OpenFreeMap basemap (no paid map keys).

### Repository layout (after rework)

```
GeoSteward/
├── app/                        # PWA frontend
├── gateway/                    # Cloud Run agent gateway (FastAPI)
├── src/geosteward/
│   ├── harness/                # Steward Harness — the paper's contribution in code
│   │   ├── checks/             #   outcome validity (CRS assertions, join integrity, sanity bounds)
│   │   ├── policy.py           #   institutional validity (declarative YAML policy engine)
│   │   └── audit.py            #   audit + manifest writing
│   ├── agents/                 # five roles retained, wired through the harness
│   ├── sources/                # usgs.py, firms_nifc.py, nhc.py, nws.py (zj_typhoon.py retired)
│   ├── hazards/                # hurricane.py, wildfire.py, earthquake.py (watch-only), flood.py (watch-only)
│   └── pipeline.py
├── events/
│   ├── milton-2024/            # deep case 1: full pipeline + SVI trade-offs + evidence
│   ├── eaton-2025/             # deep case 2: same harness, wildfire — cross-hazard transfer
│   └── archive/bavi-2026/      # archived, never deleted
├── docs/                       # paper material: harness spec, methodology, Track-A alignment
└── tests/                      # doubles as the verifiable evaluation environment
```

Live Tier-1 snapshots and published artifacts go to the **`gh-pages` branch** (hourly
commits would pollute `main` history); `main` keeps code and versioned deep-case
artifacts.

## 4. Components

### 4.1 Steward Harness

| Validity layer | Module | Checks |
|---|---|---|
| **Outcome** | `harness/checks/` | Every layer must declare its EPSG; CRS is asserted before any join. Raster-hazard × vector-boundary join integrity (coverage ratio, no orphan census tracts). Area/value sanity bounds. Uncertainty fields are mandatory. |
| **Institutional** | `harness/policy.py` | A single declarative **YAML policy file**: rules keyed by **role** (resident/planner), **evidence tier** (1/2/3), **resolution cap** (tile-level evidence forbids parcel-level claims), **geographic scope** (no damage assessment outside an event AOI), and purpose. The paper can quote this file verbatim as an instance of "computable constraints." |
| **Process** | `harness/audit.py` + manifest | Lineage for every agent output (inputs → agent → UTC timestamp → uncertainty). **Every human slider adjustment is also written to the manifest** — HITL participants are accountable too. |

### 4.2 PWA frontend (dual mode)

- **Resident mode:** address search (US Census geocoder, free) → a "resilience dossier
  card" for that location: nearby active hazards (Tier 1, nationwide), exposure and
  SVI context when inside a deep-case AOI, plain-language agent chat, and *declared
  unknowns rendered with the same prominence as findings*.
- **Planner mode:** layer panel; trade-off sliders (life safety ↔ long-term recovery,
  economic loss ↔ social marginalization) that re-weight precomputed multi-objective
  tile scores **client-side** for instant response; priority tiles and
  budget-constrained inspection routes; **lineage viewer** (click any layer → full
  provenance chain); validity badges on every layer.
- Dual mode itself demonstrates institutional validity: the same agent speaks at
  different depths to different roles (residents never see parcel-level speculation;
  planners see tile-level assessments with uncertainty).
- PWA basics: installable on phones, service-worker caching of the latest artifacts —
  offline capability is a genuine feature in disaster contexts, not a compromise.

### 4.3 Agent gateway (Cloud Run + Gemini)

Request pipeline — the harness stands guard on both sides of the LLM:

```
request(role, location, question)
 → policy pre-check (out-of-scope requests are refused before any LLM call)
 → retrieve context ONLY from manifest-listed artifacts (never the open web)
 → Gemini generation
 → claim post-check (every claim must cite an artifact ID; claims beyond the
   evidence tier → structured refusal with the triggering rule ID)
 → append audit log → respond
```

Mandatory artifact-ID citation is a structural defense against hallucination: every
sentence the agent says can be clicked back to a timestamped snapshot, turning the
candor duty into unit-testable behavior.

### 4.4 Data pipeline

The five agent roles (watcher, dossier, exposure, evidence, decision) are retained and
wired through the harness. Four new connectors feed Tier 1 hourly. Deep-case products
are precomputed offline and committed.

## 5. Data Flows

**Loop 1 — live (hourly, GitHub Actions):** cron → connectors → append-only snapshots
→ watcher registers/updates events → lightweight situational GeoJSON → published to
`gh-pages` → PWA fetches.

**Loop 2 — deep case (offline, on data updates):** org datasets (Milton / Eaton) →
full five-stage pipeline through the harness → artifacts (exposure, multi-objective
tile scores, evidence, decision) + manifest → versioned in `events/` on `main`,
published to static hosting.

**Loop 3 — interactive (user session):** slider moves re-weight client-side instantly
and POST an audit record to the gateway asynchronously; chat questions go through the
gateway pipeline above.

## 6. Error Handling (fail-closed, extended system-wide)

| Failure | Behavior |
|---|---|
| Source outage | Stage records the failure (existing fail-closed); the app shows a **stale badge + last-success timestamp** on affected layers — the candor duty, rendered in UI. |
| Gateway down / Gemini quota exhausted | Static app keeps working; chat shows an explicit "agent unavailable" — never cached fake answers. |
| Policy-violating request | Structured refusal citing the **triggering rule ID**, logged — refusals themselves are traceable. |
| Location outside coverage | Explicit "this location is outside the evaluated competence" — the paper's "competence is conditional on place" productized. |
| Artifact integrity | Manifest records a hash per artifact; the app verifies on load to prevent deployment drift. |

## 7. Testing (the test suite IS the paper's evaluation environment)

The paper's first contribution is *verifiable evaluation environments*; `tests/` is
organized as a miniature one, so the repo demonstrates the methodology the paper
proposes:

- **Outcome-layer unit tests:** CRS-mismatch cases, orphan-tract joins, out-of-bounds
  areas — positive and negative cases for every harness check.
- **Policy matrix tests:** the role × evidence-tier × resolution grid, verifying
  allow/refuse cell by cell.
- **Adversarial agent tests:** a suite of prompts engineered to elicit out-of-scope
  claims (parcel-level conclusions, outside-AOI assessments, uncited assertions) —
  all must trigger structured refusals. In the paper these are *graded tasks with
  executable checks*.
- **Offline end-to-end:** committed snapshots → full pipeline → golden-artifact
  comparison (extends the existing pattern).
- **Frontend smoke:** Playwright — map loads, mode switch, slider changes tile
  ranking.
- **CI:** full suite on every push; the live loop passes a canary validation before
  publishing.

A reviewer can add an adversarial case and run CI — there is no stronger
accountability demo.

## 8. Migration Notes

1. Merge the org fork's one extra commit (`9ad836f` — docs backlink to
   `disaster-crossview-datasets`) into `main` before restructuring.
2. Rename `rayford295/DisasterPilot` → `rayford295/GeoSteward` (GitHub redirects old
   URLs); update the org fork afterwards.
3. Rename package `disasterpilot` → `geosteward`; retire `sources/zj_typhoon.py` and
   `hazards/typhoon.py` into the archive path with the Bavi event.
4. Update `docs/track_a_alignment.md` with the official Track A brief (now obtained)
   and this design's mapping.

## 9. Out of Scope (YAGNI)

- Native iOS/Android builds (PWA covers the smartphone requirement).
- A hosted geoprocessing backend (PostGIS/FastAPI compute-on-demand) — heavy
  processing is precomputed; the only server is the thin agent gateway.
- User accounts / authentication (role is a client-side mode switch, honestly
  disclosed as such; the policy engine treats role as an input, not a security
  boundary — real authentication is post-competition work).
- Non-US hazards and live typhoon sources.
- Real-time evidence ingestion (Tier 3 uses committed cross-view datasets).

## 10. Open Items

- **Submission deadline is still unknown** — obtain it from the OASIS event page and
  size the implementation plan accordingly.
- Confirm Gemini API and Cloud Run free-tier quotas suffice for judging-week traffic.
- Choose the Milton AOI (landfall counties vs. full track swath) when building the
  deep case.
