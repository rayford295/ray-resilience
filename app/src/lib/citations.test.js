import { describe, expect, it } from "vitest";

import { parseCitations, resolveCitation, verifiabilityLabel } from "./citations.js";

const ARTIFACT = "a1b2c3d4e5f6";
const LIVE = "0f1e2d3c4b5a";

describe("parseCitations", () => {
  it("keeps plain prose as one text run", () => {
    expect(parseCitations("Nothing to cite here.")).toEqual([
      { kind: "text", value: "Nothing to cite here." },
    ]);
  });

  it("distinguishes a retained citation from a live one", () => {
    const tokens = parseCitations(
      `Assessed here [artifact:${ARTIFACT}]. One hospital nearby [live:${LIVE}].`
    );
    expect(tokens.filter((t) => t.kind === "artifact")).toEqual([
      { kind: "artifact", id: ARTIFACT },
    ]);
    expect(tokens.filter((t) => t.kind === "live")).toEqual([{ kind: "live", id: LIVE }]);
  });

  it("preserves the surrounding prose in order", () => {
    const tokens = parseCitations(`Before [artifact:${ARTIFACT}] after.`);
    expect(tokens.map((t) => t.kind)).toEqual(["text", "artifact", "text"]);
    expect(tokens[0].value).toBe("Before ");
    expect(tokens[2].value).toBe(" after.");
  });

  it("renders a malformed citation as literal text rather than a chip", () => {
    // A chip asserts that a specific record backs the sentence. A citation the
    // app could not parse backs nothing, so it must not look like one.
    const tokens = parseCitations("Assessed here [artifact:nope].");
    expect(tokens).toEqual([{ kind: "text", value: "Assessed here [artifact:nope]." }]);
  });

  it("handles empty and missing text", () => {
    expect(parseCitations("")).toEqual([]);
    expect(parseCitations(null)).toEqual([]);
    expect(parseCitations(undefined)).toEqual([]);
  });
});

describe("verifiabilityLabel", () => {
  it("names each point on the axis", () => {
    expect(verifiabilityLabel("retained").label).toBe("retained");
    expect(verifiabilityLabel("re-derivable").label).toBe("re-derivable");
    expect(verifiabilityLabel("cited-only").label).toBe("cited-only");
  });

  it("says a re-derivable answer is not retained", () => {
    expect(verifiabilityLabel("re-derivable").detail).toMatch(/not\s+retained/);
  });

  it("returns null when the gateway did not state one", () => {
    // Unstated must not default to the strongest value — that would claim a
    // hashed copy exists for an answer nobody said that about.
    expect(verifiabilityLabel(undefined)).toBeNull();
    expect(verifiabilityLabel(null)).toBeNull();
    expect(verifiabilityLabel("retianed")).toBeNull();
  });
});

describe("resolveCitation", () => {
  const row = (sha, path) => ({ sha256: sha, path, agent: "a", created_utc: "t" });

  it("distinguishes 'nothing loaded' from 'searched and absent'", () => {
    expect(resolveCitation({}, "abc123abc123").status).toBe("no_manifests");
    expect(resolveCitation({ e: [] }, "abc123abc123").status).toBe("no_manifests");
    expect(
      resolveCitation({ e: [row("f".repeat(64), "x")] }, "abc123abc123").status
    ).toBe("not_found");
  });

  it("matches by sha256 prefix and reports the owning event", () => {
    const sha = "abc123abc123" + "0".repeat(52);
    const out = resolveCitation(
      { "eaton-2025": [row(sha, "exposure/grid.geojson")] },
      "abc123abc123"
    );
    expect(out.status).toBe("found");
    expect(out.matches).toHaveLength(1);
    expect(out.matches[0].eventId).toBe("eaton-2025");
    expect(out.matches[0].row.path).toBe("exposure/grid.geojson");
  });

  it("returns every manifest row for a rebuilt artifact, across events", () => {
    const sha = "abc123abc123" + "0".repeat(52);
    const out = resolveCitation(
      { a: [row(sha, "v1"), row(sha, "v2")], b: [row(sha, "v3")] },
      "abc123abc123"
    );
    expect(out.matches.map((m) => m.row.path)).toEqual(["v1", "v2", "v3"]);
  });

  it("ignores rows without a sha256 rather than crashing on them", () => {
    const out = resolveCitation({ e: [{ path: "no-sha" }] }, "abc123abc123");
    expect(out.status).toBe("not_found");
  });
});
