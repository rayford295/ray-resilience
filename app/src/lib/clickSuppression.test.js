import { describe, expect, it } from "vitest";
import { isClickSuppressed } from "./clickSuppression.js";

describe("isClickSuppressed", () => {
  it("suppresses before the deadline", () => {
    expect(isClickSuppressed(100, 200)).toBe(true);
  });

  it("suppresses exactly at the deadline", () => {
    expect(isClickSuppressed(200, 200)).toBe(true);
  });

  it("does not suppress after the deadline", () => {
    expect(isClickSuppressed(201, 200)).toBe(false);
  });

  it("never suppresses from the initial until=0 state", () => {
    expect(isClickSuppressed(1, 0)).toBe(false);
    expect(isClickSuppressed(50000, 0)).toBe(false);
  });
});
