import { describe, expect, it } from "vitest";
import { legendScale, percentile, rampMax } from "./legend.js";

const fc = (values) => ({
  type: "FeatureCollection",
  features: values.map((v) => ({ properties: { n: v } })),
});

describe("rampMax", () => {
  it("is 1 for rate and priority views regardless of data", () => {
    expect(rampMax({ kind: "rate", metric: "n" }, fc([5, 9]))).toBe(1);
    expect(rampMax({ kind: "priority" }, undefined)).toBe(1);
  });

  it("uses the data max for count views", () => {
    expect(rampMax({ kind: "count", metric: "n" }, fc([2, 7, 4]))).toBe(7);
  });

  it("caps volume views at the 95th percentile, not the outlier", () => {
    const values = [...Array.from({ length: 99 }, (_, i) => i + 1), 10000];
    expect(rampMax({ kind: "volume", metric: "n" }, fc(values))).toBeLessThan(10000);
  });

  it("ignores non-numeric values and never returns less than 1 for counts", () => {
    expect(rampMax({ kind: "count", metric: "n" }, fc(["x", null, 0.5]))).toBe(1);
  });
});

describe("legendScale", () => {
  it("returns null while a layer is still loading — no invented scale", () => {
    expect(legendScale({ kind: "count", metric: "n" }, undefined)).toBeNull();
    expect(legendScale({ kind: "count", metric: "n" }, fc([]))).toBeNull();
  });

  it("returns null when the metric has no numeric values", () => {
    expect(legendScale({ kind: "count", metric: "missing" }, fc([1, 2]))).toBeNull();
  });

  it("marks rates as percent and volumes as capped", () => {
    expect(legendScale({ kind: "rate", metric: "n" }, fc([1]))).toMatchObject({
      percent: true,
      capped: false,
    });
    expect(legendScale({ kind: "volume", metric: "n" }, fc([1, 2, 3]))).toMatchObject({
      percent: false,
      capped: true,
    });
  });

  it("agrees with rampMax — the legend can never drift from the paint", () => {
    const view = { kind: "count", metric: "n" };
    const data = fc([3, 11, 6]);
    expect(legendScale(view, data).max).toBe(rampMax(view, data));
  });
});

describe("percentile", () => {
  it("returns 1 for an empty list (the paint fallback)", () => {
    expect(percentile([], 0.95)).toBe(1);
  });
});
