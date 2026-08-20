// Layer catalog: every view maps one committed artifact to one map layer.
// `stage` ties the layer to its harness audit records (validity badges);
// `metric` drives the choropleth. Nothing here invents data — a view that
// fails to load renders as a declared failure, never an empty success.

export const EVENTS = {
  "eaton-2025": {
    title: "Eaton Fire 2025",
    center: [-118.09, 34.19],
    zoom: 12.2,
    record: "/events/eaton-2025/dossier/event_record.json",
    manifest: "/events/eaton-2025/artifact_manifest.jsonl",
    audit: "/events/eaton-2025/audit_log.jsonl",
  },
  "milton-2024": {
    title: "Hurricane Milton 2024",
    center: [-83.05, 28.6],
    zoom: 7.2,
    record: "/events/milton-2024/dossier/event_record.json",
    manifest: "/events/milton-2024/artifact_manifest.jsonl",
    audit: "/events/milton-2024/audit_log.jsonl",
  },
};

export const VIEWS = [
  {
    id: "eaton-priority",
    event: "eaton-2025",
    label: "Damage × SVI priority",
    url: "/events/eaton-2025/exposure/svi_h3_r9_context.geojson",
    stage: "exposure.svi_context",
    kind: "priority", // planner sliders re-weight this layer client-side
    tier: 2,
  },
  {
    id: "eaton-damage",
    event: "eaton-2025",
    label: "Structure damage (DINS)",
    url: "/events/eaton-2025/exposure/dins_h3_r9_damage_grid.geojson",
    stage: "exposure.dins_grid",
    kind: "rate",
    metric: "destroyed_rate",
    legend: "share of assessed structures destroyed",
    tier: 2,
  },
  {
    id: "eaton-evidence",
    event: "eaton-2025",
    label: "Cross-view evidence coverage",
    url: "/events/eaton-2025/evidence/crossview_h3_r9_coverage.geojson",
    stage: "evidence.crossview_coverage",
    kind: "count",
    metric: "n_matched_samples",
    legend: "reliability-gated matched samples per tile",
    tier: 3,
  },
  {
    id: "milton-evidence",
    event: "milton-2024",
    label: "Street-view evidence (Horseshoe Beach)",
    url: "/events/milton-2024/evidence/bitemporal_h3_r9_grid.geojson",
    stage: "evidence.bitemporal_grid",
    kind: "count",
    metric: "n_samples",
    legend: "labeled bi-temporal pairs per tile (2024-season cumulative)",
    tier: 3,
    focus: { center: [-83.29, 29.44], zoom: 13 },
  },
  {
    id: "milton-debris",
    event: "milton-2024",
    label: "Debris volume (Pinellas County)",
    url: "/events/milton-2024/exposure/debris_h3_r9_grid.geojson",
    stage: "exposure.debris_grid",
    kind: "volume",
    metric: "VolBoth_sum",
    legend: "county debris-program volume per tile",
    tier: 2,
    focus: { center: [-82.72, 27.9], zoom: 10.5 },
  },
];

export const RAMP = ["#1d4f3f", "#2e7d5b", "#7fb069", "#e6c229", "#e07a2f", "#c92a2a"];
