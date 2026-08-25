/**
 * Geometry for a drawn selection. Kept out of the component so it can be
 * tested: a bbox computed inside a React render is a bbox nobody checks.
 */

/** Normalise two drag corners into a WGS84 bounding box, in the key order the gateway speaks. */
export function bboxFromCorners(a, b) {
  return {
    min_lat: Math.min(a.lat, b.lat),
    min_lon: Math.min(a.lng, b.lng),
    max_lat: Math.max(a.lat, b.lat),
    max_lon: Math.max(a.lng, b.lng),
  };
}

/**
 * Which of these cells have their centre inside the box. Edges count, matching
 * the gateway's `boxes_intersect`, so the two sides agree about a selection
 * dragged flush to a boundary.
 */
export function cellsInBox(cells, bbox, cellToLatLng) {
  return cells.filter((cell) => {
    const [lat, lon] = cellToLatLng(cell);
    return (
      lat >= bbox.min_lat && lat <= bbox.max_lat &&
      lon >= bbox.min_lon && lon <= bbox.max_lon
    );
  });
}
