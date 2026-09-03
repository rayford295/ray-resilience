export const EXAMPLE_ADDRESS = "2200 Lake Ave, Altadena, CA";

/**
 * First-visit orientation: three things a new visitor can do, each one
 * click away. Dismissal is remembered per browser (best-effort — private
 * windows without storage simply see the card again), and the header's
 * "?" reopens it, so choosing to hide it is never one-way.
 */
export default function WelcomeCard({ onTryAddress, onDismiss }) {
  return (
    <section className="welcome">
      <h2>Start here</h2>
      <ol className="welcome-steps">
        <li>
          <strong>Look up an address.</strong> Resident mode answers with what
          the evidence supports there — and says when a place is outside the
          evaluated areas.{" "}
          <button type="button" className="linkish" onClick={onTryAddress}>
            Try {EXAMPLE_ADDRESS} →
          </button>
        </li>
        <li>
          <strong>Switch layers.</strong> The selector above holds three deep
          cases — wildfire damage, debris volumes, street-view evidence — each
          with its validity badge and lineage.
        </li>
        <li>
          <strong>Ask Ray.</strong> Planner mode adds a
          damage-vs-vulnerability slider, and shift-drag draws an area to ask
          about. Every answer cites the artifacts it rests on.
        </li>
      </ol>
      <button type="button" className="linkish dim" onClick={onDismiss}>
        got it — don't show this again
      </button>
    </section>
  );
}
