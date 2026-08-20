// Where GeoSteward has evaluated, as an index over every layer at once.
//
// Resident lookup used to search whatever layers happened to be loaded, in a
// map keyed by event — so within one event the last layer in the catalog
// overwrote the rest. Eaton ends on the 109-cell cross-view coverage grid, so
// 156 of the 265 tiles the event had actually evaluated came back as
// "outside the evaluated deep-case areas". Told to a resident about their own
// address, that is the worst kind of wrong this app can be: confidently
// negative about somewhere it had data for.
//
// Two properties fix it. Coverage is the union across layers, not the last
// one to win. And a lookup distinguishes three states, because "no evidence
// covers you" and "I could not read some of the evidence" are different
// sentences and only one of them is a claim about the world.

/**
 * Index layers into a cell -> hits map.
 *
 * `layers` is one entry per catalog view: {viewId, event, geojson} when it
 * loaded, {viewId, event, error} when the fetch failed, and neither when it
 * has not been requested yet. The last case is deliberately not treated as
 * empty — an unrequested layer is unknown coverage, not absent coverage.
 */
export function buildCoverageIndex(layers) {
  const cells = new Map();
  const failed = [];
  const pending = [];

  for (const layer of layers) {
    if (layer.error) {
      failed.push({ viewId: layer.viewId, event: layer.event, error: layer.error });
      continue;
    }
    if (!layer.geojson) {
      pending.push(layer.viewId);
      continue;
    }
    for (const feature of layer.geojson.features ?? []) {
      const cell = feature.properties?.h3_cell;
      if (!cell) continue;
      const hits = cells.get(cell) ?? [];
      hits.push({ viewId: layer.viewId, event: layer.event, props: feature.properties });
      cells.set(cell, hits);
    }
  }

  return {
    cells,
    failed,
    pending,
    complete: failed.length === 0 && pending.length === 0,
  };
}

/**
 * Resolve one H3 cell against the index.
 *
 * `covered`     — at least one layer contains the cell; cite it.
 * `not_covered` — every layer loaded and none contains it; the honest
 *                 statement that competence is conditional on place.
 * `unknown`     — nothing matched, but some evidence is unreadable or not yet
 *                 read, so `not_covered` would be a guess dressed as a fact.
 *
 * A hit outranks unreadable layers: evidence that loaded cannot be retracted
 * by evidence that did not.
 */
export function lookupCoverage(index, cell) {
  const hits = index.cells.get(cell);
  if (hits?.length) {
    return { status: "covered", hits, incomplete: !index.complete };
  }
  if (!index.complete) {
    return {
      status: "unknown",
      hits: [],
      unreadable: index.failed.map((f) => f.viewId),
      unread: index.pending,
    };
  }
  return { status: "not_covered", hits: [] };
}

/** Distinct events contributing coverage to a set of hits. */
export function eventsOf(hits) {
  return [...new Set(hits.map((h) => h.event))];
}

/** All properties covering a cell, merged newest-last for display. */
export function mergedProps(hits) {
  return Object.assign({}, ...hits.map((h) => h.props));
}
