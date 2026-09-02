import { useState } from "react";
import { latLngToCell } from "h3-js";
import { geocodeAddress } from "../lib/data.js";
import { eventsOf, lookupCoverage, mergedProps } from "../lib/coverage.js";

/**
 * Resident mode: address -> plain-language resilience dossier.
 *
 * The lookup resolves against the coverage index over every layer, so an
 * address is judged by what GeoSteward has evaluated rather than by which
 * layer the map is currently drawing. And it has three answers, not two:
 * "no evidence covers you" is a claim, while "some evidence is unreadable"
 * is an admission, and collapsing the second into the first is how a resident
 * gets told their covered address was never evaluated.
 */
export default function ResidentPanel({ coverage, records, onFly }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ status: "idle" });

  async function search(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setState({ status: "loading" });
    try {
      const hit = await geocodeAddress(query.trim());
      if (!hit) {
        setState({ status: "nomatch" });
        return;
      }
      onFly({ center: [hit.lon, hit.lat], zoom: 13.5 });
      setState({ status: "done", hit, cell: latLngToCell(hit.lat, hit.lon, 9) });
    } catch (err) {
      setState({ status: "error", error: String(err) });
    }
  }

  // Resolved at render, not at submit: layers still arriving upgrade an
  // "unknown" answer to a real one without the resident searching again.
  const result = state.status === "done" ? lookupCoverage(coverage, state.cell) : null;
  const events = result?.hits.length ? eventsOf(result.hits) : [];

  return (
    <div>
      <form onSubmit={search} className="search">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="US address, e.g. 2200 Lake Ave, Altadena, CA"
          aria-label="address"
        />
        <button type="submit">Look up</button>
      </form>

      {state.status === "loading" && <p className="hint">geocoding…</p>}
      {state.status === "nomatch" && (
        <p className="hint">No match from the Census geocoder — try adding city and state.</p>
      )}
      {state.status === "error" && (
        <p className="hint">Geocoder unreachable ({state.error}). Nothing was guessed.</p>
      )}

      {state.status === "done" && (
        <div className="dossier">
          <h3>{state.hit.matched}</h3>

          {result.status === "covered" && (
            <>
              <p>
                This address falls in an evaluated tile of{" "}
                <strong>{events.join(", ")}</strong>.
              </p>
              <DossierFacts props={mergedProps(result.hits)} />
              {result.incomplete && (
                <p className="hint">
                  Some other layers are still unread, so more may apply here than is
                  shown.
                </p>
              )}
            </>
          )}

          {result.status === "not_covered" && (
            <p className="outside">
              This location is <strong>outside the evaluated deep-case areas</strong>.
              GeoSteward makes no damage or vulnerability claims here — competence is
              conditional on place. Every evaluated layer was read to establish this.
            </p>
          )}

          {result.status === "unknown" && (
            <p className="outside">
              <strong>Not determined.</strong>{" "}
              {result.unreadable.length > 0
                ? `${result.unreadable.length} evaluated layer(s) could not be read, so`
                : "The evaluated layers are still loading, so"}{" "}
              GeoSteward cannot yet tell whether this address is covered. It will not
              guess that it is outside the evaluated areas — that would be a claim
              about a place it has not managed to look at.
            </p>
          )}

          {events.map((eventId) =>
            records[eventId] ? (
              <div key={eventId}>
                <h4>Declared unknowns — {eventId}</h4>
                <ul className="unknowns">
                  {records[eventId].declared_unknowns.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              </div>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}

function DossierFacts({ props }) {
  // Same facts as before, presented as glanceable stat callouts. Each number
  // keeps its qualifier in the same card, so a value never reads without the
  // scope that authorizes it.
  const stats = [];
  if (typeof props.n_structures === "number") {
    stats.push({ k: "Structures assessed", v: props.n_structures, u: "in this tile" });
  }
  if (typeof props.destroyed_rate === "number") {
    stats.push({
      k: "Destroyed",
      v: `${Math.round(props.destroyed_rate * 100)}%`,
      u: "of assessed structures",
    });
  }
  if (typeof props.RPL_THEMES === "number") {
    stats.push({
      k: "Social vulnerability",
      v: props.RPL_THEMES.toFixed(2),
      u: "0 low – 1 high · CDC SVI 2022",
    });
  }
  if (typeof props.n_matched_samples === "number") {
    stats.push({ k: "Evidence samples", v: props.n_matched_samples, u: "cross-view, this tile" });
  }
  return (
    <>
      <div className="stats">
        {stats.map((s) => (
          <div className="stat" key={s.k}>
            <div className="k">{s.k}</div>
            <div className="v">{s.v}</div>
            <div className="u">{s.u}</div>
          </div>
        ))}
      </div>
      <p className="hint">
        tile resolution: H3 r9 (~0.1 km²) — statements never narrow to a single parcel
      </p>
    </>
  );
}
