import { describe, expect, it } from "vitest";
import { facilitiesNear, haversineKm } from "./facilities.js";

const point = (lon, lat, name, category = "hospital") => ({
  geometry: { type: "Point", coordinates: [lon, lat] },
  properties: { name, category },
});

describe("haversineKm", () => {
  it("is zero at the same point and ~111 km per degree of latitude", () => {
    expect(haversineKm(34, -118, 34, -118)).toBe(0);
    expect(haversineKm(34, -118, 35, -118)).toBeGreaterThan(110);
    expect(haversineKm(34, -118, 35, -118)).toBeLessThan(112);
  });
});

describe("facilitiesNear", () => {
  const fc = {
    features: [
      point(-118.1, 34.19, "Near Hospital"),
      point(-118.105, 34.192, "Nearer Clinic", "clinic"),
      point(-118.3, 34.19, "Far Station", "fire_station"), // ~18 km west
    ],
  };

  it("returns only facilities inside the radius, nearest first", () => {
    const out = facilitiesNear(fc, 34.192, -118.104, 1);
    expect(out.map((f) => f.name)).toEqual(["Nearer Clinic", "Near Hospital"]);
    expect(out[0].km).toBeLessThan(out[1].km);
  });

  it("distinguishes 'layer unreadable' (null) from 'none nearby' ([])", () => {
    expect(facilitiesNear(null, 34, -118)).toBeNull();
    expect(facilitiesNear({ error: "boom" }, 34, -118)).toBeNull();
    expect(facilitiesNear(fc, 0, 0, 1)).toEqual([]);
  });

  it("skips malformed geometries rather than crashing on them", () => {
    const broken = { features: [{ properties: { name: "x" } }, ...fc.features] };
    expect(facilitiesNear(broken, 34.192, -118.104, 1)).toHaveLength(2);
  });
});
