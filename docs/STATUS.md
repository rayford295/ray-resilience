# GeoSteward v1 — Project Status

**Updated:** 2026-08-19 · **Target:** OASIS @ ACM SIGSPATIAL 2026 Track A
**Key dates (AoE):** Short Paper & Code Submission **2026-09-04** · Finalist Notification 09-20 · Camera-Ready 10-09 · Finalist Presentation & Demo 11-03

Roadmap: five sequential plans under [`docs/superpowers/plans/`](superpowers/plans/), all derived from the
[design spec](superpowers/specs/2026-08-19-geosteward-design.md).

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
    resolution-capped lineage artifact, never served to residents.
  - Tier-3 evidence: 2,244 cross-view matched samples → **109-cell reliability-gated
    coverage grid** (`match_quality ∈ {good, usable}`); the `damaged_repairable`
    class (n=30) is declared as lacking statistical power, not hidden.
  - Dossier `event_record.json` with declared unknowns; registry profiles frozen under
    `snapshots/registry/` so every cell traces to a hashed dataset state.
- Test suite now **81 tests green** (new `test_deepcase_dins.py`); CI installs the
  `deepcase` extra (`h3`).

## 🔜 Next (not blocked)

- **Plan 3 — deep cases:** Hurricane Milton exposure/evidence build can start from
  *public* assets: the Bi-Temporal street-view dataset (Figshare
  `10.6084/m9.figshare.28801208.v2`, Hugging Face `Rayford295/BiTemporal-StreetView-Damage`,
  2,556 pre/post pairs + Horseshoe Beach boundary), the committed Pinellas County H3
  debris grids in `Rayford-AI/debris-estimate`, and public FEMA/SVI/TIGER layers.
  Eaton Fire tile-level layers can start from the committed
  `EATON_wildfire_mapillary_matched` manifests/GeoJSON (2,244 matched samples) plus the
  public CAL FIRE perimeter for the AOI.
- **Plan 4 — PWA** (dual-mode WebGIS frontend) and **Plan 5 — agent gateway**: designs
  ready; Plan 5 requires credentials (below).

## 🚧 Blocked / needs the project owner

| # | Item | Needed for | Notes |
|---|------|-----------|-------|
| 1 | **Gemini API key** | Plan 5 agent gateway | Free tier is sufficient for development. |
| 2 | **Google Cloud project** (Cloud Run enabled) | Plan 5 gateway deployment | Free tier sufficient; needed before the 11-03 finalist demo, not necessarily before 09-04. |
| 3 | ~~**Raw imagery transfer**~~ **RESOLVED 2026-08-20** | Plan 3 evidence tier (full depth) | The full collection was located on the owner's workstation (`Desktop/disaster-dataset-Yifan-all`, ~33 GB): DINS points + 19,780 attachment photos, NOAA Altadena orthoimagery, EATON/IAN matched sets, Bi-Temporal pairs. All registered and SHA-256-hashed in `_registry/`; image-level evidence demos are now possible. Remaining sub-question: where to host raw imagery for judges (HF datasets, following the Bi-Temporal precedent). |
| 4 | **GenDisasterSVI provenance ruling** | Whether Milton GenDisasterSVI may be used as evidence | **Ruling now evidence-backed:** the local `dataset.csv` source paths reference `experiment2_ip2p` (InstructPix2Pix), confirming post-event street images are model-generated. Registry tier: `generated_excluded`. Open sub-question: the 2,555 `post_sat` satellite images may be real acquisitions — owner to confirm before any use. The Bi-Temporal set (verified, published) is used instead. |
| 5 | **OASIS submission portal details** | 09-04 submission | Exact paper format/page limit and code-submission mechanism from the event portal. |
| 6 | **Repository visibility decision** | Judge access + PWA data path | Both repos are currently **private**. Judges reviewing the code, and the PWA fetching `live-data` via `raw.githubusercontent.com`, require public visibility. The timing of flipping to public is the owner's call (it also interacts with prior-disclosure considerations the owner is managing); the fallback for a private demo is token-gated access or copying products into the Pages tree. |

## Known limitations (tracked, not blocking)

- NWS zone/county alerts without polygon geometry are counted but not displayed
  (declared in `watch_status.json`); zone-centroid resolution is a Plan 4 candidate.
- Legacy typhoon modules (`sources/zj_typhoon.py`, `hazards/typhoon.py`) remain until
  Plan 3 rewires the pipeline agents to the US connectors, then retire to the archive.
- `docs/architecture.md` still describes the pre-rework pipeline; rewritten in Plan 3's
  narrative pass.
- Live snapshot growth is mitigated by gzip; an archive/rotate policy will be decided in
  the Plan 4 design before consumer URLs freeze.
