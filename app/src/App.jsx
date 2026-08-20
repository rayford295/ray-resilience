import { useCallback, useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView.jsx";
import PlannerPanel from "./components/PlannerPanel.jsx";
import ResidentPanel from "./components/ResidentPanel.jsx";
import LineagePanel from "./components/LineagePanel.jsx";
import { LiveWatchBadge, TierBadge, ValidityBadge } from "./components/Badges.jsx";
import { EVENTS, VIEWS } from "./lib/views.js";
import {
  artifactLineage,
  fetchJson,
  fetchJsonl,
  fetchLiveWatch,
  stageValidity,
} from "./lib/data.js";

export default function App() {
  const [mode, setMode] = useState("planner");
  const [viewId, setViewId] = useState("eaton-priority");
  const [layers, setLayers] = useState({}); // viewId -> geojson | {error}
  const [meta, setMeta] = useState({}); // eventId -> {manifest, audit, record}
  const [t, setT] = useState(0.5);
  const [selected, setSelected] = useState(null);
  const [flyTarget, setFlyTarget] = useState(null);
  const [live, setLive] = useState(null);
  const [showLineage, setShowLineage] = useState(false);

  const view = VIEWS.find((v) => v.id === viewId);
  const event = EVENTS[view.event];

  useEffect(() => {
    fetchLiveWatch().then(setLive);
  }, []);

  // Lazy-load the active view's artifact; failures render as failures.
  useEffect(() => {
    if (layers[viewId]) return;
    fetchJson(view.url)
      .then((data) => setLayers((s) => ({ ...s, [viewId]: data })))
      .catch((err) => setLayers((s) => ({ ...s, [viewId]: { error: String(err) } })));
  }, [viewId, view.url, layers]);

  // Event-level provenance: manifest + audit + dossier record.
  useEffect(() => {
    const eventId = view.event;
    if (meta[eventId]) return;
    Promise.all([
      fetchJsonl(event.manifest),
      fetchJsonl(event.audit),
      fetchJson(event.record),
    ])
      .then(([manifest, audit, record]) =>
        setMeta((s) => ({ ...s, [eventId]: { manifest, audit, record } }))
      )
      .catch((err) => setMeta((s) => ({ ...s, [eventId]: { error: String(err) } })));
  }, [view.event, event, meta]);

  useEffect(() => {
    setFlyTarget(view.focus ?? { center: event.center, zoom: event.zoom });
    setSelected(null);
  }, [viewId]); // eslint-disable-line react-hooks/exhaustive-deps

  const geojson = layers[viewId]?.error ? null : layers[viewId];
  const eventMeta = meta[view.event];
  const validity = useMemo(
    () => (eventMeta?.audit ? stageValidity(eventMeta.audit, view.stage) : null),
    [eventMeta, view.stage]
  );
  const lineage = useMemo(
    () => (eventMeta?.manifest ? artifactLineage(eventMeta.manifest, view.url) : null),
    [eventMeta, view.url]
  );

  const grids = useMemo(() => {
    const out = {};
    for (const v of VIEWS) {
      if (layers[v.id] && !layers[v.id].error) out[v.event] = layers[v.id];
    }
    return out;
  }, [layers]);
  const records = useMemo(() => {
    const out = {};
    for (const [eventId, m] of Object.entries(meta)) {
      if (m?.record) out[eventId] = m.record;
    }
    return out;
  }, [meta]);

  const onSelect = useCallback((props) => setSelected(props), []);

  return (
    <div className="shell">
      <header>
        <div className="brand">
          <strong>GeoSteward</strong>
          <span className="dim"> · accountable GeoAI risk analyst</span>
        </div>
        <div className="header-right">
          <LiveWatchBadge live={live} />
          <nav className="mode-switch" role="tablist">
            {["resident", "planner"].map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                className={mode === m ? "active" : ""}
                onClick={() => setMode(m)}
              >
                {m}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <div className="body">
        <aside>
          <section>
            <h2>Layer</h2>
            <select value={viewId} onChange={(e) => setViewId(e.target.value)}>
              {Object.entries(EVENTS).map(([eventId, ev]) => (
                <optgroup key={eventId} label={ev.title}>
                  {VIEWS.filter((v) => v.event === eventId).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <div className="badges">
              <TierBadge tier={view.tier} />
              <ValidityBadge validity={validity} />
            </div>
            {view.legend && <p className="hint">{view.legend}</p>}
            {layers[viewId]?.error && (
              <p className="fail-text">layer failed to load: {layers[viewId].error}</p>
            )}
          </section>

          <section>
            {mode === "planner" ? (
              <PlannerPanel
                view={view}
                geojson={geojson}
                t={t}
                onT={setT}
                onFlyToCell={setFlyTarget}
              />
            ) : (
              <ResidentPanel grids={grids} records={records} onFly={setFlyTarget} />
            )}
          </section>

          {selected && (
            <section className="details">
              <h2>Tile {String(selected.h3_cell).slice(0, 10)}…</h2>
              <dl>
                {Object.entries(selected)
                  .filter(([k]) => k !== "h3_cell" && k !== "uncertainty" && k !== "labels")
                  .map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{typeof v === "number" ? +v.toFixed(4) : String(v)}</dd>
                    </div>
                  ))}
              </dl>
              {selected.uncertainty && (
                <>
                  <h4>Uncertainty (mandatory field)</h4>
                  <pre className="uncertainty">
                    {JSON.stringify(
                      typeof selected.uncertainty === "string"
                        ? JSON.parse(selected.uncertainty)
                        : selected.uncertainty,
                      null,
                      1
                    )}
                  </pre>
                </>
              )}
            </section>
          )}

          <section>
            <button className="linkish" onClick={() => setShowLineage((s) => !s)}>
              {showLineage ? "hide" : "show"} lineage & provenance
            </button>
            {showLineage && (
              <LineagePanel view={view} lineage={lineage} validity={validity} />
            )}
          </section>

          <footer className="dim">
            Research prototype — not an official forecasting or warning service.
          </footer>
        </aside>

        <main>
          <MapView
            view={view}
            geojson={geojson}
            priorityT={t}
            flyTarget={flyTarget}
            onSelect={onSelect}
            live={live}
          />
        </main>
      </div>
    </div>
  );
}
