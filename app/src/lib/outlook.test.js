import { describe, expect, it } from "vitest";
import { HAZARD_TYPES, hazardCounts, outlookColor, outlookSummary } from "./outlook.js";

const outlookFc = {
  properties: { issue_time: "2026-09-02 00:50:00", declared_boundary: "Outlook only — …" },
  features: [
    { properties: { level: 1 } },
    { properties: { level: 1 } },
    { properties: { level: 3 } },
  ],
};

describe("outlookSummary", () => {
  it("lists only the levels present, with counts and the product's own boundary", () => {
    const s = outlookSummary(outlookFc);
    expect(s.levels.map((l) => [l.label, l.count])).toEqual([["Marginal", 2], ["Moderate", 1]]);
    expect(s.boundary).toMatch(/Outlook only/);
    expect(s.issueTime).toBe("2026-09-02 00:50:00");
  });

  it("returns null for an absent or unreadable product — no invented legend", () => {
    expect(outlookSummary(null)).toBeNull();
    expect(outlookSummary({ error: "x" })).toBeNull();
  });
});

describe("outlookColor", () => {
  it("escalates and falls back to neutral for unknown levels", () => {
    expect(outlookColor(1)).not.toBe(outlookColor(4));
    expect(outlookColor(99)).toBe("#64748b");
  });
});

describe("hazardCounts", () => {
  it("counts per hazard type from an ok live product", () => {
    const live = { status: "ok", data: { features: [
      { properties: { hazard: "wildfire" } },
      { properties: { hazard: "wildfire" } },
      { properties: { hazard: "earthquake" } },
    ] } };
    const c = hazardCounts(live);
    expect(c.get("wildfire")).toBe(2);
    expect(c.get("earthquake")).toBe(1);
  });

  it("returns null when the live layer is unavailable", () => {
    expect(hazardCounts({ status: "unavailable" })).toBeNull();
  });

  it("exactly one hazard type is an advisory, not an occurrence", () => {
    expect(HAZARD_TYPES.filter((t) => !t.occurring).map((t) => t.key)).toEqual(["weather_alert"]);
  });
});
