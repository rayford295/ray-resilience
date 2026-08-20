import { useState } from "react";
import { latLngToCell } from "h3-js";
import { geocodeAddress } from "../lib/data.js";

/**
 * Resident mode: address -> plain-language resilience dossier. Inside a
 * deep-case AOI the card cites tile-level facts; outside it says, honestly,
 * that the location is outside the evaluated competence.
 */
export default function ResidentPanel({ grids, records, onFly }) {
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
      const cell = latLngToCell(hit.lat, hit.lon, 9);
      let found = null;
      for (const [eventId, grid] of Object.entries(grids)) {
        const feature = grid?.features?.find((f) => f.properties.h3_cell === cell);
        if (feature) found = { eventId, props: feature.properties };
      }
      setState({ status: "done", hit, cell, found });
    } catch (err) {
      setState({ status: "error", error: String(err) });
    }
  }

  const record = state.found ? records[state.found.eventId] : null;

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
          {state.found ? (
            <>
              <p>
                This address falls in an evaluated tile of{" "}
                <strong>{state.found.eventId}</strong>.
              </p>
              <DossierFacts props={state.found.props} />
            </>
          ) : (
            <p className="outside">
              This location is <strong>outside the evaluated deep-case areas</strong>.
              GeoSteward makes no damage or vulnerability claims here — competence is
              conditional on place.
            </p>
          )}
          {record && (
            <>
              <h4>Declared unknowns for this event</h4>
              <ul className="unknowns">
                {record.declared_unknowns.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DossierFacts({ props }) {
  const facts = [];
  if (typeof props.n_structures === "number") {
    facts.push(`${props.n_structures} structures were assessed in this tile`);
  }
  if (typeof props.destroyed_rate === "number") {
    facts.push(`${Math.round(props.destroyed_rate * 100)}% of assessed structures destroyed`);
  }
  if (typeof props.RPL_THEMES === "number") {
    facts.push(
      `social vulnerability rank ${props.RPL_THEMES.toFixed(2)} (0 = lowest, 1 = highest, CDC SVI 2022)`
    );
  }
  if (typeof props.n_matched_samples === "number") {
    facts.push(`${props.n_matched_samples} cross-view evidence samples cover this tile`);
  }
  return (
    <ul>
      {facts.map((f) => (
        <li key={f}>{f}</li>
      ))}
      <li className="dim">
        tile resolution: H3 r9 (~0.1 km²) — statements never narrow to a single parcel
      </li>
    </ul>
  );
}
