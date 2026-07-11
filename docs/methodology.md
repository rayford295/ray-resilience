# Methodology

Three phases, one honest loop: predict exposure before landfall, observe
damage after, and score how well the pre-event structure anticipated the harm.
The methodological DNA comes from the CrossViewGate research line
(cross-view reliability gating; spatially blocked evaluation; risk-aware
claim rules), applied here to a live event.

## Phase 1 — Pre-landfall exposure & vulnerability

**Inputs.** Timestamped live-track snapshots (points, quadrant wind radii for
Beaufort 7/10/12, multi-agency forecast tracks); WorldPop/GHS-POP population
grids; OSM building footprints; coastal DEM for low-lying zones.

**Products.**
1. *Wind-swath surfaces*: union of quadrant wind-radius sectors swept along
   the observed + forecast track, per Beaufort threshold, per forecast agency
   (agency spread = track uncertainty proxy).
2. *Exposure table*: population and building counts inside each swath ×
   threshold, aggregated to county/township.
3. *Vulnerability-weighted watchlist*: exposure weighted by building-stock
   proxies, coastal low-elevation share (seawater-backflow risk flagged by
   CMA), and rainfall-triggered landslide susceptibility where slope data
   allow.

**Discipline.** Every product embeds the snapshot timestamp of the track it
used. Pre-landfall products are *forecast-conditioned*; they are frozen (not
retro-edited) so Phase-3 validation is real.

## Phase 2 — Post-landfall cross-view damage evidence

**Inputs.** Post-event satellite imagery (Sentinel-1 change detection first —
SAR sees through cloud in the days after landfall; Sentinel-2/GF optical as
skies clear); street-level and social imagery as it becomes geolocatable.

**Method.** Per assessed unit, views are treated as *witnesses with different
competence*: overhead attests roof/inundation extent, street-level attests
facade/water-line damage. A reliability gate (visibility- and
confidence-conditioned) arbitrates per sample instead of symmetric fusion.
Where neither view can attest a unit, the output is an explicit **abstain +
acquire/inspect flag**, not a forced label.

**Discipline.** Spatially blocked splits for anything fitted; cluster-aware
uncertainty; disagreement between views is reported as its own layer — prior
work shows conflict density itself predicts damage concentration.

## Phase 3 — Resilience decisions and validation

1. *Tile-priority map*: fuses Phase-2 evidence with Phase-1 vulnerability
   into inspection priorities with explicit cost assumptions.
2. *Budget-constrained route*: ordered inspection plan under stops/distance
   budgets (discoveries-per-kilometer as the metric).
3. *Resilience scorecard*: the headline analysis — how much of observed
   damage was concentrated in pre-declared watchlist areas (hit rate at
   fixed area budgets), where the pre-event model failed, and what that says
   about the vulnerability indicators used. Failures are reported with the
   same prominence as successes.

## Claim rules

- Forecast-conditioned vs observed products are never mixed in one table.
- Any statistical claim carries its spatial-dependence treatment (block
  bootstrap at minimum) or is labeled descriptive.
- Casualty/damage figures cite official releases only and carry access dates.
- Negative validation results (watchlist misses) are published, not pruned.
