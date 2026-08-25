import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { EVENTS, RAMP } from "../lib/views.js";
import { priorityScores } from "../lib/data.js";
import { bboxFromCorners } from "../lib/area.js";

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

export default function MapView({
  view,
  geojson,
  priorityT,
  flyTarget,
  onSelect,
  onAreaSelect,
  live,
  onCenter,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [dragBox, setDragBox] = useState(null); // {left, top, width, height} px, or null

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
    map.on("load", () => {
      setReady(true);
      onCenter?.(map.getCenter());
    });
    map.on("moveend", () => onCenter?.(map.getCenter()));
    mapRef.current = map;
    return () => map.remove();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Tier-1 national watch: live hazard points over whatever view is active.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || live?.status !== "ok") return;
    if (map.getSource("live")) return;
    map.addSource("live", { type: "geojson", data: live.data });
    map.addLayer({
      id: "live-points",
      type: "circle",
      source: "live",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 2.5, 10, 6],
        "circle-color": "#6fd3a8",
        "circle-opacity": 0.75,
        "circle-stroke-color": "#0b1c30",
        "circle-stroke-width": 0.8,
      },
    });
    map.on("click", "live-points", (e) => {
      const f = e.features?.[0];
      if (f) onSelect(f.properties);
    });
  }, [ready, live, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTarget) return;
    map.flyTo({ center: flyTarget.center, zoom: flyTarget.zoom, essential: true });
  }, [flyTarget]);

  // Shift-drag box-select for the planner's "ask about this area" flow.
  // Plain drag must keep panning — a planner navigates far more often than
  // they select an area — so the gesture rides on a modifier key rather than
  // taking over the map's primary interaction.
  useEffect(() => {
    const map = mapRef.current;
    const container = containerRef.current;
    if (!map || !container || !onAreaSelect) return;

    let drag = null; // {x, y} start point, in container-relative pixels
    let suppressClick = false; // swallow the click a completed drag leaves behind

    const pointerAt = (e) => {
      const rect = container.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    const boxStyle = (start, current) => ({
      left: `${Math.min(start.x, current.x)}px`,
      top: `${Math.min(start.y, current.y)}px`,
      width: `${Math.abs(current.x - start.x)}px`,
      height: `${Math.abs(current.y - start.y)}px`,
    });

    const endDrag = () => {
      drag = null;
      setDragBox(null);
      map.dragPan.enable();
    };

    // Capture phase: must win the mousedown race against MapLibre's own
    // handler (bound to the canvas, deeper in the tree) so dragPan can be
    // disabled before it starts tracking a pan.
    const onMouseDown = (e) => {
      if (!e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      drag = { start: pointerAt(e) };
      map.dragPan.disable();
      setDragBox(boxStyle(drag.start, drag.start));
    };

    const onMouseMove = (e) => {
      if (!drag) return;
      setDragBox(boxStyle(drag.start, pointerAt(e)));
    };

    const onMouseUp = (e) => {
      if (!drag) return;
      const start = drag.start;
      const end = pointerAt(e);
      const a = map.unproject([start.x, start.y]);
      const b = map.unproject([end.x, end.y]);
      endDrag();
      // Stopping propagation on `mousedown` above means MapLibre never saw a
      // drag start, so the browser's own post-mouseup "click" still reaches
      // the canvas. Left alone it would fire the grid-fill click handler and
      // open a single-cell detail panel on top of the area just selected.
      suppressClick = true;
      onAreaSelect(bboxFromCorners({ lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng }));
    };

    const onClickCapture = (e) => {
      if (!suppressClick) return;
      suppressClick = false;
      e.stopPropagation();
    };

    const onKeyDown = (e) => {
      if (e.key === "Escape" && drag) endDrag();
    };

    container.addEventListener("mousedown", onMouseDown, true);
    container.addEventListener("click", onClickCapture, true);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      container.removeEventListener("mousedown", onMouseDown, true);
      container.removeEventListener("click", onClickCapture, true);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onAreaSelect]);

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map" />
      {dragBox && <div className="select-box" style={dragBox} />}
    </div>
  );
}
