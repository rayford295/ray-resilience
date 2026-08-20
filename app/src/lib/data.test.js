// Validity is a claim the UI makes about the harness, so it has to be exactly
// as true as the audit log. These tests use the real shape of the committed
// eaton-2025 log, where one stage was rejected and re-run: nine check rows
// exist for `exposure.svi_context`, one of them failed, and the run that
// finally succeeded contains six.
//
// The bug they pin down: counting every historical check as one flat total and
// deciding pass/fail from the last stage row renders "9 checks passed", which
// is not true of any run that ever happened.

import { describe, expect, it } from "vitest";
import { stageValidity } from "./data.js";

/** The committed eaton-2025 audit rows for the twice-run SVI stage. */
const SVI_ROWS = [
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022423Z", payload: { check: "crs", passed: true, detail: "CRS EPSG:4326 matches expected" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022423Z", payload: { check: "join_integrity", passed: true, detail: "coverage 100.00%, no orphans" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022423Z", payload: { check: "join_integrity", passed: false, detail: "coverage 14.71% below required 100.00%" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "crs", passed: true, detail: "CRS EPSG:4326 matches expected" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "join_integrity", passed: true, detail: "coverage 100.00%, no orphans" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "join_integrity", passed: true, detail: "coverage 14.71%, no orphans" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "bounds", passed: true, detail: "svi_rank_min=0.0 within [0.0, 1.0]" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "bounds", passed: true, detail: "svi_rank_max=0.9323 within [0.0, 1.0]" } },
  { action: "check", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { check: "uncertainty", passed: true, detail: "field 'uncertainty' present" } },
  { action: "stage", actor: "exposure.svi_context", utc: "20260820T022620Z", payload: { status: "ok" } },
  // A different stage's rows must not leak into this one's runs.
  { action: "check", actor: "exposure.dins_grid", utc: "20260820T015631Z", payload: { check: "crs", passed: true, detail: "" } },
  { action: "stage", actor: "exposure.dins_grid", utc: "20260820T015631Z", payload: { status: "ok" } },
];

describe("stageValidity", () => {
  it("reports the latest run's own checks, not every check ever recorded", () => {
    const validity = stageValidity(SVI_ROWS, "exposure.svi_context");
    expect(validity.latest.nChecks).toBe(6);
    expect(validity.latest.nFailed).toBe(0);
    expect(validity.ok).toBe(true);
  });

  it("keeps the superseded failed run instead of folding it into the total", () => {
    const validity = stageValidity(SVI_ROWS, "exposure.svi_context");
    expect(validity.superseded).toHaveLength(1);
    expect(validity.superseded[0].nChecks).toBe(3);
    expect(validity.superseded[0].nFailed).toBe(1);
    expect(validity.superseded[0].failedChecks[0].detail).toMatch(/below required/);
  });

  it("does not mix rows from other stages into the run", () => {
    const validity = stageValidity(SVI_ROWS, "exposure.dins_grid");
    expect(validity.latest.nChecks).toBe(1);
    expect(validity.superseded).toHaveLength(0);
  });

  it("treats a run whose checks all passed as the only run when there is one", () => {
    const rows = [
      { action: "check", actor: "s", utc: "1", payload: { check: "a", passed: true } },
      { action: "check", actor: "s", utc: "1", payload: { check: "b", passed: true } },
      { action: "stage", actor: "s", utc: "1", payload: { status: "ok" } },
    ];
    const validity = stageValidity(rows, "s");
    expect(validity.latest.nChecks).toBe(2);
    expect(validity.superseded).toHaveLength(0);
    expect(validity.ok).toBe(true);
  });

  it("reports a failing latest run as not ok", () => {
    const rows = [
      { action: "check", actor: "s", utc: "1", payload: { check: "a", passed: false, detail: "nope" } },
      { action: "stage", actor: "s", utc: "1", payload: { status: "failed" } },
    ];
    const validity = stageValidity(rows, "s");
    expect(validity.ok).toBe(false);
    expect(validity.latest.nFailed).toBe(1);
  });

  it("treats an aborted trailing run as the latest, so a crash is never green", () => {
    // Checks with no closing stage row mean the stage died mid-flight. Showing
    // the previous successful run here would report stale success as current.
    const rows = [
      { action: "check", actor: "s", utc: "1", payload: { check: "a", passed: true } },
      { action: "stage", actor: "s", utc: "1", payload: { status: "ok" } },
      { action: "check", actor: "s", utc: "2", payload: { check: "a", passed: false, detail: "boom" } },
    ];
    const validity = stageValidity(rows, "s");
    expect(validity.ok).toBe(false);
    expect(validity.latest.nFailed).toBe(1);
    expect(validity.superseded).toHaveLength(1);
  });

  it("groups by run_id when the log carries one, ignoring timestamp collisions", () => {
    // Future runs stamp a run_id. Two runs inside the same second are
    // indistinguishable by timestamp, so the explicit id has to win.
    const rows = [
      { action: "check", actor: "s", utc: "1", run_id: "r1", payload: { check: "a", passed: false, detail: "old" } },
      { action: "stage", actor: "s", utc: "1", run_id: "r1", payload: { status: "failed" } },
      { action: "check", actor: "s", utc: "1", run_id: "r2", payload: { check: "a", passed: true } },
      { action: "stage", actor: "s", utc: "1", run_id: "r2", payload: { status: "ok" } },
    ];
    const validity = stageValidity(rows, "s");
    expect(validity.ok).toBe(true);
    expect(validity.latest.nChecks).toBe(1);
    expect(validity.superseded).toHaveLength(1);
    expect(validity.superseded[0].nFailed).toBe(1);
  });

  it("splits a run that restarted without closing, using the check sequence", () => {
    // eaton-2025's SVI stage aborted mid-sequence and left no stage row, so
    // the only structural marker is that the sequence began again. Timestamps
    // cannot carry this: ian-2022's sample-density stage runs one sequence
    // across a second boundary, and grouping by timestamp would split it.
    const spansASecond = [
      { action: "check", actor: "s", utc: "20260820T033819Z", payload: { check: "crs", passed: true } },
      { action: "check", actor: "s", utc: "20260820T033819Z", payload: { check: "bounds", passed: true } },
      { action: "check", actor: "s", utc: "20260820T033820Z", payload: { check: "uncertainty", passed: true } },
      { action: "stage", actor: "s", utc: "20260820T033820Z", payload: { status: "ok" } },
    ];
    const validity = stageValidity(spansASecond, "s");
    expect(validity.latest.nChecks).toBe(3);
    expect(validity.superseded).toHaveLength(0);
  });

  it("reports a stage recorded with no outcome checks as such, not as a failure", () => {
    // snapshot.registry and dossier.event_record record a stage without
    // outcome checks. "0 of 0 checks failed" reads as an alarm about nothing.
    const rows = [{ action: "stage", actor: "s", utc: "1", payload: { status: "ok" } }];
    const validity = stageValidity(rows, "s");
    expect(validity.latest.nChecks).toBe(0);
    expect(validity.ok).toBe(true);
  });

  it("reports no runs rather than a passing state when the stage never ran", () => {
    const validity = stageValidity(SVI_ROWS, "stage.that.never.ran");
    expect(validity.ok).toBe(false);
    expect(validity.latest).toBeNull();
    expect(validity.superseded).toHaveLength(0);
  });
});
