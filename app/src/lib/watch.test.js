// The live-watch badge said "882 active hazards". The watch product's own
// status file said, in the same breath, that 198 features were not displayed
// for want of mappable geometry — so the real count was 1,080, and the badge
// reported the mappable subset as the whole.
//
// The pipeline already declares this. watch_status.json is built, published,
// and served; nothing read it. A declared unknown with no consumer is not a
// declaration, and the README promises these are rendered with the same
// prominence as findings.

import { describe, expect, it } from "vitest";
import { watchSummary } from "./watch.js";

const status = (unknowns, sources = ["usgs", "nws", "nhc", "nifc"]) => ({
  status: "ok",
  data: {
    generated_utc: "20260820T195059Z",
    sources,
    declared_unknowns: unknowns,
    checks: [{ check: "crs", passed: true }],
  },
});

const live = (n) => ({
  status: "ok",
  data: { features: Array.from({ length: n }, (_, i) => ({ id: i })) },
});

describe("watchSummary", () => {
  it("reports mapped and undisplayed counts from the declared unknown", () => {
    const summary = watchSummary(
      live(882),
      status(["198 feature(s) not displayed (no mappable geometry or malformed); 0 dropped by bounds checks."])
    );
    expect(summary.mapped).toBe(882);
    expect(summary.undisplayed).toBe(198);
    expect(summary.total).toBe(1080);
  });

  it("keeps every declared unknown for display, not just the countable one", () => {
    const summary = watchSummary(
      live(10),
      status([
        "Watch data supports monitoring only; no damage or exposure conclusions.",
        "5 feature(s) not displayed (no mappable geometry or malformed); 0 dropped by bounds checks.",
      ])
    );
    expect(summary.unknowns).toHaveLength(2);
    expect(summary.undisplayed).toBe(5);
  });

  it("reports undisplayed as unknown when the status file is unavailable", () => {
    // Without the status file the badge cannot claim the count is complete.
    // Saying "882 active hazards" here would be the original bug restated.
    const summary = watchSummary(live(882), { status: "unavailable", reason: "404" });
    expect(summary.mapped).toBe(882);
    expect(summary.undisplayed).toBeNull();
    expect(summary.total).toBeNull();
    expect(summary.statusAvailable).toBe(false);
  });

  it("does not invent a count when the phrasing changes", () => {
    // Parsing prose is brittle by nature, so an unrecognised declaration must
    // degrade to "not stated" rather than to zero.
    const summary = watchSummary(live(5), status(["some features were skipped"]));
    expect(summary.undisplayed).toBeNull();
    expect(summary.unknowns).toHaveLength(1);
  });

  it("reports zero undisplayed distinctly from unknown", () => {
    const summary = watchSummary(
      live(5),
      status(["0 feature(s) not displayed (no mappable geometry or malformed); 0 dropped by bounds checks."])
    );
    expect(summary.undisplayed).toBe(0);
    expect(summary.total).toBe(5);
    expect(summary.complete).toBe(true);
  });

  it("surfaces failed sources rather than a silently shorter list", () => {
    const summary = watchSummary(live(5), {
      status: "ok",
      data: {
        generated_utc: "20260820T195059Z",
        sources: ["usgs", "nws"],
        failures: { nhc: "timeout", nifc: "500" },
        declared_unknowns: [],
      },
    });
    expect(summary.failedSources).toEqual([
      { source: "nhc", error: "timeout" },
      { source: "nifc", error: "500" },
    ]);
  });

  it("returns no summary when the watch layer itself is unavailable", () => {
    const summary = watchSummary({ status: "unavailable", reason: "offline" }, status([]));
    expect(summary.mapped).toBeNull();
    expect(summary.available).toBe(false);
  });

  it("carries the failure reason through so the badge can show it", () => {
    const summary = watchSummary({ status: "unavailable", reason: "404 | 404" }, status([]));
    expect(summary.reason).toBe("404 | 404");
  });

  it("exposes the generation timestamp so staleness is visible", () => {
    const summary = watchSummary(live(5), status([]));
    expect(summary.generatedUtc).toBe("20260820T195059Z");
  });
});
