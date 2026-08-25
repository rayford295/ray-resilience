# Design — asking a question about a drawn area

**Date:** 2026-08-25 · **Status:** approved in brainstorming (approach and the seven design
sections approved by the owner, 2026-08-25) · **Scope:** one new query path through the
existing gateway; no new dependencies, no new policy rules.

## 1. What this adds, and why the obvious version of it is wrong

Today a planner asks a question and the app sends the **map centre** — `ChatPanel.jsx` posts
`{role, lat, lon, question}` and `EvidenceStore.evidence_for(lat, lon)` resolves that point to a
single H3 r9 cell. The answer is about one tile, roughly 0.1 km².

This design lets a planner **draw a rectangle and ask about it**: select an area, ask a question,
get an answer that covers the selection and says plainly which parts of it were evaluated.

The prompting references were `terraquery.ai` and a demonstration over Frankfurt municipal
geodata. They are two different products, and only one of them is a fit. TerraQuery is an
ingestion product: upload your own orthomosaics and shapefiles, have them preprocessed, then chat
over them; its answers are counts and marked maps and they **cite nothing**. The Frankfurt
demonstration is the shape adopted here: draw over data that is already loaded and ask about it.

**The obvious version of this feature contradicts the system's central claim.** GeoSteward's
competence is bounded on purpose: exposure and damage analysis exist only inside three deep-case
AOIs, and outside them the app says so rather than extrapolating. "Draw any rectangle and ask"
invites questions about places with no evidence. That is not a reason to refuse the feature — it
is the reason the feature has to be designed rather than copied.

The resolution is that a selection is answered for the part that was evaluated, with the rest
declared. That is the same instinct `app/src/lib/coverage.js` already applies to resident address
lookups, where an unreadable layer produces `unknown` rather than a confident negative.

## 2. Scope

**In scope.** A planner-mode rectangle selection; an area-shaped request through the existing
gateway; area evidence retrieval across all intersecting events; coverage stated as declared
unknowns; the selected cells returned so the app can highlight them.

**Not in scope.** Uploading user data (the TerraQuery shape — it collides with the provenance
model, since unvetted user data has no tier, no registry profile, and no distribution class, and
it needs its own spec). Resident-mode selection. Freehand or multi-polygon selection. Persisting
a selection across sessions. Any change to the ten defects recorded in `docs/STATUS.md`.

## 3. Four decisions, with the reasoning that produced them

### 3.1 Coverage fraction does not enter the claim plane

A drawn rectangle can straddle a deep-case boundary, so "is this in an AOI" stops being a
yes-or-no question and becomes a proportion. The tempting move is a match key —
`aoi_coverage_at_least: 0.8` — that authorizes an answer only when enough of the selection is
covered.

That would be wrong twice over. It invents a threshold, and a threshold is a number somebody has
to defend; this project's style is to refuse magic numbers in governance. More fundamentally it
confuses two questions the two planes exist to keep apart: the claim plane answers **may the agent
assert this**, and coverage answers **about what**. Partial coverage is not an authorization
problem. It is an uncertainty, and uncertainty in this system travels with the evidence as a
declared unknown, never as a gate.

So `in_aoi` stays a boolean and its meaning widens by one word: the selection **intersects** any
deep-case AOI. `PolicyRequest` gains no field, `_KNOWN_MATCH_KEYS` does not change, and
`policy_v1.yaml` is untouched. `deny-outside-aoi` keeps working: a selection intersecting nothing
is `in_aoi: false` and is refused by the rule that already exists.

### 3.2 Enumerate the grids, not the polygon

The natural implementation is `h3.polygon_to_cells(selection, 9)` — ask H3 which cells the
rectangle covers. It does not survive contact with a user: a rectangle drawn over the continental
United States enumerates an astronomical number of r9 cells, so the feature would need a maximum
selection area, which is another number somebody has to defend.

Inverting the loop removes the problem rather than capping it. **Iterate the cells that exist in
the committed grids and test each centre against the rectangle.** Every grid is already indexed
`{h3_cell: properties}` by `EvidenceStore._grids`, and the three deep cases hold **6,875 cells in
total** (Eaton 265 + 265 + 109, Milton 15 + 5,618, Ian 190 + 413). Worst case is 6,875 point-in-box
tests, which is nothing, and the bound is structural: **a selection can never match more cells than
exist**. No cap is needed, so no threshold has to be justified.

`h3.cell_to_latlng` gives the centre; h3 4.5.0 is already a dependency through the `deepcase`
extra.

### 3.3 An area sees every intersecting event, not the first one

`EvidenceStore.locate` returns on its first bbox match. That is harmless for a point, which can
sit in only one deep case, and wrong for a rectangle, which can span two. The area path iterates
all events.

Consequence for the answer: **statistics are never merged across events.** Eaton's damage grid and
Milton's debris grid measure different things from different sources; a single count spanning both
would be a fabricated quantity. Each event's contribution is stated separately, and the answer says
which events the selection touched.

### 3.4 The answer carries the cells it used

The existing `answer` response gains a `cells` field: the H3 indices the evidence came from. The
app highlights them, which is what makes the answer spatial rather than a paragraph that happens to
mention an area.

This is the finest-grained thing the API has ever returned, so it is worth being explicit about why
it is safe. These are **tile** identifiers at r9 — the same resolution already published in the
grids the app renders and serves from `app/public/events/`. It discloses nothing the map does not
already show, and `deny-parcel-any-role` continues to govern the claim plane independently. The
field is a list of identifiers, never properties: the app already holds the properties.

## 4. Request shape

`/ask` accepts `area` as an alternative to `lat`/`lon`:

```
{ "role": "planner",
  "question": "...",
  "area": {"min_lat": ..., "min_lon": ..., "max_lat": ..., "max_lon": ...} }
```

Exactly one of `area` or the `lat`/`lon` pair must be present; neither or both is a 422 from
FastAPI's validator, before anything reaches the harness. A rectangle is a bounding box in WGS84,
which is what a box-select produces and what `_aoi_boxes` already speaks.

`Steward.answer` takes the same either-or. Its existing point behaviour is unchanged — this is an
added path, not a replacement, and the point path stays because a resident address lookup is
genuinely a point.

**Planner-only is enforced by the claim plane, not by the transport.** `deny-resident-damage-
assessment` already exists; a resident sending an area gets the same refusal a resident sending a
point gets. Adding a role check in the endpoint would put an authorization decision outside the
plane that owns them — the mistake `published_events` was moved into `policy_v1.yaml` to correct.

## 5. Evidence retrieval and coverage

New: `EvidenceStore.evidence_for_area(bbox) -> EventEvidence`.

- For every event, test the AOI boxes against the rectangle for intersection. `in_aoi` is true if
  any intersects.
- For every intersecting event, walk each grid's cell index and keep cells whose centre falls
  inside the rectangle. Each surviving cell contributes a `Fact` exactly as the point path does,
  carrying the same artifact ID derived from the grid's sha256.
- `evidence_tier` is the **weakest** tier among the events touched, matching the weakest-link
  instinct the verifiability axis already uses: an answer spanning a Tier 3 case and a Tier 2 case
  is not a Tier 3 answer.

Coverage is attached as declared unknowns, in the shape the dossiers already use, and states:
which events the selection touched; how many cells matched, per event and per grid; and that the
answer speaks only for the matched cells. It does **not** compute a percentage of the rectangle's
area that lies outside evaluated ground — that would require a coverage geometry the repository
does not have, and inventing one would be a claim about the world rather than about the artifacts.

## 6. Answer contract and refusals

The four existing response types are unchanged in kind:

- **answer** — gains `cells`. Everything else, including `citations` and `verifiability`, keeps its
  current meaning.
- **refusal** — a selection intersecting no AOI yields `in_aoi: false` and `deny-outside-aoi` fires.
  No new rule.
- **no_evidence** — the selection intersects an AOI but matches zero cells (a rectangle inside the
  AOI's bounding box but off the grid). The declared unknowns explain the difference, because
  "inside the area of interest" and "on evaluated ground" are not the same thing and a planner
  should not have to guess which one failed.
- **outage** — unchanged.

`check_claims` is unchanged: an area answer cites artifact IDs like any other, and every one of its
six violation classes applies as before.

## 7. UI

`PlannerPanel` gains a rectangle draw tool. No new dependency: `maplibre-gl` 4.7 and `h3-js` 4.1
are already installed, and a box-select is a pointer-drag over the canvas with a styled overlay.

While a selection is active, `ChatPanel`'s header replaces "about the map center" with the
selection and the number of evaluated cells inside it, so the scope of the question is visible
before it is asked rather than explained after. Clearing the selection returns to point mode.

When an answer returns, its `cells` are highlighted. Answers that refuse or declare no evidence
highlight nothing and show the declared unknowns with the prominence the app already gives them.

## 8. Testing

**Python.** Area evidence across two events (no merged statistics; both events named); a selection
inside an AOI bounding box matching zero cells; a selection intersecting nothing; a single-event
selection matching a known cell count; `evidence_tier` taking the weakest of the events touched;
the either-or request validation rejecting both-and-neither. The policy matrix gains rows for an
area request in and out of an AOI, asserting no new rule was needed to cover them.

**App.** The box-select producing a WGS84 bbox in the expected key order; the header reflecting a
live selection; `cells` highlighting on an answer and not on a refusal.

**The property worth pinning.** A test asserting that the cells returned for a selection are a
subset of the cells present in the committed grids — the structural bound from §3.2, which is what
makes the absence of a size cap safe rather than lucky.

## 9. Out of scope, deliberately

- **User data upload.** Its own spec, if it happens. It needs an answer to "how does unvetted user
  data acquire a tier and a provenance chain" before anything is built.
- **Resident-mode selection.** The interface is designed role-agnostically, so enabling it later is
  a front-end change; whether an exposure-only area answer is genuinely useful to a resident is a
  question worth asking separately.
- **Freehand and multi-polygon selection.** A rectangle is what a box-select produces and what
  `_aoi_boxes` already speaks. Arbitrary polygons need a point-in-polygon test and a richer request
  shape, and nothing yet shows the added expressiveness is wanted.
- **Fixing anything in `docs/STATUS.md`'s ten findings.** Those remain the owner's call. Note that
  finding 2 touches this path: `context.py:144` feeds declared unknowns into the evidence, so an
  area answer inside Eaton will carry the same stale SVI line a point answer does. This design does
  not make that worse, and does not fix it.

## 10. Risks

| Risk | Mitigation |
| --- | --- |
| A selection spanning two events produces a merged number | §3.3 forbids it; a two-event test asserts both are named separately |
| The feature invites questions about unevaluated ground | §3.1 answers the covered part and declares the rest; `deny-outside-aoi` still refuses a selection covering nothing |
| Cell enumeration becomes a performance problem | §3.2 bounds it structurally at 6,875 tests; a subset property test pins the bound |
| `cells` discloses more than the map does | §3.4: r9 tile identifiers, the same resolution already published and rendered |
| The area path drifts from the point path | Both build the same `EventEvidence` and go through one `Steward.answer`, one policy evaluation, one audit row |

## 11. Definition of done

- `/ask` accepts either a point or an area; both-and-neither are rejected before the harness.
- `EvidenceStore.evidence_for_area` returns evidence across all intersecting events, with coverage
  as declared unknowns and no merged cross-event statistics.
- `policy_v1.yaml`, `PolicyRequest`, and `_KNOWN_MATCH_KEYS` are unchanged.
- A planner can draw a rectangle, see how many evaluated cells it contains before asking, and see
  the answer's cells highlighted.
- The subset property test passes, along with the suite.
- `docs/manual/` is updated: chapter `01`'s capability catalogue gains an entry with its refusal
  boundary, `07` gains the area path in the request lifecycle, and `08` gains the draw tool.
