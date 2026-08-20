// Validity badges: the harness state of the layer you are looking at,
// rendered with the same prominence as the data itself.

/**
 * The badge speaks about one run — the latest one — because that is the only
 * thing a count can be true of. A stage that failed, was fixed, and re-ran
 * leaves both attempts in the append-only log; summing them describes no run
 * that happened. Superseded attempts are shown beside the badge rather than
 * folded into it or hidden: a rejected run is evidence the harness worked.
 */
export function ValidityBadge({ validity }) {
  if (!validity) return <span className="badge pending">checks: loading…</span>;
  const { latest, superseded } = validity;
  if (!latest) {
    return (
      <span className="badge pending" title="no harness run for this stage is recorded">
        checks: not recorded
      </span>
    );
  }
  return (
    <>
      {latest.nChecks === 0 ? (
        <span className="badge ok" title="stage recorded; it declares no outcome checks">
          ✓ recorded · no outcome checks
        </span>
      ) : validity.ok ? (
        <span className="badge ok" title={`latest run ${latest.utc}: every outcome check passed`}>
          ✓ latest run: {latest.nChecks}/{latest.nChecks} checks passed
        </span>
      ) : (
        <span
          className="badge fail"
          title={latest.failedChecks.map((c) => `${c.check}: ${c.detail}`).join("\n")}
        >
          ⚠ latest run: {latest.nFailed} of {latest.nChecks} checks failed
        </span>
      )}
      {superseded.length > 0 && <SupersededBadge runs={superseded} />}
    </>
  );
}

function SupersededBadge({ runs }) {
  const failed = runs.filter((r) => r.nFailed > 0);
  if (failed.length === 0) {
    return (
      <span className="badge tier" title={runs.map((r) => `${r.utc}: ${r.nChecks} checks`).join("\n")}>
        {runs.length} earlier run{runs.length > 1 ? "s" : ""}
      </span>
    );
  }
  return (
    <span
      className="badge stale"
      title={failed
        .flatMap((r) => r.failedChecks.map((c) => `${r.utc} — ${c.check}: ${c.detail}`))
        .join("\n")}
    >
      {failed.length} superseded failed run{failed.length > 1 ? "s" : ""} — kept, not erased
    </span>
  );
}

export function TierBadge({ tier }) {
  const label = { 1: "Tier 1 · watch", 2: "Tier 2 · analysis", 3: "Tier 3 · evidence" }[tier];
  return <span className="badge tier">{label}</span>;
}

/**
 * The nationwide watch layer, reported with its own declared gaps.
 *
 * This used to read "882 active hazards", which was the count of features the
 * pipeline could map — while the same pipeline's status product declared 198
 * more it had fetched and dropped for want of usable geometry. Displaying the
 * kept subset as the total is a quieter failure than faking a layer, and the
 * same kind of failure.
 */
export function LiveWatchBadge({ summary }) {
  if (!summary) return <span className="badge pending">live watch: checking…</span>;
  if (!summary.available) {
    return (
      <span className="badge stale" title={summary.reason}>
        live watch unavailable — no nationwide layer shown (declared, not faked)
      </span>
    );
  }
  return (
    <>
      <span
        className="badge ok"
        title={
          summary.generatedUtc
            ? `watch product generated ${summary.generatedUtc}`
            : "watch status product unavailable"
        }
      >
        live watch: {summary.mapped} hazards mapped
        {summary.total !== null && !summary.complete && ` of ${summary.total}`}
      </span>

      {summary.undisplayed > 0 && (
        <span
          className="badge stale"
          title={summary.unknowns.join("\n")}
        >
          {summary.undisplayed} not mappable — declared, not dropped quietly
        </span>
      )}

      {!summary.statusAvailable && (
        <span className="badge stale" title="live/products/watch_status.json could not be read">
          completeness unknown — status product unreadable
        </span>
      )}

      {summary.failedSources.length > 0 && (
        <span
          className="badge fail"
          title={summary.failedSources.map((f) => `${f.source}: ${f.error}`).join("\n")}
        >
          {summary.failedSources.length} source(s) failed
        </span>
      )}
    </>
  );
}
