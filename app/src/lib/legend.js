// The legend and the map fill must never disagree, so the scale they share
// lives here and both import it. MapView paints with rampMax(); the Legend
// component labels the same ramp with the same max. A legend computed by a
// second code path would eventually describe a map it no longer matches.

export function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.floor((sorted.length - 1) * p)] : 1;
}

/**
 * The upper bound of a view's color ramp — the exact value MapView feeds to
 * its interpolate expression. Rates and priorities are 0..1 by construction;
 * counts run to the data max; volumes cap at the 95th percentile so one
 * outlier tile does not flatten every other tile's color.
 */
export function rampMax(view, geojson) {
  if (view.kind === "priority" || view.kind === "rate") return 1;
  const values = (geojson?.features ?? [])
    .map((f) => f.properties?.[view.metric])
    .filter((v) => typeof v === "number");
  return view.kind === "volume"
    ? percentile(values, 0.95)
    : Math.max(...values, 1);
}

/**
 * What the legend should say about a view, or null when there is nothing
 * honest to say yet (layer still loading, no numeric values).
 *
 * `capped` marks the volume case: the swatch for the max is "p95 and above",
 * and the legend says so instead of pretending the scale ends there.
 */
export function legendScale(view, geojson) {
  if (!view) return null;
  if (view.kind === "priority") {
    return { min: 0, max: 1, percent: false, capped: false };
  }
  if (view.kind === "rate") {
    return { min: 0, max: 1, percent: true, capped: false };
  }
  if (!geojson?.features?.length) return null;
  const values = geojson.features
    .map((f) => f.properties?.[view.metric])
    .filter((v) => typeof v === "number");
  if (!values.length) return null;
  return {
    min: 0,
    max: rampMax(view, geojson),
    percent: false,
    capped: view.kind === "volume",
  };
}
