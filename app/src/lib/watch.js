// What the nationwide watch layer is, and what it is missing.
//
// The watch pipeline already declares its own gaps: watch_status.json records
// per-source health and a declared unknown counting features it could not map.
// Nothing read it, so the badge reported the mappable subset — 882 — as though
// it were the whole hazard count, when 198 more had been fetched and dropped
// for want of usable geometry.
//
// Counting what you dropped and then displaying only what you kept is a
// smaller failure than fabricating a layer, and the same kind: the number is
// presented as more complete than it is.

/** Declared unknowns are prose. This is the one shape the pipeline emits. */
const UNDISPLAYED = /^(\d+)\s+feature\(s\)\s+not\s+displayed/i;

/**
 * Merge the watch layer with its status product into one display summary.
 *
 * Every count is nullable, and null means "not stated" rather than zero.
 * Prose parsing is brittle by nature: if the pipeline rephrases its declared
 * unknown, this must fall back to admitting it does not know how many features
 * were dropped, never to implying none were.
 */
export function watchSummary(live, status) {
  const available = live?.status === "ok";
  const mapped = available ? (live.data.features?.length ?? 0) : null;

  const statusAvailable = status?.status === "ok";
  const unknowns = statusAvailable ? (status.data.declared_unknowns ?? []) : [];
  const failures = statusAvailable ? (status.data.failures ?? {}) : {};

  let undisplayed = null;
  for (const unknown of unknowns) {
    const match = UNDISPLAYED.exec(unknown.trim());
    if (match) undisplayed = Number(match[1]);
  }

  return {
    available,
    reason: available ? null : (live?.reason ?? null),
    statusAvailable,
    mapped,
    undisplayed,
    total: mapped !== null && undisplayed !== null ? mapped + undisplayed : null,
    complete: undisplayed === 0,
    unknowns,
    failedSources: Object.entries(failures).map(([source, error]) => ({ source, error })),
    sources: statusAvailable ? (status.data.sources ?? []) : [],
    generatedUtc: statusAvailable ? (status.data.generated_utc ?? null) : null,
  };
}
