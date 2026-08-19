# GeoSteward

**An accountable GeoAI risk analyst for location-based resilience understanding
and decision-making.**

AI-powered WebGIS / smartphone app (PWA): enter any US location and understand its
resilience — what hazards threaten it now, how exposed and vulnerable it is, and what
decisions the evidence actually supports. Entry for **OASIS @ ACM SIGSPATIAL 2026 ·
Track A: Disaster Resilience & Vulnerability Analysis**.

> 🚧 **Rework in progress.** This repository (formerly *DisasterPilot*) is being
> rebuilt around the design in
> [`docs/superpowers/specs/2026-08-19-geosteward-design.md`](docs/superpowers/specs/2026-08-19-geosteward-design.md).
> The previous Super Typhoon Bavi case study is preserved under `events/` and will
> move to `events/archive/` — append-only history is a core principle here.

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
| **Institutional** | Declarative policy scoping what the agent may claim, by role, evidence tier, resolution, and geographic authority — tile-level evidence never yields parcel-level claims |

Every claim the agent makes must cite an artifact ID. Every human trade-off
adjustment is audited too.

## Architecture

```
Data plane (GitHub Actions)      Presentation plane (PWA)       Agent plane (Cloud Run)
USGS / FIRMS+NIFC / NHC / NWS    React + Vite + MapLibre GL     Gemini wrapped in the
→ append-only snapshots          Resident mode: address →       Steward Harness:
→ 5-agent pipeline through       resilience dossier             policy pre-check →
  the Steward Harness            Planner mode: HITL trade-off   artifact-grounded
→ static artifacts + manifest    sliders, priority tiles,       generation → claim
  (GitHub Pages)                 lineage viewer                 post-check → audit
```

Three loosely coupled planes: if the agent gateway goes down, the maps and analysis
products keep working — graceful degradation is fail-closed design made visible.

## Hazard coverage (tiered)

- **Tier 1 — Watch:** all active US hazards, near-real-time (earthquakes, wildfires,
  tropical cyclones, flood alerts).
- **Tier 2 — Analysis:** two flagship deep cases — **Hurricane Milton (2024)** and the
  **Eaton Fire (2025)** — full exposure × social-vulnerability analysis with
  stakeholder-adjustable value trade-offs.
- **Tier 3 — Evidence:** reliability-gated cross-view damage assessment from the
  [CrossViewGate](https://github.com/rayford295/CrossViewGate) research line, using
  the org's [disaster-crossview-datasets](https://github.com/Rayford-AI/disaster-crossview-datasets).

Events with only Tier-1 data get an explicit "monitoring data only — no damage
conclusions supported." Declared unknowns are rendered with the same prominence as
findings.

## Repository map (target layout)

```
├── app/                 # PWA frontend (WebGIS + smartphone)
├── gateway/             # Cloud Run agent gateway (Gemini + harness middleware)
├── src/geosteward/      # pipeline, agents, sources, hazards, harness/
├── events/              # milton-2024/, eaton-2025/, archive/bavi-2026/
├── docs/                # design spec, methodology, Track-A alignment
└── tests/               # doubles as a verifiable evaluation environment
```

## Team

Yifan Yang (Texas A&M University, Geography). MIT License.

GeoSteward is a research prototype. It is not an official forecasting or warning
service — always follow official emergency guidance.
