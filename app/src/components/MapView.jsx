import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { EVENTS, RAMP } from "../lib/views.js";
import { priorityScores } from "../lib/data.js";

const BASEMAP = "https://tiles.openfreemap.org/styles/liberty";
const SRC = "grid";

function rampExpr(input, max) {
  const stops = RAMP.flatMap((color, i) => [(max * i) / (RAMP.length - 1), color]);
  return ["interpolate", ["linear"], input, ...stops];
}

function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.floor((sorted.length - 1) * p)] : 1;
}

function paintFor(view, geojson) {
  if (view.kind === "priority") {
    return rampExpr(["coalesce", ["feature-state", "score"], 0], 1);
  }
  if (view.kind === "rate") {
    return rampExpr(["coalesce", ["get", view.metric], 0], 1);
  }
  const values = geojson.features
    .map((f) => f.properties[view.metric])
    .filter((v) => typeof v === "number");
  const max = view.kind === "volume" ? percentile(values, 0.95) : Math.max(...values, 1);
  return rampExpr(["coalesce", ["get", view.metric], 0], max);
}

export default function MapView({ view, geojson, priorityT, flyTarget, onSelect }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP,
      center: EVENTS["eaton-2025"].center,
      zoom: EVENTS["eaton-2025"].zoom,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.GeolocateControl({ trackUserLocation: true }), "top-right");
    map.on("load", () => setReady(true));
    mapRef.current = map;
    return () => map.remove();
  }, []);

  // Swap the grid layer whenever the active view's data arrives.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !geojson) return;
    for (const id of ["grid-fill", "grid-line"]) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource(SRC)) map.removeSource(SRC);
    map.addSource(SRC, { type: "geojson", data: geojson, promoteId: "h3_cell" });
    map.addLayer({
      id: "grid-fill",
      type: "fill",
      source: SRC,
      paint: { "fill-color": paintFor(view, geojson), "fill-opacity": 0.62 },
    });
    map.addLayer({
      id: "grid-line",
      type: "line",
      source: SRC,
      paint: { "line-color": "#0b1c30", "line-width": 0.4, "line-opacity": 0.5 },
    });
    const click = (e) => {
      const f = e.features?.[0];
      if (f) onSelect(f.properties);
    };
    map.on("click", "grid-fill", click);
    map.on("mouseenter", "grid-fill", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "grid-fill", () => (map.getCanvas().style.cursor = ""));
    return () => map.off("click", "grid-fill", click);
  }, [ready, geojson, view, onSelect]);

  // Planner slider: recompute priority scores client-side (feature-state,
  // no layer rebuild) — the instant-response requirement from the design.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !geojson || view.kind !== "priority") return;
    if (!map.getSource(SRC)) return;
    const { scores } = priorityScores(geojson.features, priorityT);
    for (const [cell, v] of scores) {
      map.setFeatureState({ source: SRC, id: cell }, { score: v.score });
    }
  }, [ready, geojson, view, priorityT]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTarget) return;
    map.flyTo({ center: flyTarget.center, zoom: flyTarget.zoom, essential: true });
  }, [flyTarget]);

  return <div ref={containerRef} className="map" />;
}
