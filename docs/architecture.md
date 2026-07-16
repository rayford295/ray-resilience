# DisasterPilot architecture

One pipeline, five agent roles, auditable artifacts at every step. The design
goal is not "an LLM that talks about disasters" — it is a chain of custody
from public information to defensible decisions.

## Agent roles across the disaster lifecycle

```text
 pre-event                      landfall                    post-event
────────────────────────────────────┼──────────────────────────────────────
 1. WATCHER      poll public sources, register events, snapshot hazards
 2. DOSSIER      structured event record from captured payloads
 3. EXPOSURE     hazard footprint × population/buildings → watchlist
                                     │
 4. EVIDENCE     cross-view damage assessment (reliability-gated,
                 fails closed until imagery exists)
 5. DECISION     watch bulletin → tile priorities → inspection routes
                 → resilience scorecard (did pre-event structure
                 predict post-event harm?)
```

Implemented today: watcher, dossier, exposure, decision (watch-bulletin
stage), and source-based event closure. The full pre-event chain ran
end-to-end on Bavi live data. The evidence agent is an enforced fail-closed
interface until post-event imagery manifests exist; its methodology is the
CrossViewGate reliability-gating line, validated on three prior disasters.

The closure stage is deliberately separate from pre-event artifacts. It stops
new scheduled captures once the source marks the event inactive, records the
final source payload and reported landfalls, and lists the still-missing
official reconciliation, exposure counts, imagery, and validation labels.

## The artifact contract

Every agent output goes through `EventContext.write_json`/`register`:

- artifacts live under `events/<event-id>/<stage>/`;
- each carries agent name, UTC timestamp, and input artifact names in
  `events/<event-id>/artifact_manifest.jsonl`;
- snapshots are **append-only** — a rerun adds a new timestamped file.
  Pre-event products are therefore frozen and post-event validation is
  honest by construction;
- agents that lack their inputs **fail closed** with a reason, and the
  orchestrator records the failure instead of skipping silently.

## Source connectors

`src/disasterpilot/sources/` — one module per public source, uniform
functions, no scraping of authenticated pages:

| Source | Status | Provides |
| --- | --- | --- |
| Zhejiang Water Resources typhoon API | **live** | WP typhoon tracks, quadrant wind radii, multi-agency forecasts |
| CMA best track (tcdata) | planned | post-event reconciliation |
| GDACS | planned | multi-hazard global alerts (watcher expansion) |
| USGS earthquakes | planned | seismic events |
| Copernicus/Sentinel catalogs | planned | evidence-phase imagery manifests |

## Honesty rules (inherited from the CrossViewGate research line)

1. Forecast-conditioned and observed products never mix in one table.
2. Machine-generated records contain only machine-verifiable numbers;
   narrative facts (casualties, warnings) are human-curated with citations.
3. Unknowns are declared in every decision product, not omitted.
4. No damage estimate without imagery: the evidence agent raises rather
   than interpolates.
5. Post-event, every pre-event product is scored against observations and
   the misses are published with the hits.

## Where LLM agents plug in

The current agents are deterministic pipeline stages — that is deliberate:
the artifact chain and fail-closed rules are the skeleton that any LLM layer
must respect. Planned LLM integration points, each producing artifacts under
the same contract:

- dossier narrative synthesis from cited sources (with claim-to-source map);
- imagery/report triage in the evidence phase;
- bulletin drafting for human review (never auto-published).
