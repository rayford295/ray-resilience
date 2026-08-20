import { useMemo } from "react";
import { priorityScores, topCells, recordAdjustment } from "../lib/data.js";
import { cellToLatLng } from "h3-js";

export default function PlannerPanel({ view, geojson, t, onT, onFlyToCell }) {
  const isPriority = view.kind === "priority";
  const ranking = useMemo(() => {
    if (!isPriority || !geojson) return null;
    const { scores, missing } = priorityScores(geojson.features, t);
    return { top: topCells(scores, 10), missing, total: scores.size };
  }, [isPriority, geojson, t]);

  if (!isPriority) {
    return (
      <p className="hint">
        Trade-off sliders apply to the <strong>Damage × SVI priority</strong> layer —
        switch to it to re-weight inspection priorities.
      </p>
    );
  }

  return (
    <div>
      <label className="slider-label">
        <span>social vulnerability</span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={t}
          onChange={(e) => {
            const value = Number(e.target.value);
            onT(value);
            recordAdjustment({ control: "damage_vs_svi", t: value });
          }}
        />
        <span>structural damage</span>
      </label>
      <p className="hint">
        priority = {t.toFixed(2)} × damage + {(1 - t).toFixed(2)} × SVI · every move is
        audit-logged (local until the gateway ships)
      </p>
      {ranking && (
        <>
          <h3>Top priority tiles</h3>
          {ranking.missing > 0 && (
            <p className="hint">
              {ranking.missing} of {ranking.total} tiles scored with partial data
              (missing damage or SVI counted as 0 — declared, not imputed).
            </p>
          )}
          <ol className="ranking">
            {ranking.top.map((row) => (
              <li key={row.cell}>
                <button
                  onClick={() => {
                    const [lat, lng] = cellToLatLng(row.cell);
                    onFlyToCell({ center: [lng, lat], zoom: 14 });
                  }}
                >
                  <code>{row.cell.slice(0, 9)}…</code> score {row.score.toFixed(2)}
                  {row.n !== null && <span className="dim"> · {row.n} structures</span>}
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
