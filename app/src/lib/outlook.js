// The flash-flood outlook's display vocabulary, shared by the map paint and
// the legend chips so the two cannot drift. Levels are WPC's own ordinal
// scale; the colors escalate monotonically (amber -> fuchsia) rather than
// starting at green — on a resident-facing map, green under a flood outlook
// would read as "safe", which is not what Marginal means.

export const OUTLOOK_LEVELS = [
  { level: 1, label: "Marginal", color: "#f59e0b" },
  { level: 2, label: "Slight", color: "#f97316" },
  { level: 3, label: "Moderate", color: "#dc2626" },
  { level: 4, label: "High", color: "#a21caf" },
];

export function outlookColor(level) {
  return OUTLOOK_LEVELS.find((l) => l.level === level)?.color ?? "#64748b";
}

/** Counts per level actually present in the product — the legend shows what
 * is on the map today, not every category that could exist. */
export function outlookSummary(geojson) {
  if (!geojson || geojson.error || !Array.isArray(geojson.features)) return null;
  const counts = new Map();
  for (const f of geojson.features) {
    const lvl = f.properties?.level;
    if (typeof lvl === "number") counts.set(lvl, (counts.get(lvl) ?? 0) + 1);
  }
  return {
    issueTime: geojson.properties?.issue_time ?? null,
    boundary: geojson.properties?.declared_boundary ?? null,
    levels: OUTLOOK_LEVELS.filter((l) => counts.has(l.level)).map((l) => ({
      ...l,
      count: counts.get(l.level),
    })),
  };
}

// Live watch hazard vocabulary: one color per hazard type, and one visual
// distinction that matters more than color — NWS weather alerts are
// *advisories about what may come*, while the other three sources report
// what is happening. The map renders alerts hollow so the two claims never
// look like the same kind of dot.
export const HAZARD_TYPES = [
  { key: "earthquake", label: "Earthquakes", color: "#7c3aed", occurring: true },
  { key: "wildfire", label: "Wildfires", color: "#ea580c", occurring: true },
  { key: "tropical_cyclone", label: "Tropical cyclones", color: "#1d4ed8", occurring: true },
  { key: "weather_alert", label: "NWS alerts", color: "#0891b2", occurring: false },
];

export function hazardCounts(live) {
  if (live?.status !== "ok") return null;
  const counts = new Map();
  for (const f of live.data.features ?? []) {
    const h = f.properties?.hazard;
    if (h) counts.set(h, (counts.get(h) ?? 0) + 1);
  }
  return counts;
}
