# DisasterPilot

> 📦 **Datasets:** [disaster-crossview-datasets](https://github.com/Rayford-AI/disaster-crossview-datasets) — the shared cross-view disaster data backbone for the Rayford-AI org.

**A multi-agent pipeline from public disaster information to auditable
decisions — pre-event watch to post-event evidence.**

🌐 **Website: https://rayford295.github.io/DisasterPilot/**

Entry for **OASIS @ ACM SIGSPATIAL 2026 · Track A: Disaster Resilience &
Vulnerability Analysis**. Its first case study, **Super Typhoon Bavi (2026)**,
captured the pre-landfall track in real time and now preserves a separate
post-event closure record.

## What it does

```text
public sources ──▶ WATCHER ──▶ DOSSIER ──▶ EXPOSURE ──▶ EVIDENCE ──▶ DECISION
                 snapshot     structured   hazard ×     cross-view   bulletins,
                 hazards      event        population   damage       priorities,
                 (append-     record       footprints   (reliability inspection
                 only)                                  -gated)      routes
```

Five agent roles cover the disaster lifecycle: **watch** public sources and
register events; build a **dossier** of machine-verifiable facts; compute
**exposure** footprints for vulnerability analysis; assess post-event
**evidence** with reliability-gated cross-view fusion; and emit **decision**
products an emergency manager can act on. Details:
[`docs/architecture.md`](docs/architecture.md).

Three design rules make it defensible rather than demo-ware:

1. **Append-only artifacts with provenance.** Every agent output carries its
   inputs, agent, and UTC timestamp in a per-event manifest. Pre-event
   products are frozen, so post-event validation is honest by construction.
2. **Fail closed.** No imagery → no damage numbers; missing inputs → recorded
   failure, never silent skipping or interpolation.
3. **Declared unknowns.** Every decision product lists what is *not* known
   with the same prominence as what is.

The evidence methodology comes from the
[CrossViewGate](https://github.com/rayford295/CrossViewGate) research line
(reliability-gated cross-view damage assessment, validated across the 2025
Eaton wildfire and Hurricanes Ian and Milton).

## Closed case study: Super Typhoon Bavi (2026)

Bavi (international number 2609, peak 910 hPa) made landfall on the
Xiapu–Wenling coastal segment on the night of 2026-07-11 CST. This
repository began capturing its track **before landfall**:

- `events/bavi-2026/snapshots/` — 41 append-only captures, ending with an
  inactive-source snapshot containing 168 track points, quadrant 7/10/12-
  Beaufort wind radii, and multi-agency forecasts;
- `events/bavi-2026/DOSSIER.md` — sourced event dossier with a post-event
  reconciliation ledger;
- `events/bavi-2026/{dossier,exposure,decision}/` — pipeline products:
  structured event record, wind-footprint GeoJSON, watch bulletin with
  declared unknowns.
- `events/bavi-2026/closure/` — a separate closure record built from the
  final committed source payload. It reports source-recorded landfalls without
  rewriting frozen pre-event products.

Reproduce the pre-event pipeline (offline mode reuses committed snapshots):

```bash
pip install -e .
python scripts/run_pre_event.py --event-id bavi-2026 --tfid 202609 --offline
python scripts/close_event.py --event-dir events/bavi-2026
python -m unittest discover -s tests
```

## Repository map

```text
├── src/disasterpilot/
│   ├── agents/          # watcher, dossier, exposure, evidence, decision
│   ├── sources/         # public-source connectors (ZJ typhoon API live; GDACS/USGS planned)
│   ├── hazards/         # hazard-specific parsing + geometry (typhoon wind swaths)
│   └── pipeline.py      # orchestrator with fail-closed stage reporting
├── events/bavi-2026/    # case study #1: snapshots + dossier + pipeline artifacts
├── docs/                # architecture, methodology, Track-A alignment
└── tests/               # unit + offline end-to-end pipeline tests (CI)
```

- Methodology (three-phase resilience loop): [`docs/methodology.md`](docs/methodology.md)
- Track-A requirement mapping: [`docs/track_a_alignment.md`](docs/track_a_alignment.md)

## Team

Yifan Yang (Texas A&M University, Geography).
中文说明见 [`README_CN.md`](README_CN.md)。MIT License.
