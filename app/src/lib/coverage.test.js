// Resident lookup asks one question — "does Ray Resilience have anything to say
// about this address?" — and there are three honest answers, not two.
//
// The bug this pins down: App.jsx built its grid map keyed by event, so later
// layers of the same event overwrote earlier ones. Eaton's catalog order ends
// on the 109-cell cross-view coverage grid, so 156 of the 265 tiles the event
// actually evaluated resolved to "outside the evaluated deep-case areas".
// Lazy loading made it worse — an untouched layer contributed nothing at all —
// and a failed fetch was indistinguishable from a genuine miss.

import { describe, expect, it } from "vitest";
import { buildCoverageIndex, lookupCoverage } from "./coverage.js";

const cellFeature = (cell, props = {}) => ({
  type: "Feature",
  properties: { h3_cell: cell, ...props },
});

const grid = (...features) => ({ type: "FeatureCollection", features });

describe("buildCoverageIndex", () => {
  it("keeps every layer of an event instead of letting the last one win", () => {
    // The exact shape of the Eaton bug: a wide damage grid and a narrow
    // evidence grid, same event. Both must contribute cells.
    const index = buildCoverageIndex([
      { viewId: "eaton-damage", event: "eaton-2025", geojson: grid(cellFeature("a"), cellFeature("b")) },
      { viewId: "eaton-evidence", event: "eaton-2025", geojson: grid(cellFeature("a")) },
    ]);
    expect(index.cells.size).toBe(2);
    expect(index.cells.get("b")).toHaveLength(1);
  });

  it("merges properties from every layer covering one cell", () => {
    const index = buildCoverageIndex([
      { viewId: "damage", event: "e", geojson: grid(cellFeature("a", { destroyed_rate: 0.5 })) },
      { viewId: "evidence", event: "e", geojson: grid(cellFeature("a", { n_samples: 12 })) },
    ]);
    const hits = index.cells.get("a");
    expect(hits.map((h) => h.viewId).sort()).toEqual(["damage", "evidence"]);
  });

  it("records which layers failed so a miss can be told from ignorance", () => {
    const index = buildCoverageIndex([
      { viewId: "ok", event: "e", geojson: grid(cellFeature("a")) },
      { viewId: "broken", event: "e", error: "404 Not Found" },
    ]);
    expect(index.failed).toEqual([{ viewId: "broken", event: "e", error: "404 Not Found" }]);
  });

  it("treats a layer that has not loaded yet as incomplete, not as empty", () => {
    const index = buildCoverageIndex([
      { viewId: "ok", event: "e", geojson: grid(cellFeature("a")) },
      { viewId: "pending", event: "e" },
    ]);
    expect(index.complete).toBe(false);
    expect(index.pending).toEqual(["pending"]);
  });
});

describe("lookupCoverage", () => {
  const complete = () =>
    buildCoverageIndex([
      { viewId: "damage", event: "eaton-2025", geojson: grid(cellFeature("hit", { destroyed_rate: 0.5 })) },
    ]);

  it("reports covered when a layer contains the cell", () => {
    const result = lookupCoverage(complete(), "hit");
    expect(result.status).toBe("covered");
    expect(result.hits[0].event).toBe("eaton-2025");
  });

  it("reports not_covered only when every layer loaded and none matched", () => {
    const result = lookupCoverage(complete(), "miss");
    expect(result.status).toBe("not_covered");
  });

  it("reports unknown when a layer failed and nothing matched", () => {
    // The claim that matters: with part of the evidence unreadable, "this
    // location is outside the evaluated areas" is not a statement the system
    // is entitled to make.
    const index = buildCoverageIndex([
      { viewId: "damage", event: "eaton-2025", geojson: grid(cellFeature("hit")) },
      { viewId: "evidence", event: "milton-2024", error: "network error" },
    ]);
    const result = lookupCoverage(index, "miss");
    expect(result.status).toBe("unknown");
    expect(result.unreadable).toEqual(["evidence"]);
  });

  it("reports unknown when a layer is still loading and nothing matched", () => {
    const index = buildCoverageIndex([
      { viewId: "damage", event: "eaton-2025", geojson: grid(cellFeature("hit")) },
      { viewId: "evidence", event: "milton-2024" },
    ]);
    expect(lookupCoverage(index, "miss").status).toBe("unknown");
  });

  it("still reports covered when a layer failed but another one matched", () => {
    // A hit is a hit: unreadable layers cannot retract evidence that loaded.
    const index = buildCoverageIndex([
      { viewId: "damage", event: "eaton-2025", geojson: grid(cellFeature("hit")) },
      { viewId: "evidence", event: "milton-2024", error: "network error" },
    ]);
    expect(lookupCoverage(index, "hit").status).toBe("covered");
  });

  it("reports unknown before any layer has loaded", () => {
    const index = buildCoverageIndex([{ viewId: "damage", event: "eaton-2025" }]);
    expect(lookupCoverage(index, "anything").status).toBe("unknown");
  });
});
