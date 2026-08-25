import { describe, expect, it } from "vitest";
import { bboxFromCorners, cellsInBox } from "./area.js";

describe("bboxFromCorners", () => {
  it("normalises corners dragged in any direction", () => {
    const a = { lat: 34.2, lng: -118.06 };
    const b = { lat: 34.15, lng: -118.16 };
    expect(bboxFromCorners(a, b)).toEqual({
      min_lat: 34.15, min_lon: -118.16, max_lat: 34.2, max_lon: -118.06,
    });
    // Dragging the other way must give the same box.
    expect(bboxFromCorners(b, a)).toEqual(bboxFromCorners(a, b));
  });
});

describe("cellsInBox", () => {
  const box = { min_lat: 0, min_lon: 0, max_lat: 1, max_lon: 1 };
  const centres = { in: [0.5, 0.5], out: [5, 5], edge: [1, 1] };
  const cellToLatLng = (c) => centres[c];

  it("keeps cells whose centre is inside, including on the edge", () => {
    expect(cellsInBox(["in", "out", "edge"], box, cellToLatLng)).toEqual(["in", "edge"]);
  });

  it("returns nothing for an empty cell list", () => {
    expect(cellsInBox([], box, cellToLatLng)).toEqual([]);
  });
});
