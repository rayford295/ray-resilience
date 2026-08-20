// Validity badges: the harness state of the layer you are looking at,
// rendered with the same prominence as the data itself.

export function ValidityBadge({ validity }) {
  if (!validity) return <span className="badge pending">checks: loading…</span>;
  if (validity.ok) {
    return (
      <span className="badge ok" title="every outcome check on this stage passed">
        ✓ {validity.nChecks} checks passed
      </span>
    );
  }
  return (
    <span
      className="badge fail"
      title={validity.failedChecks.map((c) => `${c.check}: ${c.detail}`).join("\n")}
    >
      ⚠ {validity.nFailed} of {validity.nChecks} checks failed
    </span>
  );
}

export function TierBadge({ tier }) {
  const label = { 1: "Tier 1 · watch", 2: "Tier 2 · analysis", 3: "Tier 3 · evidence" }[tier];
  return <span className="badge tier">{label}</span>;
}

export function LiveWatchBadge({ live }) {
  if (!live) return <span className="badge pending">live watch: checking…</span>;
  if (live.status === "ok") {
    return (
      <span className="badge ok">
        live watch: {live.data.features?.length ?? 0} active hazards
      </span>
    );
  }
  return (
    <span className="badge stale" title={live.reason}>
      live watch unavailable — no nationwide layer shown (declared, not faked)
    </span>
  );
}
