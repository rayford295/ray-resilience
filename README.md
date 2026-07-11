# Typhoon Bavi (2026) — Near-Real-Time Resilience & Vulnerability Analysis

**Entry for OASIS @ ACM SIGSPATIAL 2026 · Track A: Disaster Resilience &
Vulnerability Analysis.**

Super Typhoon Bavi (2026 international number **2609**, 巴威) is making
landfall on the Fujian–Zhejiang coast of China **as this repository is being
built** (expected landfall window: night of 2026-07-11 CST, Xiapu–Wenling
segment). This project performs the full resilience-analysis loop on a live
event: pre-landfall exposure and vulnerability mapping, post-landfall
cross-view damage evidence, and budget-constrained inspection prioritization —
with the claim discipline of a research protocol, not a demo.

## Why this entry is different

Most disaster-track entries fit one model to one post-event dataset. This
entry brings a tested methodological position developed in
[CrossViewGate](https://github.com/rayford295/CrossViewGate) across three
prior disasters (2025 Eaton wildfire, Hurricanes Ian and Milton):

1. **Views disagree, and the disagreement is signal.** Street-level and
   overhead evidence systematically attest different damage facets. We treat
   per-sample view reliability — not symmetric fusion — as the core object.
2. **Risk-aware claims only.** Every output carries its evidence scope:
   spatially blocked splits, cluster-aware uncertainty, and an explicit
   `risk-aware` / `risk-controlled` claim rule. No leaderboard numbers from
   leaked splits.
3. **Decisions, not just maps.** The final products are a review queue, a
   tile-priority map, and an inspection route under an explicit budget —
   the artifacts an emergency manager can actually consume.

## Live status

| Item | State |
| --- | --- |
| Event | Super Typhoon Bavi (2609), peak 910 hPa / CMA 62 m/s |
| Phase | **Pre-landfall** — track + wind-radii snapshots being captured |
| First data product | `data/snapshots/` live track from the Zhejiang Water Resources typhoon API (points + quadrant wind radii + multi-agency forecasts) |
| Casualties so far (Philippines transit) | ≥18 dead, 8 injured, 5 missing |
| CN warning level | Orange (2026-07-09), CMA Level-II emergency response |

Event dossier with sources: [`docs/event_bavi_2026.md`](docs/event_bavi_2026.md).

## Analysis phases

**Phase 1 — Exposure & vulnerability (pre-landfall, now).**
Intersect forecast wind swaths (quadrant 7/10/12-Beaufort radii) with
population, building footprints, and coastal low-lying zones to produce a
pre-event exposure surface and a vulnerability-weighted watchlist of
townships. Everything is timestamped so post-event validation is honest.

**Phase 2 — Cross-view damage evidence (post-landfall).**
As imagery becomes available (satellite first, street-level later), apply
reliability-gated cross-view assessment: per-sample decision on which view to
trust, calibrated confidence, and explicit abstention where neither view can
attest damage.

**Phase 3 — Resilience decisions.**
Convert sample-level evidence into tile priorities and a budget-constrained
inspection route; validate Phase-1 vulnerability predictions against Phase-2
observed damage — the resilience question is *how well pre-event structure
predicted post-event harm*.

Method details: [`docs/methodology.md`](docs/methodology.md).
Track-A requirement mapping: [`docs/track_a_alignment.md`](docs/track_a_alignment.md).

## Quickstart

```bash
pip install -e .
# capture a live track snapshot (timestamped, never overwrites)
python scripts/fetch_bavi_track.py --output-dir data/snapshots
# normalize + wind-swath geometry
python -m pytest tests -q
```

## Repository map

```text
├── docs/               # event dossier, methodology, track alignment
├── src/bavi/           # track parsing, wind-swath geometry, exposure
├── scripts/            # data capture + analysis pipelines
├── data/snapshots/     # timestamped live API captures (small JSON)
└── tests/              # unit tests (CI on every push)
```

## Data sources

- Live track/forecast: Zhejiang Water Resources typhoon API (public)
- Best track (post-event): CMA tcdata, JMA, JTWC
- Population: WorldPop / GHS-POP · Buildings: OSM / EOC footprints
- Imagery: Sentinel-1/2, GF series (as released), street-level as available
- Event facts: see dossier citations

## Team

Yifan Yang (Texas A&M University, Geography) — building on the CrossViewGate
research line (cross-view reliability gating, ISPRS manuscript in preparation).

中文说明见 [`README_CN.md`](README_CN.md)。MIT License.
