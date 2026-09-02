import { RAMP } from "../lib/views.js";
import { legendScale } from "../lib/legend.js";

/**
 * Color legend for the active grid layer. The scale comes from the same
 * function the map paint uses (lib/legend.js), so the bar labels exactly
 * what the tiles show. While a layer is loading there is no legend rather
 * than an invented one, and a p95-capped volume scale says it is capped.
 */
export default function Legend({ view, geojson }) {
  const scale = legendScale(view, geojson);
  if (!scale) return null;

  const gradient = `linear-gradient(to right, ${RAMP.join(", ")})`;
  const maxLabel = scale.percent
    ? "100%"
    : Number.isInteger(scale.max)
      ? String(scale.max)
      : scale.max.toFixed(1);

  return (
    <div className="legend">
      <div className="legend-bar" style={{ background: gradient }} />
      <div className="legend-labels">
        <span>{scale.percent ? "0%" : "0"}</span>
        {view.legend && <span className="legend-unit">{view.legend}</span>}
        <span>
          {maxLabel}
          {scale.capped ? "+" : ""}
        </span>
      </div>
      {scale.capped && (
        <p className="hint legend-note">
          color scale capped at the 95th percentile — tiles above it share the
          top color rather than washing out the rest
        </p>
      )}
    </div>
  );
}
