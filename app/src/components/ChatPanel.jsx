import { useRef, useState } from "react";

import { parseCitations, verifiabilityLabel } from "../lib/citations.js";

const DEFAULT_ENDPOINT =
  localStorage.getItem("steward-endpoint") || "http://localhost:8080";

/**
 * Ask the Steward: the PWA face of the agent gateway. Every response type
 * the gateway can emit — cited answer, rule-ID refusal, declared
 * no-evidence, declared outage — renders as itself; nothing is papered over.
 */
export default function ChatPanel({ role, location }) {
  const [endpoint, setEndpoint] = useState(DEFAULT_ENDPOINT);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  async function send(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy || !location) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { from: "user", question, role }]);
    let reply;
    try {
      const r = await fetch(`${endpoint.replace(/\/$/, "")}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          lat: location.lat,
          lon: location.lng,
          question,
        }),
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
    setBusy(false);
    queueMicrotask(() =>
      logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" })
    );
  }

  return (
    <div className="chat">
      <p className="hint">
        Asking as <strong>{role}</strong> about the map center
        {location && (
          <span className="dim">
            {" "}({location.lat.toFixed(4)}, {location.lng.toFixed(4)})
          </span>
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
