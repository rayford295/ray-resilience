import { useMemo, useRef, useState } from "react";
import { cellToLatLng } from "h3-js";

import { parseCitations, verifiabilityLabel } from "../lib/citations.js";
import { cellsInBox } from "../lib/area.js";

const DEFAULT_ENDPOINT =
  localStorage.getItem("steward-endpoint") || "http://localhost:8080";

/**
 * Ask the Steward: the PWA face of the agent gateway. Every response type
 * the gateway can emit — cited answer, rule-ID refusal, declared
 * no-evidence, declared outage — renders as itself; nothing is papered over.
 */
export default function ChatPanel({
  role,
  location,
  selection,
  onClearSelection,
  cells,
  onAnswerCells,
}) {
  const [endpoint, setEndpoint] = useState(DEFAULT_ENDPOINT);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  // Same edge-inclusive, centre-in-box rule the gateway applies to `area` --
  // but a matching predicate is necessary, not sufficient. What makes this
  // count agree with the answer's own `cells` is that both sides now walk the
  // same input set too: the gateway's `evidence_for_area` tests every grid of
  // every intersecting event, and `cells` here is the union of every view's
  // layer, fetched as soon as planner mode is entered (App.jsx), not just
  // whichever one is on screen.
  const selectedCount = useMemo(
    () => (selection ? cellsInBox(cells ?? [], selection, cellToLatLng).length : 0),
    [selection, cells]
  );

  async function send(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy || (!location && !selection)) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { from: "user", question, role }]);
    let reply;
    try {
      const r = await fetch(`${endpoint.replace(/\/$/, "")}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          selection
            ? { role, question, area: selection }
            : { role, lat: location.lat, lon: location.lng, question }
        ),
      });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      reply = await r.json();
    } catch (err) {
      reply = {
        type: "agent_unavailable",
        reason:
          `Gateway unreachable at ${endpoint} (${err.message}). ` +
          "Run it locally: pip install -e .[deepcase,gateway] && uvicorn gateway.main:app --port 8080",
      };
    }
    setMessages((m) => [...m, { from: "steward", ...reply }]);
    // A refusal, a no_evidence, or an outage carries no cells — clearing the
    // highlight here, not just skipping the update, keeps a stale highlight
    // from sitting on the map beside a refusal it would misleadingly seem to
    // be about.
    onAnswerCells?.(reply.type === "answer" ? reply.cells ?? [] : null);
    setBusy(false);
    queueMicrotask(() =>
      logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" })
    );
  }

  return (
    <div className="chat">
      <p className="hint">
        Asking as <strong>{role}</strong>{" "}
        {selection ? (
          <>
            about the selected area
            <span className="dim">
              {" "}
              ({selection.min_lat.toFixed(4)}, {selection.min_lon.toFixed(4)} to{" "}
              {selection.max_lat.toFixed(4)}, {selection.max_lon.toFixed(4)}) —{" "}
              {selectedCount} evaluated cell{selectedCount === 1 ? "" : "s"}
            </span>
            {" "}
            <button type="button" className="linkish" onClick={onClearSelection}>
              clear
            </button>
          </>
        ) : (
          <>
            about the map center
            {location && (
              <span className="dim">
                {" "}({location.lat.toFixed(4)}, {location.lng.toFixed(4)})
              </span>
            )}
          </>
        )}
        . The steward answers only from committed artifacts — refusals cite the
        rule that triggered them.
      </p>
      <div className="chat-log" ref={logRef}>
        {messages.map((m, i) =>
          m.from === "user" ? (
            <div key={i} className="msg user">{m.question}</div>
          ) : (
            <StewardMessage key={i} reply={m} />
          )
        )}
        {busy && (
          <div className="msg steward dim">
            policy pre-check → evidence → model → claim post-check…
          </div>
        )}
      </div>
      <form onSubmit={send} className="search">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            role === "resident" ? "How safe is this area?" : "How severe is the damage here?"
          }
          aria-label="question for the steward"
        />
        <button type="submit" disabled={busy}>Ask</button>
      </form>
      <details className="endpoint">
        <summary className="dim">gateway endpoint</summary>
        <input
          value={endpoint}
          onChange={(e) => {
            setEndpoint(e.target.value);
            localStorage.setItem("steward-endpoint", e.target.value);
          }}
        />
      </details>
    </div>
  );
}

function renderCitations(text) {
  return parseCitations(text).map((token, i) => {
    if (token.kind === "artifact") {
      return (
        <span key={i} className="cite" title="cites a committed, hashed artifact">
          {token.id.slice(0, 6)}
        </span>
      );
    }
    if (token.kind === "live") {
      return (
        <span
          key={i}
          className="cite live"
          title={
            "cites a live third-party lookup — re-derivable, not retained. " +
            "No copy of the response is kept; the recorded request and its " +
            "response hash are in events/live_evidence.jsonl."
          }
        >
          ↻ {token.id.slice(0, 6)}
        </span>
      );
    }
    return <span key={i}>{token.value}</span>;
  });
}

function StewardMessage({ reply }) {
  if (reply.type === "answer") {
    const live = reply.live_citations ?? [];
    const verifiability = verifiabilityLabel(reply.verifiability);
    return (
      <div className="msg steward">
        <div>{renderCitations(reply.text)}</div>
        <div className="msg-meta">
          rule {reply.rule_id} · {reply.event} · {reply.citations.length} artifact
          {reply.citations.length > 1 ? "s" : ""} cited
          {live.length > 0 && (
            <> · {live.length} live lookup{live.length > 1 ? "s" : ""}</>
          )}
          {reply.cells?.length > 0 && (
            <> · {reply.cells.length} tile{reply.cells.length > 1 ? "s" : ""} highlighted on the map</>
          )}
          {verifiability && (
            <>
              {" · "}
              <span className={`verif ${reply.verifiability}`} title={verifiability.detail}>
                {verifiability.label}
              </span>
            </>
          )}
        </div>
        {/* Required wherever third-party content is surfaced, and rendered from
            the gateway's own field so the app cannot show the content while
            forgetting the credit. */}
        {reply.attribution && live.length > 0 && (
          <div className="msg-meta attribution">
            Live facility context: {reply.attribution}. Not retained — re-derivable from
            the recorded request.
          </div>
        )}
      </div>
    );
  }
  if (reply.type === "live_source_unavailable") {
    // Distinct from an agent outage: the model is fine, the third-party
    // capability is absent. Saying "agent unavailable" here would misdescribe
    // which part of the system failed.
    return (
      <div className="msg steward outage">
        <strong>Live source unavailable</strong>
        <div>{reply.reason}</div>
      </div>
    );
  }
  if (reply.type === "refusal") {
    return (
      <div className="msg steward refusal">
        <strong>Refused — rule {reply.rule_id}</strong>
        <div>{reply.reason}</div>
      </div>
    );
  }
  if (reply.type === "no_evidence") {
    return (
      <div className="msg steward noev">
        <strong>No evidence here</strong>
        <div>{reply.reason}</div>
      </div>
    );
  }
  return (
    <div className="msg steward outage">
      <strong>Agent unavailable</strong>
      <div>{reply.reason}</div>
    </div>
  );
}
