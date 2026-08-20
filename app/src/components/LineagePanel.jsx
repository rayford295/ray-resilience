import { getLocalAudit } from "../lib/data.js";

/**
 * Lineage viewer: from the visible layer back to timestamped, hashed
 * sources — manifest rows, harness checks, and any local HITL adjustments.
 */
export default function LineagePanel({ view, lineage, validity }) {
  const localAudit = getLocalAudit();
  return (
    <div className="lineage">
      <h3>Lineage — {view.label}</h3>
      {!lineage?.length && <p className="hint">manifest loading…</p>}
      {lineage?.map((row, i) => (
        <div className="artifact" key={`${row.sha256}-${i}`}>
          <div className="mono">{row.path}</div>
          <div className="dim">
            {row.agent} · {row.created_utc} · sha256 {row.sha256.slice(0, 12)}…
          </div>
          {row.inputs?.length > 0 && (
            <div className="dim">inputs: {row.inputs.slice(0, 4).join(", ")}
              {row.inputs.length > 4 ? ` (+${row.inputs.length - 4} more)` : ""}
            </div>
          )}
          {row.notes && <div className="notes">{row.notes}</div>}
        </div>
      ))}
      {lineage?.length > 1 && (
        <p className="hint">
          {lineage.length} manifest rows: this artifact was rebuilt — append-only
          history keeps every version's provenance.
        </p>
      )}

      <h4>Harness checks on this stage</h4>
      {validity ? (
        <p className={validity.ok ? "ok-text" : "fail-text"}>
          {validity.nChecks - validity.nFailed}/{validity.nChecks} outcome checks passed
          {validity.nFailed > 0 &&
            ` — failures are preserved in the audit log, not erased`}
        </p>
      ) : (
        <p className="hint">audit log loading…</p>
      )}

      {localAudit.length > 0 && (
        <>
          <h4>Your adjustments (audited)</h4>
          <p className="hint">
            {localAudit.length} slider move{localAudit.length > 1 ? "s" : ""} recorded
            locally — will POST to the agent gateway once it ships.
          </p>
        </>
      )}
    </div>
  );
}
