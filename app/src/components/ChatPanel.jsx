import { useRef, useState } from "react";

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
  const parts = text.split(/(\[artifact:[0-9a-f]{12}\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[artifact:([0-9a-f]{12})\]$/);
    if (match) {
      return (
        <span key={i} className="cite" title="cites a committed, hashed artifact">
          {match[1].slice(0, 6)}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function StewardMessage({ reply }) {
  if (reply.type === "answer") {
    return (
      <div className="msg steward">
        <div>{renderCitations(reply.text)}</div>
        <div className="msg-meta">
          rule {reply.rule_id} · {reply.event} · {reply.citations.length} artifact
          {reply.citations.length > 1 ? "s" : ""} cited
        </div>
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
