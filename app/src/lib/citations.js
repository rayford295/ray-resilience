// Two citation forms, and the difference between them is the point.
//
// [artifact:HASH12] points at a file committed to this repository. A reader
// opens it and checks the number.
//
// [live:HASH12] points at a row in events/live_evidence.jsonl: a request this
// project issued to a third party, and the sha256 of the response it got back.
// No copy of that response exists anywhere, because the licence forbids keeping
// one. A reader re-issues the recorded request with their own key and compares
// digests.
//
// Both are checkable. They are not checkable in the same way, and rendering
// them identically would tell the reader they were — which is the kind of quiet
// overstatement this app exists not to make. So a live chip says what it is,
// and carries the attribution the terms require wherever the content appears.

const CITATION = /(\[(?:artifact|live):[0-9a-f]{12}\])/g;
const PARSE = /^\[(artifact|live):([0-9a-f]{12})\]$/;

/**
 * Split answer prose into text runs and citation tokens, in order.
 *
 * Returns `{kind: "text", value}` and `{kind: "artifact"|"live", id}` tokens.
 * Unrecognised bracket text stays text: a malformed citation should render as
 * the literal characters the model produced, not silently vanish into a chip
 * that implies evidence nobody checked.
 */
export function parseCitations(text) {
  if (!text) return [];
  return text
    .split(CITATION)
    .filter((part) => part !== "")
    .map((part) => {
      const match = PARSE.exec(part);
      if (!match) return { kind: "text", value: part };
      return { kind: match[1], id: match[2] };
    });
}

/**
 * How an answer describes its own checkability, for display.
 *
 * Weakest-link, matching the harness: an answer resting on both hashed grids
 * and a live lookup is `re-derivable`, not `retained`, because one part of it
 * is. `null` verifiability means the gateway did not say — older gateway, or a
 * response type that carries no claim — and is rendered as unstated rather than
 * assumed to be the strongest value.
 */
export function verifiabilityLabel(verifiability) {
  switch (verifiability) {
    case "retained":
      return {
        label: "retained",
        detail: "Every source is a hashed file committed to this repository.",
      };
    case "re-derivable":
      return {
        label: "re-derivable",
        detail:
          "Part of this answer came from a live third-party lookup that was not " +
          "retained. Re-issue the recorded request with your own key to check it.",
      };
    case "cited-only":
      return {
        label: "cited-only",
        detail:
          "Part of this answer can be neither retained nor reproduced; only its " +
          "citations are checkable.",
      };
    default:
      return null;
  }
}
