// Facility proximity for the resident dossier. The artifact records OSM
// *presence*; this module only adds geometry — which recorded points sit
// within a radius of the looked-up address — and the answer must always
// travel with the same qualifier the artifact declares: presence, not
// operational status.

const EARTH_RADIUS_KM = 6371;

export function haversineKm(lat1, lon1, lat2, lon2) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

/**
 * Facilities within `radiusKm` of a point, nearest first.
 *
 * Returns null (not []) when the layer is absent or unreadable: "no
 * facilities recorded nearby" and "the facility layer could not be read"
 * are different statements, and the dossier renders them differently.
 */
export function facilitiesNear(geojson, lat, lon, radiusKm = 1) {
  if (!geojson || geojson.error || !Array.isArray(geojson.features)) return null;
  const out = [];
  for (const f of geojson.features) {
    const [flon, flat] = f.geometry?.coordinates ?? [];
    if (typeof flat !== "number" || typeof flon !== "number") continue;
    const km = haversineKm(lat, lon, flat, flon);
    if (km <= radiusKm) {
      out.push({
        name: f.properties?.name ?? "(unnamed in OSM)",
        category: f.properties?.category ?? "unknown",
        km,
      });
    }
  }
  out.sort((a, b) => a.km - b.km);
  return out;
}
