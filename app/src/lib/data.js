// Data access: artifact fetching, manifest/audit parsing, geocoding, and
// the client-side priority score. All fetch failures surface as explicit
// status objects — the UI renders unavailability, it never papers over it.

const cache = new Map();

/** App-internal artifact paths resolve against the deploy base ("./" on
 * GitHub Pages under /GeoSteward/); absolute http(s) URLs pass through. */
export function resolveUrl(url) {
  if (/^https?:/.test(url)) return url;
  return import.meta.env.BASE_URL.replace(/\/$/, "") + url;
}

export async function fetchJson(rawUrl) {
  const url = resolveUrl(rawUrl);
  if (cache.has(url)) return cache.get(url);
  const promise = fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`);
    return r.json();
  });
  cache.set(url, promise);
  promise.catch(() => cache.delete(url));
  return promise;
}

export async function fetchJsonl(rawUrl) {
  const url = resolveUrl(rawUrl);
  const key = `jsonl:${url}`;
  if (cache.has(key)) return cache.get(key);
  const promise = fetch(url).then(async (r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`);
    const text = await r.text();
    return text
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line));
  });
  cache.set(key, promise);
  promise.catch(() => cache.delete(key));
  return promise;
}

/**
 * Harness check summary for one pipeline stage, grouped by run.
 *
 * A stage can run more than once: the harness fails closed, the maintainer
 * fixes the input, the stage runs again. The audit log is append-only, so both
 * attempts are in there. Summing every check row and taking pass/fail from the
 * last stage row produces a sentence about no run in particular — "9 checks
 * passed" for eaton-2025's SVI stage, where the successful run had six and an
 * earlier one failed.
 *
 * Runs are recovered from two structural markers, not from timestamps:
 *
 *   - a `stage` row closes the run it belongs to;
 *   - a check whose name repeats the open run's *first* check name means the
 *     stage's fixed check sequence started over, so the previous attempt died
 *     without writing a stage row.
 *
 * Timestamps cannot do this job. eaton-2025's SVI stage aborted two minutes
 * before its successful re-run, but ian-2022's sample-density stage writes one
 * sequence across a second boundary — grouping by timestamp would merge the
 * first pair and split the second. `run_id`, stamped by the harness on new
 * runs, supersedes both markers when present; the sequence heuristic exists
 * only for logs written before it, which are append-only and never rewritten.
 */
export function stageValidity(auditRows, stage) {
  const rows = auditRows.filter((r) => r.actor === stage);
  const runs = [];
  let current = null;

  const open = (runId) => {
    current = { runId, checks: [], status: "aborted", utc: null };
    runs.push(current);
    return current;
  };

  for (const row of rows) {
    const runId = row.run_id ?? null;
    const name = row.payload?.check;
    const sequenceRestarted =
      current !== null &&
      row.action === "check" &&
      current.checks.length > 0 &&
      name === current.checks[0].check;

    if (current === null || sequenceRestarted || (runId !== null && runId !== current.runId)) {
      open(runId);
    }
    current.utc = row.utc ?? current.utc;
    if (row.action === "check") {
      current.checks.push(row.payload);
    } else {
      current.status = row.payload?.status ?? "unknown";
      if (runId === null) current = null; // the stage row closes this run
    }
  }

  const summaries = runs.map((run) => {
    const failedChecks = run.checks.filter((c) => !c.passed);
    return {
      nChecks: run.checks.length,
      nFailed: failedChecks.length,
      failedChecks,
      status: run.status,
      utc: run.utc,
      ok: run.status === "ok" && failedChecks.length === 0,
    };
  });

  const latest = summaries.length ? summaries[summaries.length - 1] : null;
  return {
    latest,
    superseded: summaries.slice(0, -1),
    ok: Boolean(latest?.ok),
  };
}

/** Manifest rows for the artifact behind a view (newest last). */
export function artifactLineage(manifestRows, artifactPath) {
  return manifestRows.filter((r) => r.path.endsWith(artifactPath.split("/").pop()));
}

/**
 * Multi-objective priority: t weights structural damage against social
 * vulnerability. Both inputs are [0,1]; missing values contribute 0 and are
 * counted so the UI can say how many tiles are partially scored.
 */
export function priorityScores(features, t) {
  let missing = 0;
  const scores = new Map();
  for (const f of features) {
    const p = f.properties;
    const damage = typeof p.destroyed_rate === "number" ? p.destroyed_rate : null;
    const svi = typeof p.RPL_THEMES === "number" ? p.RPL_THEMES : null;
    if (damage === null || svi === null) missing += 1;
    const score = t * (damage ?? 0) + (1 - t) * (svi ?? 0);
    scores.set(p.h3_cell, { score, damage, svi, n: p.n_structures ?? null });
  }
  return { scores, missing };
}

export function topCells(scores, n = 10) {
  return [...scores.entries()]
    .sort((a, b) => b[1].score - a[1].score)
    .slice(0, n)
    .map(([cell, v]) => ({ cell, ...v }));
}

/** US Census geocoder (free, no key). Returns null when nothing matches. */
export async function geocodeAddress(oneline) {
  const url =
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" +
    new URLSearchParams({
      address: oneline,
      benchmark: "Public_AR_Current",
      format: "json",
    });
  const r = await fetch(url);
  if (!r.ok) throw new Error(`geocoder ${r.status}`);
  const data = await r.json();
  const match = data?.result?.addressMatches?.[0];
  if (!match) return null;
  return {
    lon: match.coordinates.x,
    lat: match.coordinates.y,
    matched: match.matchedAddress,
  };
}

/**
 * Tier-1 live watch. Preferred source: the Pages tree (/live/, republished
 * hourly by the deploy workflow, works while the repo is private). Fallback:
 * the live-data branch raw URL (works once the repo is public). When both
 * fail the UI shows a declared-unavailable badge — graceful degradation is
 * part of the design, not a bug.
 */
const LIVE_SOURCES = [
  "../live/products/national_watch.geojson",
  "https://raw.githubusercontent.com/rayford295/GeoSteward/live-data/live/products/national_watch.geojson",
];

export async function fetchLiveWatch() {
  const reasons = [];
  for (const url of LIVE_SOURCES) {
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      if (!Array.isArray(data.features)) throw new Error("not a FeatureCollection");
      return { status: "ok", data, source: url, fetchedUtc: new Date().toISOString() };
    } catch (err) {
      reasons.push(`${url}: ${err}`);
    }
  }
  return { status: "unavailable", reason: reasons.join(" | ") };
}

/** Local audit trail for HITL adjustments (design: POST to gateway; that
 * plane doesn't exist yet, so records queue locally and say so). */
const localAudit = [];
export function recordAdjustment(payload) {
  localAudit.push({
    action: "human_adjustment",
    actor: "planner-ui",
    utc: new Date().toISOString(),
    payload,
    delivery: "local-only (agent gateway pending)",
  });
  return localAudit;
}
export function getLocalAudit() {
  return localAudit;
}
