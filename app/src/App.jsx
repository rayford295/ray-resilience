import { useCallback, useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView.jsx";
import PlannerPanel from "./components/PlannerPanel.jsx";
import ResidentPanel from "./components/ResidentPanel.jsx";
import LineagePanel from "./components/LineagePanel.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import CitationCard from "./components/CitationCard.jsx";
import Legend from "./components/Legend.jsx";
import WelcomeCard, { EXAMPLE_ADDRESS } from "./components/WelcomeCard.jsx";
import { LiveWatchBadge, TierBadge, ValidityBadge } from "./components/Badges.jsx";
import { EVENTS, VIEWS } from "./lib/views.js";
import { buildCoverageIndex } from "./lib/coverage.js";
import { resolveCitation } from "./lib/citations.js";
import { watchSummary } from "./lib/watch.js";
import {
  artifactLineage,
  fetchJson,
  fetchJsonl,
  fetchLiveWatch,
  fetchWatchStatus,
  stageValidity,
} from "./lib/data.js";

const WELCOME_KEY = "gs-welcome-dismissed";

function welcomeDismissed() {
  try {
    return localStorage.getItem(WELCOME_KEY) === "1";
  } catch {
    return false;
  }
}

export default function App() {
  const [mode, setMode] = useState("planner");
  const [viewId, setViewId] = useState("eaton-priority");
  const [layers, setLayers] = useState({}); // viewId -> geojson | {error}
  const [meta, setMeta] = useState({}); // eventId -> {manifest, audit, record}
  const [dossiers, setDossiers] = useState({}); // eventId -> event_record (resident lookup)
  const [t, setT] = useState(0.5);
  const [selected, setSelected] = useState(null);
  const [flyTarget, setFlyTarget] = useState(null);
  const [live, setLive] = useState(null);
  const [watchStatus, setWatchStatus] = useState(null);
  const [showLineage, setShowLineage] = useState(false);
  const [mapCenter, setMapCenter] = useState(null);
  const [selection, setSelection] = useState(null); // shift-drag area bbox, or null for point mode
  const [highlightCells, setHighlightCells] = useState(null); // last answer's cells, or null
  const [showWelcome, setShowWelcome] = useState(() => !welcomeDismissed());
  const [exampleAddress, setExampleAddress] = useState(null);
  const [citation, setCitation] = useState(null); // clicked citation token, or null
  // Manifests fetched only to resolve citations — kept OUT of `meta`, whose
  // entries must stay the full manifest+audit+record triple (a partial entry
  // there would short-circuit the lineage/validity fetch and empty both panels).
  const [citeManifests, setCiteManifests] = useState({});
  const [facilityLayers, setFacilityLayers] = useState({}); // eventId -> geojson | {error}
  const [showFacilities, setShowFacilities] = useState(true);

  const view = VIEWS.find((v) => v.id === viewId);
  const event = EVENTS[view.event];

  // The layer and its own account of what it is missing, fetched together —
  // the hazard count is only presentable alongside the count it excludes.
  useEffect(() => {
    fetchLiveWatch().then(setLive);
    fetchWatchStatus().then(setWatchStatus);
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

  // The box-select affordance is planner-only (residents' damage questions are
  // refused whether point or area, so offering it would just invite a refusal
  // they can't use) — drop any active selection when leaving planner mode.
  // The highlight is downstream of an area answer, so it goes stale the same
  // way the selection that produced it does.
  useEffect(() => {
    if (mode !== "planner") {
      setSelection(null);
      setHighlightCells(null);
    }
  }, [mode]);

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

  // Resident lookup asks about coverage across every layer, so it cannot ride
  // on whichever layer the map happens to be showing. Entering resident mode
  // requests all of them; until they answer, a miss is "unknown", never
  // "outside the evaluated areas".
  useEffect(() => {
    if (mode !== "resident") return;
    for (const v of VIEWS) {
      if (layers[v.id]) continue;
      fetchJson(v.url)
        .then((data) => setLayers((s) => (s[v.id] ? s : { ...s, [v.id]: data })))
        .catch((err) =>
          setLayers((s) => (s[v.id] ? s : { ...s, [v.id]: { error: String(err) } }))
        );
    }
    // Dossiers too: an address can match any event, and its declared unknowns
    // belong with the answer rather than behind a layer switch. Kept separate
    // from `meta`, which is the full manifest+audit+record triple the lineage
    // and validity panels need — a partial entry there would short-circuit
    // their fetch and silently empty both panels.
    for (const [eventId, ev] of Object.entries(EVENTS)) {
      if (dossiers[eventId]) continue;
      fetchJson(ev.record)
        .then((record) => setDossiers((s) => (s[eventId] ? s : { ...s, [eventId]: record })))
        .catch(() => {});
    }
  }, [mode, layers, dossiers]);

  // The same instinct, for the same reason, on the planner side: `areaCells`
  // below is what the header count and the post-answer highlight both read,
  // and the gateway's own `evidence_for_area` walks every grid of every
  // intersecting event, not just the one the map happens to be showing. If
  // `areaCells` only ever saw the active view, a selection over an event
  // that isn't on screen would show a header count the answer then
  // contradicts — not because the two sides compute coverage differently
  // (`cellsInBox` and `evidence_for_area` apply the identical edge-inclusive
  // rule), but because they'd be counting over different input sets. Loading
  // every view as soon as planner mode is entered gives both sides the same
  // universe; until they all arrive, the count is a floor that only grows,
  // never one that overstates what a selection covers.
  useEffect(() => {
    if (mode !== "planner") return;
    for (const v of VIEWS) {
      if (layers[v.id]) continue;
      fetchJson(v.url)
        .then((data) => setLayers((s) => (s[v.id] ? s : { ...s, [v.id]: data })))
        .catch((err) =>
          setLayers((s) => (s[v.id] ? s : { ...s, [v.id]: { error: String(err) } }))
        );
    }
  }, [mode, layers]);

  const coverage = useMemo(
    () =>
      buildCoverageIndex(
        VIEWS.map((v) => ({
          viewId: v.id,
          event: v.event,
          geojson: layers[v.id]?.error ? undefined : layers[v.id],
          error: layers[v.id]?.error,
        }))
      ),
    [layers]
  );
  // Best local knowledge of what the answer could speak for: the union of
  // cells across every layer already fetched, not just the one on screen —
  // the gateway resolves `area` against whichever artifact covers it, not
  // whichever layer the map happens to be showing.
  const areaCells = useMemo(() => {
    const ids = new Set();
    for (const layer of Object.values(layers)) {
      if (!layer || layer.error) continue;
      for (const f of layer.features ?? []) {
        if (f.properties?.h3_cell) ids.add(f.properties.h3_cell);
      }
    }
    return [...ids];
  }, [layers]);
  const records = useMemo(() => {
    const out = { ...dossiers };
    for (const [eventId, m] of Object.entries(meta)) {
      if (m?.record) out[eventId] = m.record;
    }
    return out;
  }, [meta, dossiers]);

  useEffect(() => {
    const wanted = mode === "resident" ? Object.keys(EVENTS) : [view.event];
    for (const eventId of wanted) {
      if (facilityLayers[eventId]) continue;
      fetchJson(EVENTS[eventId].facilities)
        .then((data) => setFacilityLayers((s) => (s[eventId] ? s : { ...s, [eventId]: data })))
        .catch((err) =>
          setFacilityLayers((s) => (s[eventId] ? s : { ...s, [eventId]: { error: String(err) } }))
        );
    }
  }, [mode, view.event, facilityLayers]);

  const onSelect = useCallback((props) => setSelected(props), []);

  const onCite = useCallback((token) => setCitation(token), []);

  // A citation can point into any event, not just the one on screen, so an
  // open citation backfills every event's manifest not already fetched.
  // `null` marks a fetch in flight; a failed fetch settles to [] so the card
  // reports "searched and absent" rather than spinning forever.
  useEffect(() => {
    if (!citation) return;
    for (const [eventId, ev] of Object.entries(EVENTS)) {
      if (citeManifests[eventId] !== undefined) continue;
      setCiteManifests((c) => ({ ...c, [eventId]: c[eventId] ?? null }));
      fetchJsonl(ev.manifest)
        .then((rows) => setCiteManifests((c) => ({ ...c, [eventId]: rows })))
        .catch(() => setCiteManifests((c) => ({ ...c, [eventId]: [] })));
    }
  }, [citation]); // eslint-disable-line react-hooks/exhaustive-deps

  const citationResolution = useMemo(() => {
    if (!citation) return null;
    const manifests = { ...citeManifests };
    for (const [eventId, m] of Object.entries(meta)) {
      if (m?.manifest) manifests[eventId] = m.manifest;
    }
    return resolveCitation(manifests, citation.id);
  }, [citation, citeManifests, meta]);
  const citationLoading =
    citation != null &&
    citationResolution?.status !== "found" &&
    Object.values(citeManifests).some((rows) => rows === null);

  const dismissWelcome = () => {
    setShowWelcome(false);
    try {
      localStorage.setItem(WELCOME_KEY, "1");
    } catch {
      // best-effort: a browser without storage just sees the card next visit
    }
  };

  return (
    <div className="shell">
      <header>
        <div className="brand">
          <strong>GeoSteward</strong>
          <span className="dim"> · accountable GeoAI risk analyst</span>
        </div>
        <div className="header-right">
          <LiveWatchBadge summary={live && watchStatus ? watchSummary(live, watchStatus) : null} />
          <button
            type="button"
            className="help-btn"
            title="show the getting-started card"
            aria-label="show the getting-started card"
            onClick={() => setShowWelcome(true)}
          >
            ?
          </button>
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
          {showWelcome && (
            <WelcomeCard
              onTryAddress={() => {
                setMode("resident");
                setExampleAddress(EXAMPLE_ADDRESS);
              }}
              onDismiss={dismissWelcome}
            />
          )}
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
            <Legend view={view} geojson={geojson} />
            <label className="facility-toggle">
              <input
                type="checkbox"
                checked={showFacilities}
                onChange={(e) => setShowFacilities(e.target.checked)}
              />
              <span>
                critical facilities{" "}
                {facilityLayers[view.event]?.features
                  ? `(${facilityLayers[view.event].features.length})`
                  : facilityLayers[view.event]?.error
                    ? "(layer unreadable)"
                    : ""}
              </span>
            </label>
            {showFacilities && (
              <p className="hint attribution-line">
                OSM presence, not operational status · © OpenStreetMap contributors (ODbL)
              </p>
            )}
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
              <ResidentPanel
                coverage={coverage}
                records={records}
                onFly={setFlyTarget}
                exampleQuery={exampleAddress}
                onExampleConsumed={() => setExampleAddress(null)}
                facilityLayers={facilityLayers}
              />
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
            <h2>Ask the steward</h2>
            <ChatPanel
              role={mode}
              location={mapCenter}
              selection={selection}
              onClearSelection={() => setSelection(null)}
              cells={areaCells}
              onAnswerCells={setHighlightCells}
              onCite={onCite}
            />
          </section>

          {citation && (
            <section>
              <CitationCard
                citation={citation}
                resolution={citationResolution}
                loading={citationLoading}
                onClose={() => setCitation(null)}
              />
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
            onAreaSelect={mode === "planner" ? setSelection : undefined}
            live={live}
            onCenter={setMapCenter}
            highlightCells={highlightCells}
            facilities={facilityLayers[view.event]}
            showFacilities={showFacilities}
          />
        </main>
      </div>
    </div>
  );
}
