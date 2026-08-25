# Area Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A planner draws a rectangle on the map, asks a question, and gets an answer that covers the selection and says which parts of it were evaluated.

**Architecture:** One added path through the existing gateway. `EvidenceStore` gains an area retrieval that walks the committed grids and keeps cells whose centre falls in the rectangle; `Steward.answer` accepts a point or an area and returns the cells it used; the app gains a box-select and highlights what comes back. No new policy rules, no new dependencies.

**Tech Stack:** Python 3.11 (stdlib + `h3` 4.5.0, already a `deepcase` dependency), FastAPI/Pydantic for the endpoint, React 18 + MapLibre GL 4.7 + `h3-js` 4.1 (all already installed), `unittest` and `vitest`.

**Spec:** [`docs/design/specs/2026-08-25-area-query-design.md`](../specs/2026-08-25-area-query-design.md)

## Global Constraints

- **No new dependencies**, Python or npm. `h3` 4.5.0 and `maplibre-gl` 4.7 are present; use them.
- **`policy_v1.yaml`, `PolicyRequest`, and `_KNOWN_MATCH_KEYS` must not change.** `in_aoi` stays a boolean; its meaning widens to "the selection intersects any deep-case AOI". If you find yourself wanting a coverage-fraction match key, stop — the spec's §3.1 explains why that is the wrong plane.
- **Never merge statistics across events.** Eaton damage and Milton debris measure different things; one number spanning both would be a fabricated quantity. Each event's contribution is stated separately.
- **Enumerate the grids, not the polygon.** Do not call `h3.polygon_to_cells`. Iterate the cells already indexed by `EvidenceStore._grids` and test each centre with `h3.cell_to_latlng`. The bound is structural — 6,875 cells exist across the three deep cases — so no size cap is needed and none should be added.
- **A bounding box is `{"min_lat", "min_lon", "max_lat", "max_lon"}` in WGS84**, the same shape `_aoi_boxes` already returns.
- **Planner-only is enforced by the claim plane**, not by the transport. Do not add a role check to the endpoint.
- **Follow the existing style:** comments explain *why*, not *what*; unhashed data never becomes citable evidence (`_artifact_id` returning `None` means skip).
- Every task ends with the full suite green: `python -m unittest discover -s tests` and, for app tasks, `cd app && npm test`.

---

### Task 1: Area evidence retrieval

The core. Everything else is wiring.

**Files:**
- Modify: `src/geosteward/gateway/context.py`
- Test: `tests/test_gateway_area.py` (create)

**Interfaces:**
- Consumes: `EvidenceStore._grids(event_id) -> dict[str, dict[str, Any]]`, `EvidenceStore._artifact_id(event_id, filename) -> str | None`, `EvidenceStore._aoi_boxes(record) -> list[dict[str, float]]`, `Fact`, `EventEvidence`, `RESOLUTION = 9`.
- Produces, and Task 2 relies on these exactly:
  - `EventEvidence` gains two fields: `event_ids: list[str]` (default empty) and `cells: list[str]` (default empty). `event_id` keeps its current meaning as a **label** — it is only ever used in audit payloads and the response's `"event"` field, never matched on — and for a multi-event selection it becomes the joined label `"+".join(sorted(event_ids))`.
  - `boxes_intersect(a: dict[str, float], b: dict[str, float]) -> bool` — module-level.
  - `EvidenceStore.locate_area(bbox: dict[str, float]) -> list[str]` — every event whose AOI intersects, sorted.
  - `EvidenceStore.evidence_for_area(bbox: dict[str, float]) -> EventEvidence`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gateway_area.py
import unittest
from pathlib import Path

from geosteward.gateway.context import EvidenceStore, boxes_intersect

EVENTS = Path(__file__).resolve().parents[1] / "events"

# Eaton's AOI, comfortably inside it. Verified against
# events/eaton-2025/dossier/event_record.json's aoi_bbox_wgs84.
EATON_BOX = {"min_lat": 34.15, "min_lon": -118.16, "max_lat": 34.23, "max_lon": -118.06}
# Open ocean south-west of the Galapagos: intersects nothing.
NOWHERE = {"min_lat": -10.0, "min_lon": -120.0, "max_lat": -9.0, "max_lon": -119.0}


class BoxesIntersectTests(unittest.TestCase):
    def test_overlapping_boxes_intersect(self):
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 2, "max_lon": 2}
        b = {"min_lat": 1, "min_lon": 1, "max_lat": 3, "max_lon": 3}
        self.assertTrue(boxes_intersect(a, b))

    def test_disjoint_boxes_do_not_intersect(self):
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 1, "max_lon": 1}
        b = {"min_lat": 5, "min_lon": 5, "max_lat": 6, "max_lon": 6}
        self.assertFalse(boxes_intersect(a, b))

    def test_touching_edges_intersect(self):
        # A selection dragged flush to an AOI edge is a real selection, not a miss.
        a = {"min_lat": 0, "min_lon": 0, "max_lat": 1, "max_lon": 1}
        b = {"min_lat": 1, "min_lon": 1, "max_lat": 2, "max_lon": 2}
        self.assertTrue(boxes_intersect(a, b))


class AreaEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(EVENTS)

    def test_selection_outside_every_aoi_is_not_in_aoi(self):
        ev = self.store.evidence_for_area(NOWHERE)
        self.assertFalse(ev.in_aoi)
        self.assertEqual(ev.cells, [])
        self.assertEqual(ev.event_ids, [])

    def test_selection_inside_eaton_matches_cells_and_cites_artifacts(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        self.assertTrue(ev.in_aoi)
        self.assertEqual(ev.event_ids, ["eaton-2025"])
        self.assertTrue(ev.cells, "expected the selection to match committed cells")
        self.assertTrue(ev.facts)
        # Unhashed data never becomes citable evidence.
        self.assertTrue(all(f.artifact_id for f in ev.facts))

    def test_returned_cells_are_a_subset_of_the_committed_grids(self):
        # The structural bound that makes a size cap unnecessary: a selection
        # cannot match more cells than exist. Pins spec section 3.2.
        ev = self.store.evidence_for_area(EATON_BOX)
        committed = set()
        for index in self.store._grids("eaton-2025").values():
            committed |= set(index)
        self.assertTrue(set(ev.cells) <= committed)

    def test_coverage_is_declared_not_merged(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        coverage = [f.text for f in ev.facts if "selection" in f.text]
        self.assertTrue(coverage, "expected a declared coverage fact")
        self.assertTrue(any("eaton-2025" in t for t in coverage))

    def test_tier_is_the_weakest_among_events_touched(self):
        ev = self.store.evidence_for_area(EATON_BOX)
        tiers = [
            int(self.store.events[e]["record"].get("evidence_tier", 1))
            for e in ev.event_ids
        ]
        self.assertEqual(ev.evidence_tier, min(tiers))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_gateway_area -v`
Expected: FAIL — `ImportError: cannot import name 'boxes_intersect'`.

**Before implementing**, confirm `EATON_BOX` really is inside Eaton's AOI and really does match cells:

```bash
python3 -c "
import json; r=json.load(open('events/eaton-2025/dossier/event_record.json'))
print(r.get('aoi_bbox_wgs84') or r.get('aoi'))"
```

If the box is wrong, correct the constant in the test to a box inside the real AOI — do not loosen the assertions to fit a wrong box.

- [ ] **Step 3: Implement**

Add to `src/geosteward/gateway/context.py`:

```python
def boxes_intersect(a: dict[str, float], b: dict[str, float]) -> bool:
    """Do two WGS84 bounding boxes overlap? Touching edges count.

    A selection dragged flush against an AOI edge is a real selection; treating
    it as a miss would make the boundary behave differently from either side.
    """
    return (
        a["min_lat"] <= b["max_lat"]
        and b["min_lat"] <= a["max_lat"]
        and a["min_lon"] <= b["max_lon"]
        and b["min_lon"] <= a["max_lon"]
    )
```

Extend `EventEvidence` with the two new fields (keep the existing ones and their order):

```python
    event_ids: list[str] = field(default_factory=list)
    cells: list[str] = field(default_factory=list)
```

Add to `EvidenceStore`:

```python
    def locate_area(self, bbox: dict[str, float]) -> list[str]:
        """Every event whose AOI meets the rectangle.

        `locate` returns on its first match, which is right for a point — it can
        sit in only one deep case — and wrong for a rectangle, which can span two.
        """
        hits = []
        for event_id, entry in self.events.items():
            boxes = self._aoi_boxes(entry["record"])
            if any(boxes_intersect(bbox, box) for box in boxes):
                hits.append(event_id)
        return sorted(hits)

    def evidence_for_area(self, bbox: dict[str, float]) -> EventEvidence:
        event_ids = self.locate_area(bbox)
        if not event_ids:
            return EventEvidence(event_id="none", evidence_tier=1, in_aoi=False)

        tiers = [
            int(self.events[e]["record"].get("evidence_tier", 1)) for e in event_ids
        ]
        evidence = EventEvidence(
            event_id="+".join(event_ids),
            #: Weakest of the events touched, for the same reason verifiability
            #: takes the weakest link: an answer spanning a Tier 2 case and a
            #: Tier 3 case is not a Tier 3 answer.
            evidence_tier=min(tiers),
            in_aoi=True,
            event_ids=event_ids,
        )

        for event_id in event_ids:
            matched: set[str] = set()
            per_grid: list[str] = []
            for filename, index in self._grids(event_id).items():
                aid = self._artifact_id(event_id, filename)
                if aid is None:
                    continue  # unhashed data never becomes citable evidence
                hits = 0
                for cell, props in index.items():
                    lat, lon = h3.cell_to_latlng(cell)
                    if not (
                        bbox["min_lat"] <= lat <= bbox["max_lat"]
                        and bbox["min_lon"] <= lon <= bbox["max_lon"]
                    ):
                        continue
                    hits += 1
                    matched.add(cell)
                    unc = props.get("uncertainty")
                    unc_note = (
                        f" | uncertainty: {json.dumps(unc, ensure_ascii=False)}"
                        if unc
                        else ""
                    )
                    evidence.facts.append(
                        Fact(
                            text=f"[{event_id} / {filename} / tile {cell}] "
                            f"{_scalar_items(props)}{unc_note}",
                            artifact_id=aid,
                            source_path=filename,
                        )
                    )
                if hits:
                    per_grid.append(f"{filename}: {hits}")

            record = self.events[event_id]["record"]
            record_id = self._artifact_id(event_id, "event_record.json")
            if record_id:
                #: Coverage travels with the evidence as a declared unknown, not
                #: as an authorization input. What the selection did NOT cover is
                #: not computed as a fraction: that would need a geometry of
                #: evaluated ground the repository does not have, and inventing
                #: one would be a claim about the world rather than the artifacts.
                evidence.facts.append(
                    Fact(
                        text=(
                            f"[{event_id} / selection coverage] "
                            f"{len(matched)} evaluated tile(s) inside the selection "
                            f"({'; '.join(per_grid) if per_grid else 'no grid matched'}). "
                            "This answer speaks only for those tiles."
                        ),
                        artifact_id=record_id,
                        source_path="event_record.json",
                    )
                )
                for unknown in record.get("declared_unknowns", []):
                    evidence.facts.append(
                        Fact(
                            text=f"[{event_id} / declared unknown] {unknown}",
                            artifact_id=record_id,
                            source_path="event_record.json",
                        )
                    )
            evidence.cells.extend(sorted(matched))

        return evidence
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_gateway_area -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Full suite, then commit**

Run: `python -m unittest discover -s tests`
Expected: PASS — 238 existing tests plus 8 new.

```bash
git add src/geosteward/gateway/context.py tests/test_gateway_area.py
git commit -m "feat: evidence retrieval for a drawn area, across every event it touches"
```

---

### Task 2: The area path through `Steward.answer`

**Files:**
- Modify: `src/geosteward/gateway/steward.py`
- Test: `tests/test_gateway_area.py` (extend)

**Interfaces:**
- Consumes: `EvidenceStore.evidence_for_area(bbox) -> EventEvidence` with `.cells` and `.event_ids` (Task 1).
- Produces, and Task 3 relies on this: `Steward.answer(role, question, *, lat=None, lon=None, area=None) -> dict`. Exactly one of `area` or the `lat`/`lon` pair must be given; both or neither raises `ValueError`. An `answer`-type response gains `"cells": list[str]`.

**The signature change is keyword-only after `question` on purpose.** The existing call is positional — `answer(role, lat, lon, question)` — and silently accepting a differently-ordered positional call would be a latent bug. Update the two call sites: `gateway/main.py` and `scripts/ask_steward.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gateway_area.py`:

```python
class AnswerAreaContractTests(unittest.TestCase):
    """The either-or contract, checked without invoking a model."""

    def setUp(self):
        from geosteward.gateway.steward import Steward
        self.steward = Steward(store=EvidenceStore(EVENTS), llm=None, policy=None)

    def test_neither_point_nor_area_is_rejected(self):
        with self.assertRaises(ValueError):
            self.steward.answer("planner", "how bad is it?")

    def test_both_point_and_area_is_rejected(self):
        with self.assertRaises(ValueError):
            self.steward.answer(
                "planner", "how bad is it?", lat=34.19, lon=-118.1, area=EATON_BOX
            )
```

Construct `Steward` the way the existing `tests/test_gateway_steward.py` does — read it first and mirror its fixture, including its fake LLM and policy. Replace the `setUp` above with that construction; the two assertions are what matter.

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_gateway_area -v`
Expected: FAIL — `TypeError` on the new call shape.

- [ ] **Step 3: Implement**

In `src/geosteward/gateway/steward.py`, change the signature and the first evidence line:

```python
    def answer(
        self,
        role: str,
        question: str,
        *,
        lat: float | None = None,
        lon: float | None = None,
        area: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        has_point = lat is not None and lon is not None
        if has_point == (area is not None):
            #: Exactly one, and the check is here rather than only in the
            #: endpoint so a direct caller cannot skip it.
            raise ValueError("give either lat/lon or area, not both and not neither")

        purpose, resolution = classify(question)
        evidence = (
            self.store.evidence_for_area(area)
            if area is not None
            else self.store.evidence_for(lat, lon)
        )
```

Everything downstream is unchanged — the policy request, the audit rows, the retry loop, `check_claims`. In the `answer` response dict, add one line beside `"n_facts"`:

```python
                    #: The tiles this answer drew on, so the map can show what
                    #: it is about. r9 identifiers only, the resolution already
                    #: published in the grids the app renders.
                    "cells": evidence.cells,
```

Update the two call sites to keywords:
- `gateway/main.py`: `steward.answer(request.role, request.question, lat=..., lon=..., area=...)` — Task 3 finishes this; for now pass `lat=request.lat, lon=request.lon`.
- `scripts/ask_steward.py`: pass `lat=` and `lon=` by keyword.

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_gateway_area tests.test_gateway_steward -v`
Expected: PASS — the new contract tests plus the existing 28 gateway tests, which must not regress.

- [ ] **Step 5: Full suite, then commit**

```bash
git add src/geosteward/gateway/steward.py gateway/main.py scripts/ask_steward.py tests/test_gateway_area.py
git commit -m "feat: Steward.answer takes a point or an area, and returns the tiles it used"
```

---

### Task 3: The endpoint accepts an area

**Files:**
- Modify: `gateway/main.py`
- Test: `tests/test_gateway_area.py` (extend)

**Interfaces:**
- Consumes: `Steward.answer(role, question, *, lat, lon, area)` (Task 2).
- Produces: `/ask` accepting `{role, question, area}` or `{role, question, lat, lon}`.

- [ ] **Step 1: Write the failing test**

```python
class AskRequestValidationTests(unittest.TestCase):
    def test_area_only_validates(self):
        from gateway.main import AskRequest
        r = AskRequest(role="planner", question="how bad?", area=EATON_BOX)
        self.assertIsNotNone(r.area)

    def test_neither_is_rejected(self):
        from pydantic import ValidationError
        from gateway.main import AskRequest
        with self.assertRaises(ValidationError):
            AskRequest(role="planner", question="how bad?")

    def test_both_is_rejected(self):
        from pydantic import ValidationError
        from gateway.main import AskRequest
        with self.assertRaises(ValidationError):
            AskRequest(
                role="planner", question="how bad?",
                lat=34.19, lon=-118.1, area=EATON_BOX,
            )
```

`fastapi` and `pydantic` come from the `gateway` extra. If the import fails, install it: `python -m pip install -e ".[deepcase,gateway]"`. If the extra is genuinely unavailable, mark this class with `@unittest.skipUnless` on the import rather than deleting it, and say so in your report.

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_gateway_area -v`
Expected: FAIL — `AskRequest` has no `area` field.

- [ ] **Step 3: Implement**

In `gateway/main.py`:

```python
class AreaBox(BaseModel):
    min_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)


class AskRequest(BaseModel):
    role: str = Field(pattern="^(resident|planner)$")
    question: str = Field(min_length=1, max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    area: AreaBox | None = None

    @model_validator(mode="after")
    def exactly_one_location(self):
        #: Rejected here, before the harness sees it, so an ambiguous request
        #: never reaches the plane that decides authorization.
        if (self.lat is not None and self.lon is not None) == (self.area is not None):
            raise ValueError("give either lat/lon or area, not both and not neither")
        return self
```

Import `model_validator` from `pydantic`. Update the route:

```python
@app.post("/ask")
def ask(request: AskRequest) -> dict:
    return steward.answer(
        request.role,
        request.question,
        lat=request.lat,
        lon=request.lon,
        area=request.area.model_dump() if request.area else None,
    )
```

**Do not add a role check.** A resident sending an area gets the same refusal a resident sending a point gets, from `deny-resident-damage-assessment` — authorization belongs to the claim plane.

- [ ] **Step 4: Run tests, then the full suite**

Run: `python -m unittest tests.test_gateway_area -v` then `python -m unittest discover -s tests`

- [ ] **Step 5: Commit**

```bash
git add gateway/main.py tests/test_gateway_area.py
git commit -m "feat: /ask takes either a point or an area, exactly one"
```

---

### Task 4: Draw a rectangle and ask about it

**Files:**
- Modify: `app/src/components/MapView.jsx`, `app/src/App.jsx`, `app/src/components/ChatPanel.jsx`, `app/src/styles.css`
- Test: `app/src/lib/area.js` (create) and `app/src/lib/area.test.js` (create)

**Interfaces:**
- Consumes: `/ask` accepting `area` (Task 3).
- Produces:
  - `app/src/lib/area.js` exporting `bboxFromCorners(a, b) -> {min_lat, min_lon, max_lat, max_lon}` where `a` and `b` are `{lat, lng}` drag corners in either order, and `cellsInBox(cells, bbox, cellToLatLng) -> string[]`.
  - `App` state `selection` (a bbox or `null`), passed to `ChatPanel` as `selection`.

**Put the geometry in `app/src/lib/`, not in the component.** Every other testable thing in this app lives there — `coverage.js`, `watch.js`, `citations.js` — and the four `.test.js` files all sit beside them. A bbox computed inside a React component cannot be tested.

- [ ] **Step 1: Write the failing tests**

```javascript
// app/src/lib/area.test.js
import { describe, expect, it } from "vitest";
import { bboxFromCorners, cellsInBox } from "./area.js";

describe("bboxFromCorners", () => {
  it("normalises corners dragged in any direction", () => {
    const a = { lat: 34.2, lng: -118.06 };
    const b = { lat: 34.15, lng: -118.16 };
    expect(bboxFromCorners(a, b)).toEqual({
      min_lat: 34.15, min_lon: -118.16, max_lat: 34.2, max_lon: -118.06,
    });
    // Dragging the other way must give the same box.
    expect(bboxFromCorners(b, a)).toEqual(bboxFromCorners(a, b));
  });
});

describe("cellsInBox", () => {
  const box = { min_lat: 0, min_lon: 0, max_lat: 1, max_lon: 1 };
  const centres = { in: [0.5, 0.5], out: [5, 5], edge: [1, 1] };
  const cellToLatLng = (c) => centres[c];

  it("keeps cells whose centre is inside, including on the edge", () => {
    expect(cellsInBox(["in", "out", "edge"], box, cellToLatLng)).toEqual(["in", "edge"]);
  });

  it("returns nothing for an empty cell list", () => {
    expect(cellsInBox([], box, cellToLatLng)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd app && npx vitest run src/lib/area.test.js`
Expected: FAIL — cannot resolve `./area.js`.

- [ ] **Step 3: Implement the library**

```javascript
// app/src/lib/area.js
/**
 * Geometry for a drawn selection. Kept out of the component so it can be
 * tested: a bbox computed inside a React render is a bbox nobody checks.
 */

/** Normalise two drag corners into a WGS84 bounding box, in the key order the gateway speaks. */
export function bboxFromCorners(a, b) {
  return {
    min_lat: Math.min(a.lat, b.lat),
    min_lon: Math.min(a.lng, b.lng),
    max_lat: Math.max(a.lat, b.lat),
    max_lon: Math.max(a.lng, b.lng),
  };
}

/**
 * Which of these cells have their centre inside the box. Edges count, matching
 * the gateway's `boxes_intersect`, so the two sides agree about a selection
 * dragged flush to a boundary.
 */
export function cellsInBox(cells, bbox, cellToLatLng) {
  return cells.filter((cell) => {
    const [lat, lon] = cellToLatLng(cell);
    return (
      lat >= bbox.min_lat && lat <= bbox.max_lat &&
      lon >= bbox.min_lon && lon <= bbox.max_lon
    );
  });
}
```

- [ ] **Step 4: Run tests**

Run: `cd app && npx vitest run src/lib/area.test.js`
Expected: PASS, 3 tests.

- [ ] **Step 5: Wire the draw tool**

In `MapView.jsx`, add a shift-drag box-select: on `mousedown` with `shiftKey`, record the corner and disable `map.dragPan`; on `mousemove`, draw an absolutely-positioned `div` overlay sized to the drag; on `mouseup`, convert both corners with `map.unproject`, call `bboxFromCorners`, hand the result to a new `onSelect` prop, and re-enable `dragPan`. Escape cancels.

Use a plain overlay `div` styled in `styles.css` — MapLibre needs no plugin for this and the constraint forbids adding one.

In `App.jsx`, hold `const [selection, setSelection] = useState(null)`, pass `onSelect={setSelection}` to `MapView` and `selection={selection}` to `ChatPanel`.

- [ ] **Step 6: Send the area**

In `ChatPanel.jsx`, replace the body construction:

```javascript
        body: JSON.stringify(
          selection
            ? { role, question, area: selection }
            : { role, lat: location.lat, lon: location.lng, question }
        ),
```

Guard the early return on having either: `if (!question || busy || (!location && !selection)) return;`

Replace the header text so the scope is visible before the question is asked, not explained after: when `selection` is set, show the selection and how many evaluated cells it contains (compute with `cellsInBox` over the cells already loaded in `layers`), with a button to clear it; otherwise keep "about the map center".

- [ ] **Step 7: Run the app suite, then commit**

Run: `cd app && npm test`
Expected: PASS — the existing 37 tests plus 3 new.

```bash
git add app/src/lib/area.js app/src/lib/area.test.js app/src/components/MapView.jsx app/src/App.jsx app/src/components/ChatPanel.jsx app/src/styles.css
git commit -m "feat: shift-drag a rectangle and ask about it"
```

---

### Task 5: Highlight the answer, and document the capability

**Files:**
- Modify: `app/src/components/MapView.jsx`, `app/src/App.jsx`, `app/src/components/ChatPanel.jsx`, `app/src/styles.css`
- Modify: `docs/manual/01-capabilities.md`, `docs/manual/07-gateway-and-agent.md`, `docs/manual/08-app-pwa.md`

- [ ] **Step 1: Highlight the returned cells**

When a reply of type `answer` arrives, lift its `cells` into `App` state and render them in `MapView` as a highlight layer above the active view. A refusal, a `no_evidence`, or an outage highlights nothing — those responses carry no cells, and showing a stale highlight beside a refusal would suggest the refusal was about somewhere else.

- [ ] **Step 2: Run the app suite**

Run: `cd app && npm test` — expected PASS.

- [ ] **Step 3: Document it in the manual**

The manual is bilingual: English first, Chinese restatement as a `>` blockquote. Terminology is bound by `docs/manual/12-glossary.md` **character for character** — flatten the file and `grep -F` each term you use before committing; a term split across a hard wrap defeats the check. `层级` is reserved for tier (`层级（1/2/3 级）`, individual tiers `N 级`, never `第 N 层级`); validity conditions are named, never numbered; planes are `断言平面` / `发布平面`.

- `01-capabilities.md`: a tenth capability entry with all five fields in order — **Does** · **Valid where** · **Backed by** · **Implemented in** · **Refuses**. The `Refuses` field is the point of the chapter and must be specific: a selection intersecting no AOI is refused by `deny-outside-aoi`; statistics are never merged across events; the answer speaks only for the matched tiles. Cite `src/geosteward/gateway/context.py` and `app/src/lib/area.js`.
- `07-gateway-and-agent.md`: the either-or request shape and where the area branch sits in the lifecycle — one paragraph in the existing lifecycle section, not a new heading.
- `08-app-pwa.md`: the draw tool, the selection header, and the highlight; add `bboxFromCorners` and `cellsInBox` to the exported-names material.

**A citation is a claim the reader can check the statement there** — open every file you cite and confirm it establishes what you wrote. Four chapters needed a fix round for terminology and one for a citation that did not back its sentence.

- [ ] **Step 4: Run every gate, then commit**

```bash
python -m unittest discover -s tests
python scripts/manual_anchors.py check docs README.md src/geosteward/live/__init__.py
python scripts/publication_boundary.py plan --check
cd app && npm test && cd ..
```

All four must pass. The anchor count will rise; report the new number.

```bash
git add app docs/manual
git commit -m "feat: highlight the tiles an area answer used, and document the capability"
```

---

## Self-Review

**Spec coverage.** §3.1 (coverage out of the claim plane) → Task 1's declared-unknown fact plus the global constraint forbidding a match key. §3.2 (enumerate grids) → Task 1 Step 3 and the subset property test. §3.3 (all intersecting events, no merged stats) → `locate_area` and the per-event loop. §3.4 (`cells` in the answer) → Task 2. §4 (request shape) → Tasks 2 and 3. §5 (evidence and coverage) → Task 1. §6 (answer contract and refusals) → Tasks 2 and 3; the `no_evidence` and `deny-outside-aoi` paths need no code because the existing branches already handle empty facts and `in_aoi: false`. §7 (UI) → Tasks 4 and 5. §8 (testing) → the tests in each task, with the subset property in Task 1. §11 (definition of done) → Task 5's gate run plus the manual updates.

**Placeholder scan.** No "TBD", no "add validation", no "similar to Task N". Task 4 Step 5 describes the draw interaction in prose rather than code because it is DOM event wiring against a live map instance, which cannot be written blind — the testable part was extracted into `area.js` with complete code, which is the point of splitting it out.

**Type consistency.** `bboxFromCorners` and `cellsInBox` are named identically in Task 4's tests, implementation, and Task 5's documentation step. `evidence_for_area`, `locate_area`, and `boxes_intersect` match across Tasks 1–3. The bbox key order `{min_lat, min_lon, max_lat, max_lon}` is the same in the Python tests, the JS library, and the Pydantic model.

**One thing the executor should expect to adjust.** The owner said details are open to change after the core works. The likeliest adjustments are the coverage fact's wording (Task 1) and the draw interaction's modifier key (Task 4 uses shift-drag). Neither changes an interface.
