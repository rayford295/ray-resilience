import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { cellToBoundary } from "h3-js";
import "maplibre-gl/dist/maplibre-gl.css";
import { EVENTS, RAMP } from "../lib/views.js";
import { rampMax } from "../lib/legend.js";
import { priorityScores } from "../lib/data.js";
import { bboxFromCorners } from "../lib/area.js";
import { isClickSuppressed } from "../lib/clickSuppression.js";

const BASEMAP = "https://tiles.openfreemap.org/styles/liberty";
const SRC = "grid";
const HIGHLIGHT_SRC = "answer-highlight";
const HIGHLIGHT_FILL = "answer-highlight-fill";
const HIGHLIGHT_LINE = "answer-highlight-line";
const FACILITY_SRC = "facilities";
const FACILITY_LAYER = "facility-points";
// Comfortably longer than the same-tick gap between mouseup and the
// resulting synthetic click, comfortably shorter than two deliberate clicks.
const CLICK_SUPPRESS_MS = 300;

/** The cells an answer drew on, as a GeoJSON polygon per cell — independent
 * of whichever layer is on screen, since an area answer can draw on tiles
 * from an event the map is not currently displaying. */
function highlightGeojson(cells) {
  return {
    type: "FeatureCollection",
    features: (cells ?? []).map((cell) => ({
      type: "Feature",
      properties: { h3_cell: cell },
      geometry: { type: "Polygon", coordinates: [cellToBoundary(cell, true)] },
    })),
  };
}

function rampExpr(input, max) {
  const stops = RAMP.flatMap((color, i) => [(max * i) / (RAMP.length - 1), color]);
  return ["interpolate", ["linear"], input, ...stops];
}

// The ramp's upper bound comes from lib/legend.js so the Legend component
// labels exactly the scale this paint uses — one code path, no drift.
function paintFor(view, geojson) {
  if (view.kind === "priority") {
    return rampExpr(["coalesce", ["feature-state", "score"], 0], 1);
  }
  if (view.kind === "rate") {
    return rampExpr(["coalesce", ["get", view.metric], 0], 1);
  }
  return rampExpr(["coalesce", ["get", view.metric], 0], rampMax(view, geojson));
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
  highlightCells,
  facilities,
  showFacilities,
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
    // Rebuilding grid-fill/grid-line re-adds them at the top of the paint
    // order, which would bury an already-added highlight layer beneath the
    // new grid. Re-assert the highlight's position rather than the grid's,
    // since the highlight is what a stale layer order would visually hide.
    if (map.getLayer(HIGHLIGHT_FILL)) map.moveLayer(HIGHLIGHT_FILL);
    if (map.getLayer(HIGHLIGHT_LINE)) map.moveLayer(HIGHLIGHT_LINE);
    return () => map.off("click", "grid-fill", click);
  }, [ready, geojson, view, onSelect]);

  // Highlight the tiles the last answer drew on, above the active view. A
  // refusal, a no_evidence, or an outage carries no cells (App.jsx clears
  // `highlightCells` on every reply that isn't a cited answer), so this
  // renders an empty layer rather than leaving a stale highlight beside a
  // refusal it would misleadingly seem to be about.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const data = highlightGeojson(highlightCells);
    const existing = map.getSource(HIGHLIGHT_SRC);
    if (existing) {
      existing.setData(data);
      return;
    }
    map.addSource(HIGHLIGHT_SRC, { type: "geojson", data });
    map.addLayer({
      id: HIGHLIGHT_FILL,
      type: "fill",
      source: HIGHLIGHT_SRC,
      paint: { "fill-color": "#e6c229", "fill-opacity": 0.22 },
    });
    map.addLayer({
      id: HIGHLIGHT_LINE,
      type: "line",
      source: HIGHLIGHT_SRC,
      paint: { "line-color": "#e6c229", "line-width": 2.5 },
    });
  }, [ready, highlightCells]);

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

  // Critical-facility context points (OSM presence, never operational
  // status) over the active event's AOI. The name in the popup is
  // contributor-written text from OSM, so the popup is built from DOM nodes
  // rather than an HTML string.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const data =
      facilities && !facilities.error
        ? facilities
        : { type: "FeatureCollection", features: [] };
    const src = map.getSource(FACILITY_SRC);
    if (src) {
      src.setData(data);
    } else {
      map.addSource(FACILITY_SRC, { type: "geojson", data });
      map.addLayer({
        id: FACILITY_LAYER,
        type: "circle",
        source: FACILITY_SRC,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 3, 13, 7],
          "circle-color": [
            "match", ["get", "category"],
            "hospital", "#dc2626",
            "clinic", "#7c3aed",
            "fire_station", "#ea580c",
            "police", "#1d4ed8",
            "#64748b",
          ],
          "circle-opacity": 0.9,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.2,
        },
      });
      map.on("click", FACILITY_LAYER, (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const el = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = f.properties.name;
        const cat = document.createElement("div");
        cat.textContent = `${f.properties.category} — OSM presence, not operational status`;
        cat.style.fontSize = "0.75rem";
        const attribution = document.createElement("div");
        attribution.textContent = "© OpenStreetMap contributors (ODbL)";
        attribution.style.cssText = "font-size:0.7rem;color:#64748b;margin-top:2px";
        el.append(name, cat, attribution);
        new maplibregl.Popup({ closeButton: true, maxWidth: "260px" })
          .setLngLat(f.geometry.coordinates)
          .setDOMContent(el)
          .addTo(map);
      });
      map.on("mouseenter", FACILITY_LAYER, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", FACILITY_LAYER, () => (map.getCanvas().style.cursor = ""));
    }
    if (map.getLayer(FACILITY_LAYER)) {
      map.setLayoutProperty(
        FACILITY_LAYER, "visibility", showFacilities ? "visible" : "none"
      );
    }
  }, [ready, facilities, showFacilities]);

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
    // A deadline, not a boolean: the synthetic click after a drag fires at the
    // nearest common ancestor of the mousedown/mouseup targets, which can sit
    // above `container` (e.g. the drag ends over the sidebar) and never reach
    // this capturing listener at all. A boolean armed there and only disarmed
    // by that same listener would stay armed forever, silently swallowing the
    // next unrelated click. A deadline needs no disarm step on any path — it
    // is simply false again once time passes it, whether or not the click
    // handler below ever ran.
    let suppressClickUntil = 0;

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
      // open a single-cell detail panel on top of the area just selected. The
      // synthetic click dispatches synchronously right after this handler
      // returns, so a short window is all the deadline needs.
      suppressClickUntil = performance.now() + CLICK_SUPPRESS_MS;
      onAreaSelect(bboxFromCorners({ lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng }));
    };

    const onClickCapture = (e) => {
      if (!isClickSuppressed(performance.now(), suppressClickUntil)) return;
      e.stopPropagation();
    };

    const onKeyDown = (e) => {
      if (e.key === "Escape" && drag) endDrag();
    };

    // The pointer can be released outside the window entirely (dragged past
    // the browser's edge onto the desktop), where no mouseup ever fires. Left
    // alone that stranded `drag` keeps dragPan disabled and the overlay drawn
    // with no recovery but Escape. A lost window blur is the general signal
    // that the gesture is no longer ours to track.
    const onBlur = () => {
      if (drag) endDrag();
    };

    container.addEventListener("mousedown", onMouseDown, true);
    container.addEventListener("click", onClickCapture, true);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("blur", onBlur);
    return () => {
      container.removeEventListener("mousedown", onMouseDown, true);
      container.removeEventListener("click", onClickCapture, true);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("blur", onBlur);
    };
  }, [onAreaSelect]);

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map" />
      {dragBox && <div className="select-box" style={dragBox} />}
      {highlightCells?.length > 0 && (
        <div className="highlight-note">
          {highlightCells.length} tile{highlightCells.length > 1 ? "s" : ""} highlighted —
          last answer
        </div>
      )}
    </div>
  );
}
