/**
 * What a clicked citation resolves to.
 *
 * An [artifact:…] chip resolves to manifest rows — the artifact's committed
 * provenance: path, agent, timestamp, full hash, inputs. A [live:…] chip has
 * no manifest row by design (nothing was retained), so it resolves to an
 * explanation of where the request record lives instead. And when a lookup
 * finds nothing, the card says which of the two empty cases happened rather
 * than showing a blank.
 */
export default function CitationCard({ citation, resolution, loading, onClose }) {
  return (
    <div className="lineage">
      <h3>
        Citation {citation.kind === "live" ? "↻ " : ""}
        <span className="mono">{citation.id}</span>{" "}
        <button type="button" className="linkish dim" onClick={onClose}>
          close
        </button>
      </h3>

      {citation.kind === "live" ? (
        <p className="hint">
          A live third-party lookup: nothing was retained, because the source's
          license forbids keeping a copy. The recorded request and the sha256 of
          the response it got are in <span className="mono">events/live_evidence.jsonl</span>;
          re-issue the request with your own key and compare digests.
        </p>
      ) : loading ? (
        <p className="hint">searching loaded manifests…</p>
      ) : resolution?.status === "found" ? (
        <>
          {resolution.matches.map(({ eventId, row }, i) => (
            <div className="artifact" key={`${row.sha256}-${i}`}>
              <div className="mono">{row.path}</div>
              <div className="dim">
                {eventId} · {row.agent} · {row.created_utc}
              </div>
              <div className="dim mono">sha256 {row.sha256}</div>
              {row.inputs?.length > 0 && (
                <div className="dim">
                  inputs: {row.inputs.slice(0, 4).join(", ")}
                  {row.inputs.length > 4 ? ` (+${row.inputs.length - 4} more)` : ""}
                </div>
              )}
              {row.notes && <div className="notes">{row.notes}</div>}
            </div>
          ))}
          {resolution.matches.length > 1 && (
            <p className="hint">
              {resolution.matches.length} manifest rows share this hash prefix —
              append-only history keeps every build's provenance.
            </p>
          )}
        </>
      ) : resolution?.status === "not_found" ? (
        <p className="hint">
          Not found in any loaded manifest. The answer cited an artifact this
          page has not been able to read — that is a gap to report, not a
          record to invent.
        </p>
      ) : (
        <p className="hint">No manifests are loaded yet.</p>
      )}
    </div>
  );
}
