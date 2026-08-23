# Bilingual Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `docs/manual/` — thirteen bilingual files that are the single authority on GeoSteward's architecture and mechanism — plus a CI-gated anchor checker, and retire the two documents that contradict the current architecture.

**Architecture:** One new script (`scripts/manual_anchors.py`) lands first so every subsequent file is gated as it is written. Then `12-glossary.md` fixes the Chinese terminology the other twelve files are bound by. Then the orientation files, then the mechanism chapters in policy order, then the reference and onboarding files. Retirement of `docs/architecture.md` and `docs/methodology.md` comes **last**, because their still-valid content must be absorbed into chapters `02` and `06` before they can be safely removed.

**Tech Stack:** Python 3.11 stdlib (`re`, `pathlib`, `argparse`), `unittest`, GitHub Actions, Markdown.

**Spec:** [`docs/design/specs/2026-08-23-bilingual-manual-design.md`](../specs/2026-08-23-bilingual-manual-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

- **Bilingual form:** English first; the Chinese restatement immediately after as a Markdown blockquote (`>`), at subsection granularity. Never parallel files.
- **The Chinese is a restatement, not a translation.** Where a Chinese reader needs US context the English does not spell out — what CAL FIRE DINS is, which agency publishes CDC SVI, what NIFC/WFIGS covers — the Chinese gains a clause. A literal translation is a defect.
- **Language-neutral content appears exactly once:** code blocks, command lines, path tables, field names, diagrams. Tables whose cells are prose get a Chinese counterpart table; tables of identifiers do not.
- **Terminology is bound by `docs/manual/12-glossary.md`.** First use of a glossary term in each file links to it. No file may coin a second Chinese rendering for a term the glossary fixes.
- **Every capability entry and module row carries at least one repo-relative path anchor**, written as an inline-code span or a Markdown link.
- **Numbers are read from artifacts or from a test run during writing** — never copied from `docs/STATUS.md` or `README.md`. If a figure appears in both and they disagree, that is a finding for `docs/STATUS.md`, not something to smooth over.
- **Nothing unimplemented is described in the present tense.** Absences belong in `11-limits-and-gaps.md` and in the `refuses` field of capability entries.
- **No patent intent and no claim-style language anywhere in the repository.** The disclosure memo is a separate out-of-repo document with its own spec.
- **Do not fix code defects discovered while writing.** File them in `docs/STATUS.md` under `Next` or `Known limitations`. Documentation work that quietly edits behaviour is unreviewable.
- **Every file must pass** `python scripts/manual_anchors.py check` before its task is committed.

### How to read the content tasks

Tasks 2–13 produce prose. For prose, "show the code" cannot mean pre-writing the paragraphs — the paragraphs are the deliverable. So each content task instead specifies, exactly: the **sources to read**, the **required section skeleton** (verbatim headings), the **facts the file must state**, the **anchors it must carry**, and the **questions the finished file must answer**. Content that meets that specification is complete; content that omits a required fact or heading is not. This is the honest analogue of a code contract for prose, and it is what makes each file independently reviewable.

> **中文。** 任务 2–13 产出散文。对散文而言，"展示代码"不可能意味着预先写好段落——段落本身就是交付物。
> 因此每个内容任务精确规定的是：**要读的源文件**、**必需的章节骨架**（标题逐字给出）、
> **文件必须陈述的事实**、**必须携带的路径锚点**、以及**成品必须能回答的问题**。
> 满足这个规格的内容即为完成；漏掉任一必需事实或标题的则未完成。

---

### Task 1: `scripts/manual_anchors.py` and its CI gate

Lands before any manual content so every later file is gated as it is written.

**Files:**
- Create: `scripts/manual_anchors.py`
- Create: `tests/test_manual_anchors.py`
- Modify: `.github/workflows/test.yml` (add a step to the `unit-tests` job, after the existing `plan --check` step at the end of the job)

**Interfaces:**
- Produces, and later tasks rely on these names:
  - `extract_anchors(text: str, source: Path) -> list[Anchor]`
  - `Anchor` — a frozen dataclass with fields `raw: str`, `path: str`, `line_ref: str | None`, `source: Path`, `source_line: int`
  - `DECLARED_ABSENT: dict[str, str]` — path to the reason it is expected to be missing
  - `resolve(anchor: Anchor, repo_root: Path) -> bool` — true when the path exists **or** is declared absent
  - `stale_absences(repo_root: Path) -> list[str]` — declared-absent paths that now exist
  - `collect(roots: list[Path], repo_root: Path) -> list[Anchor]`
  - `main(argv: list[str]) -> int` — returns `0` when every anchor resolves and no absence is stale, `1` otherwise
- CLI: `python scripts/manual_anchors.py list [ROOT ...]` and `python scripts/manual_anchors.py check [ROOT ...]`, both defaulting to `ROOT = docs/manual` when no argument is given.

**What counts as an anchor.** A token is an anchor when it appears either inside an inline-code span (single backticks) or as a Markdown link target, and after stripping an optional trailing `:N` or `:N-M` line reference it:

1. contains `/`, and
2. contains no whitespace, and
3. begins with one of the repository's top-level directories: `app/`, `docs/`, `events/`, `gateway/`, `scripts/`, `src/`, `tests/`, `.github/`.

Rule 3 is what keeps `H3 r9`, `sha256`, `EPSG:4326`, and prose like `and/or` from being treated as paths. A trailing `/` means the anchor is a directory and is resolved as one.

**Templates and deliberately-absent paths.** Two kinds of cited path must not be treated as failures, and getting this wrong would make the gate actively harmful.

A token containing `<`, `>`, or `*` is a **template or glob**, not a path — `events/<event-id>/artifact_manifest.jsonl` describes a shape. Skip these entirely.

A small number of paths are cited **because they do not exist**, and that is the honest content. `events/live_evidence.jsonl` is the case that matters: Task 8 requires `05-verifiability-and-live.md` to state that the file does not exist outside tests, because no live API call has ever run. If the gate failed on that citation, the cheapest way for an implementer to make CI green would be to delete the sentence — and that sentence is the most honest one in the chapter. A gate that pressures someone into removing a true statement is worse than no gate.

So the script carries a `DECLARED_ABSENT` mapping from path to the reason it is expected to be missing, and **verifies the declaration in both directions**: a declared-absent path that is cited does not fail, but a declared-absent path that has come into existence **does** fail, with a message telling the reader to update the declaration. Otherwise the list itself rots — a stale exemption silently stops checking a path that is now real. This is the same shape as `artifact_classes` in `src/geosteward/harness/policy_v1.yaml`: declare the exceptions explicitly, then check the declaration.

Seed it with exactly one entry, and require a comment for any addition:

```python
DECLARED_ABSENT = {
    # No Google Maps Platform key exists, so neither live adapter has ever run.
    # The manual cites this path precisely to say the file is not there.
    # See docs/manual/05-verifiability-and-live.md.
    "events/live_evidence.jsonl": "no GMP key; both adapters are tested against a stub",
}
```

**Known misses, to be documented in the script's module docstring rather than fixed.** Bare (un-backticked) paths in prose are not extracted, because the false-positive rate over English text is not worth it. A path broken across two lines is not extracted — `src/geosteward/harness/policy_v1.yaml` line 115 wraps `docs/design/specs/` onto the next line and this script will not catch it. And an anchor that resolves says nothing about whether the behaviour behind it still matches the sentence citing it. Stating the limits is the point; a gate whose coverage is overstated is worse than one whose coverage is known.

**Not in scope for the gate:** `docs/design/plans/` and `docs/design/specs/`. Plans cite files they are about to create and specs cite paths as historical record — including, deliberately, `src/disasterpilot/sources/usgs.py` as an example of a path that must *not* resolve. Running the gate over design records would report dozens of correct citations as failures. Only pass it roots whose paths are meant to be live.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_manual_anchors.py
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import manual_anchors as ma

REPO = Path(__file__).resolve().parents[1]


class ExtractTests(unittest.TestCase):
    def test_backticked_path_is_an_anchor(self):
        anchors = ma.extract_anchors("see `src/geosteward/pipeline.py` for it", Path("x.md"))
        self.assertEqual([a.path for a in anchors], ["src/geosteward/pipeline.py"])

    def test_markdown_link_target_is_an_anchor(self):
        anchors = ma.extract_anchors("[the engine](src/geosteward/harness/policy.py)", Path("x.md"))
        self.assertEqual([a.path for a in anchors], ["src/geosteward/harness/policy.py"])

    def test_line_reference_is_stripped_and_preserved(self):
        (anchor,) = ma.extract_anchors("`src/geosteward/harness/policy.py:195`", Path("x.md"))
        self.assertEqual(anchor.path, "src/geosteward/harness/policy.py")
        self.assertEqual(anchor.line_ref, "195")

    def test_non_path_code_spans_are_not_anchors(self):
        text = "`H3 r9`, `sha256`, `EPSG:4326`, `and/or`, `resolution_cap`"
        self.assertEqual(ma.extract_anchors(text, Path("x.md")), [])

    def test_directory_anchor_keeps_trailing_slash(self):
        (anchor,) = ma.extract_anchors("`docs/incidents/`", Path("x.md"))
        self.assertEqual(anchor.path, "docs/incidents/")

    def test_source_line_is_recorded(self):
        (anchor,) = ma.extract_anchors("intro\nsee `scripts/run_watch.py`\n", Path("x.md"))
        self.assertEqual(anchor.source_line, 2)


class ResolveTests(unittest.TestCase):
    def test_existing_file_resolves(self):
        (anchor,) = ma.extract_anchors("`src/geosteward/pipeline.py`", Path("x.md"))
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_existing_directory_resolves(self):
        (anchor,) = ma.extract_anchors("`docs/incidents/`", Path("x.md"))
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_missing_file_does_not_resolve(self):
        (anchor,) = ma.extract_anchors("`src/disasterpilot/sources/usgs.py`", Path("x.md"))
        self.assertFalse(ma.resolve(anchor, REPO))


class TemplateAndAbsenceTests(unittest.TestCase):
    def test_template_tokens_are_not_anchors(self):
        text = "`events/<event-id>/artifact_manifest.jsonl` and `events/*/dossier/`"
        self.assertEqual(ma.extract_anchors(text, Path("x.md")), [])

    def test_declared_absent_path_resolves(self):
        # Cited in order to say it is not there; must not fail the gate.
        (anchor,) = ma.extract_anchors("`events/live_evidence.jsonl`", Path("x.md"))
        self.assertIn(anchor.path, ma.DECLARED_ABSENT)
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_declared_absent_path_that_now_exists_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "events").mkdir()
            (root / "events" / "live_evidence.jsonl").write_text("{}\n")
            stale = ma.stale_absences(root)
            self.assertIn("events/live_evidence.jsonl", stale)

    def test_no_stale_absences_in_this_repo(self):
        self.assertEqual(ma.stale_absences(REPO), [])


class CliTests(unittest.TestCase):
    def test_check_passes_on_the_repo_docs(self):
        self.assertEqual(ma.main(["check", "docs"]), 0)

    def test_check_fails_on_a_broken_anchor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "broken.md"
            bad.write_text("this cites `src/disasterpilot/sources/usgs.py`\n")
            self.assertEqual(ma.main(["check", str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_manual_anchors -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manual_anchors'`

- [ ] **Step 3: Implement the script**

Write `scripts/manual_anchors.py` satisfying the interface above. Required elements:

- A module docstring stating what the gate catches, the three known misses named above, and why `DECLARED_ABSENT` exists.
- `TOP_LEVEL = ("app/", "docs/", "events/", "gateway/", "scripts/", "src/", "tests/", ".github/")`
- `DECLARED_ABSENT` seeded exactly as shown above.
- Two extraction regexes: inline code spans (`` `([^`\n]+)` ``) and Markdown link targets (`\]\(([^)\s]+)\)`). Run both over each line, record the 1-based line number.
- A `_looks_like_path` predicate implementing rules 1–3, and rejecting any token containing `<`, `>`, or `*`.
- `_split_line_ref` stripping a trailing `:N` or `:N-M`.
- `stale_absences` returning every `DECLARED_ABSENT` key that now exists on disk. `main` runs this on `check` regardless of which roots were passed, and reports each as `declared absent but now exists: PATH — update DECLARED_ABSENT`.
- `collect` walks any directory root for `*.md`, and reads a file root directly whatever its extension — so CI can point it at `README.md` and at source files that cite docs.
- `main` prints, for `check`, one line per unresolved anchor in the form `path/to/source.md:LINE  unresolved: cited/path` and a final count; returns `1` if any. For `list`, prints every anchor found with its source and line, and returns `0`.
- Anchors are deduplicated per `(source, source_line, path)` so a path cited twice on one line is reported once.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_manual_anchors -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Run the gate over the repository as it stands**

Run: `python scripts/manual_anchors.py check docs README.md src/geosteward/live/__init__.py`
Expected: exit 0. `docs/manual/` does not exist yet, which is not an error — an absent root contributes no anchors.

If this reports unresolved anchors in existing docs, that is a real finding: fix the cited paths in those documents and note the fix in the commit message. Do not weaken the predicate to make the gate pass.

- [ ] **Step 6: Wire the gate into CI**

In `.github/workflows/test.yml`, append to the `unit-tests` job:

```yaml
      - name: Documentation path anchors resolve
        # The failure this catches is docs/architecture.md pointing at
        # src/disasterpilot/ for four days after the package was renamed: a
        # path asserted in prose with nothing to check it. Scope includes the
        # source files that cite documentation paths, because two of those
        # went stale in the 2026-08-23 folder move.
        run: >-
          python scripts/manual_anchors.py check
          docs README.md src/geosteward/live/__init__.py
```

- [ ] **Step 7: Full suite, then commit**

Run: `python -m unittest discover -s tests`
Expected: PASS — 212 existing tests plus 15 new ones. Record the actual total; it is the number `10-getting-started.md` will cite in Task 13.

```bash
git add scripts/manual_anchors.py tests/test_manual_anchors.py .github/workflows/test.yml
git commit -m "feat: path anchors in documentation are checkable, and checked in CI"
```

---

### Task 2: `docs/manual/12-glossary.md`

Written second because the other twelve files are bound by it. Numbered `12` for reading order; built first for dependency order.

**Files:**
- Create: `docs/manual/12-glossary.md`

**Interfaces:**
- Produces: the single Chinese rendering for every term below. Tasks 3–13 must use these exact renderings and must link to this file on first use of a term.

**Sources to read:** `src/geosteward/harness/policy_v1.yaml` (the two planes, the three artifact attributes, `verifiability`), `src/geosteward/harness/checks/outcome.py`, `src/geosteward/live/base.py`, `README.md` (the validity table), `docs/incidents/2026-08-20-publication-boundary.md`.

**Required structure.** A single table, alphabetical by English term, with four columns: `Term` · `中文` · `What it is (one line)` · `Specified in`. The fourth column is an anchor, which is what puts this file under the Task 1 gate.

**Required entries — all eighteen, none omitted:**

AOI · artifact ID · artifact manifest · audit log · CAL FIRE DINS · CDC SVI · claim plane · declared unknowns · distribution plane · fail-closed · H3 r9 · NIFC/WFIGS · resolution cap · Steward Harness · tier (1/2/3) · validity (outcome / process / institutional) · verifiability (`retained` / `re-derivable` / `cited-only`) · weakest-link.

**Required facts:**
- `H3 r9` is stated with its approximate cell area (~0.1 km²), because that is what makes it the meaningful public evidence resolution rather than an arbitrary parameter.
- `CAL FIRE DINS` is expanded (Damage Inspection) and identified as a California state agency post-fire structure survey — the entry a Chinese reader most needs context for.
- `CDC SVI` is identified as the US Centers for Disease Control Social Vulnerability Index, 2022 vintage, tract-level.
- `NIFC/WFIGS` is identified as the US National Interagency Fire Center's Wildland Fire Interagency Geospatial Services feed.
- `verifiability` states the total order and the weakest-link rule, and states that it is **orthogonal to tier** — the distinction the rest of the manual depends on.
- `fail-closed` states what the system does instead of guessing: it refuses and records the reason.

**Questions the finished file must answer:** For any term used in chapters `01`–`11`, what does it mean in one line, what is its Chinese rendering, and which file in the repository specifies it?

- [ ] **Step 1: Read the five sources listed above**
- [ ] **Step 2: Write the file** to the required structure with all eighteen entries
- [ ] **Step 3: Verify the gate**

Run: `python scripts/manual_anchors.py check docs/manual`
Expected: exit 0.

- [ ] **Step 4: Verify entry completeness**

Run: `grep -c '^| ' docs/manual/12-glossary.md`
Expected: 19 or more — eighteen entries plus the header row.

- [ ] **Step 5: Commit**

```bash
git add docs/manual/12-glossary.md
git commit -m "docs(manual): bilingual glossary, binding on the rest of the manual"
```

---

### Task 3: `docs/manual/README.md`

**Files:**
- Create: `docs/manual/README.md`

**Interfaces:**
- Consumes: the Chinese renderings fixed in Task 2.
- Produces: the file list and the three reading paths that Tasks 4–13 slot into. Every chapter filename below is final; later tasks must not rename.

**Sources to read:** `README.md`, `docs/STATUS.md`, `docs/design/specs/2026-08-23-bilingual-manual-design.md` §2 and §4.

**Required structure — these headings, verbatim:**

```
# GeoSteward Manual · 使用与机制说明书
## The one-minute version
## Which parts to read
## The thirteen files
## What this manual is not
```

**Required facts:**
- The one-minute version states, in under 200 words per language: what GeoSteward is, that hazard monitoring is nationwide while exposure and damage analysis exist only inside three deep-case AOIs, and that the distinguishing property is enforced refusal rather than breadth.
- `## Which parts to read` gives the three paths from spec §4: maintainer/handover (`10` → `09` → `02`–`05`); Chinese-speaking colleague or student (`README` → `01` → `06` → `10`, with `12` alongside); mechanism study (`02` → `03` → `04` → `05` → `07`).
- `## The thirteen files` is a table of filename → one-line subject, every file anchored.
- `## What this manual is not` states the division of labour from spec §8: `README.md` is the entry point, `docs/STATUS.md` is the dated ledger, `docs/design/specs/` holds decision records, `docs/track_a_alignment.md` maps to the venue brief. It states that when the manual and `STATUS.md` disagree about a fact, the artifacts decide.

**Questions the finished file must answer:** Where do I start given who I am? What is in each of the thirteen files? If I want current status rather than mechanism, where do I go instead?

- [ ] **Step 1: Read the three sources**
- [ ] **Step 2: Write the file** to the verbatim skeleton
- [ ] **Step 3: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0. Chapter files that do not exist yet must **not** be anchored as paths in this task; list them as plain names in the table and convert them to links in Task 14.
- [ ] **Step 4: Commit**

```bash
git add docs/manual/README.md
git commit -m "docs(manual): index, one-minute version, and three reading paths"
```

---

### Task 4: `docs/manual/01-capabilities.md`

The file that answers the question that prompted this work.

**Files:**
- Create: `docs/manual/01-capabilities.md`

**Interfaces:**
- Consumes: glossary renderings (Task 2).
- Produces: the capability names that `08-app-pwa.md` (Task 11) and `11-limits-and-gaps.md` (Task 13) refer back to.

**Sources to read:** `README.md` (the works/does-not table), `src/geosteward/harness/policy_v1.yaml`, `app/src/lib/views.js`, `app/src/App.jsx`, `docs/STATUS.md`, and the three `events/*/dossier/event_record.json` files.

**Required structure.** One `###` section per capability. Every section carries these five fields as a definition list or short table, in this order, with these labels:

```
**Does** · **Valid where** · **Backed by** · **Implemented in** · **Refuses**
```

**The `Refuses` field is mandatory and may not be empty.** The system's distinguishing property is that each capability has an articulated refusal boundary; a catalogue of capabilities alone would read as a stronger claim than the system makes. If a capability appears to refuse nothing, that is a finding to record, not a field to drop.

**Required capabilities — all nine:**

1. **Nationwide Tier-1 hazard watch** — four sources, hourly, per-source failure declared. Anchors: `src/geosteward/sources/usgs.py`, `src/geosteward/sources/nws.py`, `src/geosteward/sources/nhc.py`, `src/geosteward/sources/nifc.py`, `scripts/run_watch.py`. Refuses: any damage or exposure conclusion from watch data — state the declared-unknown string that carries this.
2. **Three deep cases** — Eaton Fire 2025, Hurricane Milton 2024, Hurricane Ian 2022. Anchors: `events/eaton-2025/`, `events/milton-2024/`, `events/ian-2022/`, `scripts/build_eaton_case.py`, `scripts/build_milton_case.py`, `scripts/build_ian_case.py`. Refuses: analysis outside the three AOIs.
3. **Resident mode** — address to plain-language dossier. Anchor: `app/src/components/ResidentPanel.jsx`, `app/src/lib/coverage.js`. Refuses: damage assessment for residents (`deny-resident-damage-assessment`), and confident negatives for addresses it could not evaluate — the `unknown` coverage state.
4. **Planner mode with the trade-off slider** — damage against social vulnerability, recomputed client-side. Anchors: `app/src/components/PlannerPanel.jsx`, `app/src/lib/data.js`. Refuses: parcel-level output at any weighting (`deny-parcel-any-role`).
5. **Validity badges** — check counts read from committed audit logs, latest run only. Anchors: `app/src/components/Badges.jsx`, `app/src/lib/data.js`. Refuses: summing checks across runs — say what the pre-2026-08-20 behaviour was and why it was wrong.
6. **Lineage viewer** — manifest rows with agents, hashes, inputs. Anchor: `app/src/components/LineagePanel.jsx`. Refuses: showing full workstation paths — published manifests redact to `<workstation>`, sha256 remains the anchor.
7. **The agent chat loop** — four response types. Anchors: `src/geosteward/gateway/steward.py`, `app/src/components/ChatPanel.jsx`. Refuses: uncited factual sentences, fabricated artifact IDs, and answers that cite a live lookup without also citing a retained artifact.
8. **The publication boundary** — what a build may serve. Anchors: `scripts/publication_boundary.py`, `src/geosteward/harness/distribution.py`. Refuses: publishing parcel-resolution, internal-audience, lineage-audience, or third-party-restricted artifacts.
9. **Offline and installable operation** — keyless basemap, cached artifacts. Anchors: `app/vite.config.js`, `app/src/lib/data.js`. Refuses: nothing at runtime, but state the deliberate cost — no keyed basemap, by design, because keyless operation is a property the project claims.

**Required facts:**
- Every count cited (features per grid, sources, tests) is read from the artifact, not from `README.md`. The grids and their sizes as of this writing: Eaton damage grid 265 cells, Eaton SVI context 265, Eaton cross-view coverage 109, Milton bi-temporal 15, Milton debris 5,618, Ian cross-view 190, Ian density 413. Verify each with `python3 -c "import json;print(len(json.load(open('PATH'))['features']))"` rather than trusting this list.
- The Milton attribution caveat is stated where the Milton case appears: post imagery is 2024-season cumulative (Debby + Helene + Milton), so damage is not attributable to Milton alone.
- The Ian density layer is stated as density-only — no per-point severity link exists, so no damage labels are claimed.

**Questions the finished file must answer:** What can this system do? For each thing, where does it work, what backs it, and what will it refuse to say?

- [ ] **Step 1: Read the sources listed above**
- [ ] **Step 2: Verify every count** you intend to cite, using the command shown, and record the values
- [ ] **Step 3: Write the file** — nine sections, five fields each, `Refuses` never empty
- [ ] **Step 4: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 5: Verify no capability lost its refusal field**

Run: `grep -c '\*\*Refuses\*\*' docs/manual/01-capabilities.md`
Expected: 9.

- [ ] **Step 6: Commit**

```bash
git add docs/manual/01-capabilities.md
git commit -m "docs(manual): capability catalogue, each entry with its refusal boundary"
```

---

### Task 5: `docs/manual/02-harness-outcome-audit.md`

**Files:**
- Create: `docs/manual/02-harness-outcome-audit.md`

**Interfaces:**
- Consumes: glossary renderings.
- Produces: the description of the artifact contract that `06-data-and-evidence.md` (Task 9) builds on, and the run-grouping explanation `08-app-pwa.md` (Task 11) refers to.

**Sources to read:** `src/geosteward/harness/checks/outcome.py`, `src/geosteward/harness/audit.py`, `src/geosteward/pipeline.py`, `docs/architecture.md` (for the artifact-contract section being absorbed — read it before Task 14 deletes it), and any `events/*/audit_log.jsonl`.

**Required structure — these headings, verbatim:**

```
# 02 · Outcome validity and the provenance record
## The four outcome checks
## The artifact contract
## The audit log is append-only
## Recovering runs from structure, not timestamps
## A real fail-closed catch, preserved
```

**Required facts:**
- The four checks by their real names and signatures: `check_crs(declared, expected="EPSG:4326")`, `check_join_integrity(...)`, `check_bounds(name, value, minimum, maximum)`, `check_uncertainty_present(payload, field="uncertainty")`, each returning a `CheckResult`. Anchor `src/geosteward/harness/checks/outcome.py`.
- The artifact contract, absorbed from `docs/architecture.md`: artifacts live under `events/<event-id>/<stage>/`; each carries agent name, UTC timestamp, and input artifact names in `events/<event-id>/artifact_manifest.jsonl`; snapshots are append-only so a rerun adds a new timestamped file rather than replacing one; agents lacking inputs fail closed with a recorded reason instead of being skipped silently.
- `sha256_file` and `new_run_id` from `src/geosteward/harness/audit.py`, and that `AuditLog.record` stamps `run_id` for new logs.
- **Why run recovery reads structural markers rather than timestamps.** A `stage` row closes a run; a check repeating the run's *first* check name means the sequence restarted, which is what an aborted run leaves behind. Timestamps provably fail here, and the manual must give both halves of the proof: Eaton's aborted run is two minutes before its re-run, while Ian's `svi_sample_density` writes one sequence *across* a second boundary. Logs written before `run_id` existed are grouped by the reader; they are never rewritten.
- The preserved catch: an over-strict join assertion (envelope tracts versus burn tracts) was rejected by the harness during the Eaton SVI build and corrected. It remains in the audit log. State where to find it.
- `check_uncertainty_present` currently passes on a `None` value — a known carry-forward item. State it here as a limitation, and cross-reference `11-limits-and-gaps.md`.

**Questions the finished file must answer:** What does the harness check before an artifact is accepted? What is recorded about every artifact? Why can't I just group audit rows by timestamp? Where can I see the harness having actually rejected something?

- [ ] **Step 1: Read the five sources**, including `docs/architecture.md` before it is deleted
- [ ] **Step 2: Locate the preserved fail-closed catch** in `events/eaton-2025/audit_log.jsonl` and note the row so the file can point at it
- [ ] **Step 3: Write the file** to the verbatim skeleton
- [ ] **Step 4: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 5: Commit**

```bash
git add docs/manual/02-harness-outcome-audit.md
git commit -m "docs(manual): outcome checks, the artifact contract, and the audit record"
```

---

### Task 6: `docs/manual/03-policy-claim-plane.md`

**Files:**
- Create: `docs/manual/03-policy-claim-plane.md`

**Sources to read:** `src/geosteward/harness/policy.py`, `src/geosteward/harness/policy_v1.yaml` (the `rules:` section), `src/geosteward/gateway/steward.py`, `tests/test_policy_v1_matrix.py`.

**Required structure — these headings, verbatim:**

```
# 03 · The claim plane — what the agent may assert
## Ordered rules, first match wins, default deny
## Validation happens at load, not at evaluation
## Classification is deterministic; the model does not choose its own authorization
## The rules, one at a time
## The claim post-check
```

**Required facts:**
- `PolicyEngine.from_yaml`, `PolicyEngine.evaluate(request: PolicyRequest) -> PolicyDecision`, and `default_deny`. Anchor `src/geosteward/harness/policy.py`.
- Construction-time validation via `validate_rules` and `_validate_verifiability_values`: an unknown match key or a malformed rule fails loudly at load. State the reason plainly — a typo in a *deny* rule's match key would make the rule match nothing, so a silent load is a silent widening of authorization.
- Each of the seven claim rules by ID, with the question it answers: `deny-outside-aoi`, `deny-parcel-any-role`, `deny-resident-damage-assessment`, `deny-damage-assessment-without-retained-evidence`, `allow-watch-anywhere`, `allow-exposure-in-aoi`, `allow-planner-damage-tier3`, `allow-facility-context-re-derivable`. (That is eight; the manual lists all eight.)
- What the allow rules deliberately do **not** permit: `cited-only` matches no allow rule and falls through to `default-deny`, so the fail-closed default carries the non-deterministic regime without a rule being written for it.
- `classify(question) -> tuple[str, str]` in `src/geosteward/gateway/steward.py` is deterministic Python, not an LLM call.
- The claim post-check via `check_claims`: citation-by-default with a **closed** exemption set — question, imperative advice, declared limit — implemented as `is_non_assertive`. State the inversion history: it previously required citations only on sentences containing a digit, so *"Your neighborhood was not significantly affected."* passed uncited. Acceptance over thirteen representative drafts moved 9/13 → 7/13, closing three uncited assertions and fixing one false positive. A lower acceptance number is the improvement.
- The matrix test exists and checks the policy cell by cell. Anchor `tests/test_policy_v1_matrix.py`.

**Questions the finished file must answer:** How is a request authorized? What happens to a request no rule matches? Who decides the purpose and resolution of a question — the model or the code? Why is a sentence without a digit still required to carry a citation?

- [ ] **Step 1: Read the four sources**
- [ ] **Step 2: Write the file** to the verbatim skeleton, all eight rules covered
- [ ] **Step 3: Verify rule coverage**

Run: `for id in deny-outside-aoi deny-parcel-any-role deny-resident-damage-assessment deny-damage-assessment-without-retained-evidence allow-watch-anywhere allow-exposure-in-aoi allow-planner-damage-tier3 allow-facility-context-re-derivable; do grep -q "$id" docs/manual/03-policy-claim-plane.md || echo "MISSING: $id"; done`
Expected: no output.

- [ ] **Step 4: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 5: Commit**

```bash
git add docs/manual/03-policy-claim-plane.md
git commit -m "docs(manual): the claim plane, rule by rule"
```

---

### Task 7: `docs/manual/04-policy-distribution-plane.md`

Separate from Task 6 on purpose. Merging the two planes into one chapter would reproduce, in the documentation, the conflation that caused the 2026-08-20 incident.

**Files:**
- Create: `docs/manual/04-policy-distribution-plane.md`

**Sources to read:** `src/geosteward/harness/distribution.py`, `src/geosteward/harness/publication.py`, `scripts/publication_boundary.py`, `src/geosteward/harness/policy_v1.yaml` (`published_events`, `artifact_classes`, `distribution`), `docs/incidents/2026-08-20-publication-boundary.md`, `.github/workflows/test.yml`, `.github/workflows/pages.yml`.

**Required structure — these headings, verbatim:**

```
# 04 · The distribution plane — what a build may publish
## Why a second plane exists
## Three attributes per artifact class
## The rules, one at a time
## Two independent defences
## The CI gates
## Ordering must be a function of the policy
```

**Required facts:**
- The claim plane governs what the agent *asserts*; nothing asserted the parcel file, so it satisfied every claim rule while being copied to the public site by the build. Summarise and link `docs/incidents/2026-08-20-publication-boundary.md` rather than re-narrating it. Public surface went from 30 files to 16.
- The three attributes with their meanings from the YAML comments: `resolution_cap` (finest geography the artifact can support a statement about), `audience` (`public` ships, `lineage` is reachable by hash not URL, `internal` supports reproduction on the maintainer's workstation), `license` (whether the content is ours to redistribute).
- **Why `license` is separate from the other two.** The first two record what this project judges safe to serve; a third party's terms are not ours to judge. State that `damage_points_restricted` is `license: public-domain-source` but `resolution_cap: parcel` — the disclosure judgment and the licence judgment are independent, and neither excuses the other.
- Value-set validation at load, with the concrete reason: `third-party-restrcited` — a typo — would match no deny rule and the file would publish.
- Every artifact class in the table, grouped as the YAML groups them: tile products, accountability records, the live lookup record, the restricted parcel source, the internal snapshots. A kind absent from the table is denied publication, and that is the point.
- The six distribution rules by ID: `deny-publish-third-party-restricted`, `deny-publish-parcel-resolution`, `deny-publish-internal-audience`, `deny-publish-lineage-audience`, `allow-publish-tile-products`, `allow-publish-event-accountability-records`.
- **Two independent defences:** `deny-publish-third-party-restricted` denies a *classified* artifact; `verify_site`'s set difference over the assembled tree denies an *unrecognised* file. Name both functions: `plan_publication` and `verify_site` in `src/geosteward/harness/publication.py`.
- The three CLI modes and where each runs: `plan`, `plan --check` (in the `unit-tests` job), `verify app/dist` (in the `app-build` job). Anchor `.github/workflows/test.yml`.
- The 2026-08-21 ordering fix: `plan_publication` sorted `Path` objects, and `PurePath` ordering case-folds on Windows but not on POSIX, so two registry profiles differing only in case swapped places between the maintainer's workstation and CI. Ordering is now by POSIX relative path string via `_sort_key`. State the reason it mattered: a gate that fails for cosmetic reasons is a gate people learn to override.
- `redact` replaces absolute workstation paths with `<workstation>` in published manifests; the repository copy keeps full lineage and sha256 remains the verifiable anchor.

**Questions the finished file must answer:** Why wasn't the claim plane enough? What decides whether a file ships? What stops a brand-new artifact kind from silently widening the public surface? Why does the allowlist have to be byte-identical between my laptop and CI?

- [ ] **Step 1: Read the seven sources**
- [ ] **Step 2: Run `python scripts/publication_boundary.py plan`** and read its output, so the chapter describes real behaviour rather than the code's intent
- [ ] **Step 3: Write the file** to the verbatim skeleton
- [ ] **Step 4: Verify rule coverage**

Run: `for id in deny-publish-third-party-restricted deny-publish-parcel-resolution deny-publish-internal-audience deny-publish-lineage-audience allow-publish-tile-products allow-publish-event-accountability-records; do grep -q "$id" docs/manual/04-policy-distribution-plane.md || echo "MISSING: $id"; done`
Expected: no output.

- [ ] **Step 5: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 6: Commit**

```bash
git add docs/manual/04-policy-distribution-plane.md
git commit -m "docs(manual): the distribution plane and the two defences behind it"
```

---

### Task 8: `docs/manual/05-verifiability-and-live.md`

**Files:**
- Create: `docs/manual/05-verifiability-and-live.md`

**Sources to read:** `src/geosteward/live/base.py`, `src/geosteward/live/record.py`, `src/geosteward/live/places.py`, `src/geosteward/live/grounded.py`, `src/geosteward/live/fake.py`, `tests/test_live_record.py`, `tests/test_live_adapters.py`, `docs/design/specs/2026-08-20-non-retainable-evidence-design.md`.

**Required structure — these headings, verbatim:**

```
# 05 · Verifiability — accountability without retention
## The problem: forbidden to keep the evidence
## A third axis, orthogonal to tier
## Two regimes, because re-derivation needs determinism
## The record is publishable because it is empty
## What is enforced, and by what test
## Never run against a live API
```

**Required facts:**
- The problem in one sentence: Google Maps Platform terms forbid retaining Maps Content, while GeoSteward proves traceability by hashing and freezing every input. Structurally incompatible, which is what makes it a research question rather than an integration chore.
- `verifiability_rank` and `weakest` in `src/geosteward/harness/policy.py`: `retained` > `re-derivable` > `cited-only`, totally ordered, weakest-link semantics. Orthogonal to tier — a Places fact can be current and accurate and still uncheckable without a key.
- Regime 1, structured APIs: re-derivable via request plus response sha256 (`response_digest` in `src/geosteward/live/base.py`); drift is reported as drift, not failure (`compare_digests` in `src/geosteward/live/record.py`).
- Regime 2, grounded generation: not reproducible even at temperature 0, so hashing prose would look like an anchor and hold nothing. `GroundedResult` therefore has **no digest field** — state this as a deliberate absence. The accountable unit becomes the citation, not the content, and such answers fall through to `default-deny`.
- The core result: `events/live_evidence.jsonl` holds the request (entirely ours — we chose the cell, the radius, the field mask), a response sha256, a count, and the source's own licence and retention declarations. A reader with their own key replays the request and compares digests.
- Place IDs are deliberately absent (owner ruling, spec §11.2). `LiveResult.reference_ids` carries them for the project's own joins; `record.py` never names the field, and a test asserts no reference id reaches the written row.
- `build_payload` builds from a named key list and asserts against it on every write, raising `RecordShapeError`; the request must name an `h3_cell`, because a record classified at tile resolution cannot carry a point.
- The containment property test: a fake source is seeded with content of exactly the kinds the licence forbids warehousing, the recorder is driven for real, and the bytes on disk are searched for every one of those strings. State why it exists in this form — after the publication-boundary incident, "the record cannot contain restricted content" was not left as an intention.
- The model is given counts, not names (`hospital=1, fire_station=1 within 1200 m`), because retention and onward disclosure are different questions and a hosted model endpoint is onward disclosure.
- **The load-bearing limitation, stated plainly:** neither adapter has ever run against a live API. There is no GMP key, both are tested against an in-process stub, and `events/live_evidence.jsonl` does not exist outside tests. This establishes the behaviour of this code and nothing about Google's.

**Questions the finished file must answer:** If I am not allowed to keep the evidence, what makes a claim resting on it accountable? Why is a hash useless for the grounded case? What exactly is in the published record, and what is deliberately not? Has any of this run for real?

- [ ] **Step 1: Read the eight sources**
- [ ] **Step 2: Write the file** to the verbatim skeleton
- [ ] **Step 3: Verify the limitation is present and unhedged**

Run: `grep -n "never run\|no GMP key\|does not exist outside tests" docs/manual/05-verifiability-and-live.md`
Expected: at least one match. A chapter describing this mechanism without stating that it has never executed against Google would be the exact failure this manual exists to prevent.

- [ ] **Step 4: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 5: Commit**

```bash
git add docs/manual/05-verifiability-and-live.md
git commit -m "docs(manual): the verifiability axis and the content-free lookup record"
```

---

### Task 9: `docs/manual/06-data-and-evidence.md`

The longest chapter. Absorbs the surviving content of `docs/methodology.md` before Task 14 archives it.

**Files:**
- Create: `docs/manual/06-data-and-evidence.md`

**Sources to read:** all four `src/geosteward/sources/*.py` connectors plus `src/geosteward/sources/watchbase.py`, `src/geosteward/watch.py`, the three `scripts/build_*_case.py`, all three `events/*/dossier/event_record.json`, every `events/*/*/*.geojson`, `events/*/snapshots/registry/*.json`, and `docs/methodology.md`.

**Required structure — these headings, verbatim:**

```
# 06 · Data and evidence
## Tier 1 — the nationwide watch
## Tier 2 and 3 — the three deep cases
### Eaton Fire, 2025
### Hurricane Milton, 2024
### Hurricane Ian, 2022
## The methodological lineage
## The dataset registry, and what cannot be rebuilt
## Sources that were excluded, and why
```

**Required facts:**
- The four connectors, each with its failure mode: NWS is paginated and fails closed on page-cap overflow; NIFC fails closed on ArcGIS error envelopes rather than reporting zero hazards. State why that distinction matters — an error reported as zero is a false all-clear.
- `watch_status.json` declares per-source health and the features it could not map. Give a real reading: at 2026-08-23T15:42Z, usgs 298 / nws 19 with 198 skipped / nhc 3 / nifc 571, all four ok. Re-read the current file rather than copying these numbers.
- For each deep case: the AOI, the inputs, and **every property name** in each output grid with what it means. The grids and their real property sets, to be re-verified before writing:
  - `events/eaton-2025/exposure/dins_h3_r9_damage_grid.geojson` — `h3_cell`, `n_structures`, `n_none`, `n_minor`, `n_moderate`, `n_severe`, `n_destroyed`, `n_unknown`, `destroyed_rate`, `uncertainty`
  - `events/eaton-2025/exposure/svi_h3_r9_context.geojson` — adds `tract_geoid`, `RPL_THEMES`, `RPL_THEME1`–`RPL_THEME4`
  - `events/eaton-2025/evidence/crossview_h3_r9_coverage.geojson` — `h3_cell`, `labels`, `match_quality`, `n_matched_samples`, `uncertainty`
  - `events/milton-2024/evidence/bitemporal_h3_r9_grid.geojson` — `h3_cell`, `labels`, `n_samples`, `uncertainty`
  - `events/milton-2024/exposure/debris_h3_r9_grid.geojson` — `VolCD`, `VolVG`, `VolCD_sum`, `VolVG_sum`, `VolBoth_sum`, `windgust_M`, `rainfall_M`, `dist_htrack_M`, `h3_cell`, `uncertainty`
  - `events/ian-2022/evidence/crossview_h3_r9_grid.geojson` and `events/ian-2022/evidence/svi_density_h3_r9_grid.geojson` — `h3_cell`, `labels`, `n_samples`, `uncertainty`
- The `uncertainty` field is present on **every** feature of every grid, because `check_uncertainty_present` requires it. Say what each grid puts in it.
- Declared unknowns per case, read from `event_record.json`. The Milton record additionally has `excluded_sources`.
- The Milton attribution caveat, declared per feature: post imagery is 2024-season cumulative (Debby + Helene + Milton).
- The Eaton `damaged_repairable` class has n=30 and is declared as lacking statistical power rather than hidden.
- The Ian density layer is density-only: 4,121 CVIAN street-view positions to 413 cells, no verifiable per-point severity link, so no damage labels are claimed. Candour over coverage.
- **The methodological lineage, absorbed from `docs/methodology.md`:** views treated as witnesses with different competence (overhead attests roof and inundation extent, street-level attests facade and water-line damage); a reliability gate arbitrates per sample instead of symmetric fusion; where neither view can attest, the output is an explicit abstain plus acquire/inspect flag rather than a forced label; spatially blocked splits for anything fitted; disagreement between views reported as its own layer. Also absorb the honesty rules: forecast-conditioned and observed products never mixed in one table; unknowns declared in every decision product; no damage estimate without imagery.
- The dataset registry: SHA-256 checksums for 134,272 files (~33 GB) on the maintainer's workstation, with profiles frozen under each event's `snapshots/registry/`. **`events/` cannot be regenerated by a third party** — the builders read a private corpus. What a reviewer can verify is the committed artifacts, their hashes, and their audit logs.
- Exclusions with evidence: GenDisasterSVI street imagery is excluded because `dataset.csv` source paths reference `experiment2_ip2p` (InstructPix2Pix), confirming model generation; its 2,555 `post_sat` satellite images were confirmed as real acquisitions by the owner on 2026-08-20 and are usable. The exclusion is auditable — the registry profile (`generated_excluded`) is frozen into the event's snapshots.

**Questions the finished file must answer:** Where does each number on the map come from? What does each field in each grid mean? What was deliberately left out and how would I check that? Could I rebuild this from a fresh clone?

- [ ] **Step 1: Read the sources**, including `docs/methodology.md` before Task 14 archives it
- [ ] **Step 2: Re-verify every grid's property set and feature count**

Run:
```bash
python3 - <<'PY'
import json, pathlib
for p in sorted(pathlib.Path('events').glob('*/*/*.geojson')):
    d = json.load(open(p)); f = d.get('features') or []
    print(p, len(f)); print("  ", sorted(f[0]['properties'])) if f else None
PY
```

- [ ] **Step 3: Re-read the current `watch_status.json`** from the `live-data` branch or `live/products/` and use its actual figures
- [ ] **Step 4: Write the file** to the verbatim skeleton
- [ ] **Step 5: Verify every grid is documented**

Run: `for f in $(python3 -c "import pathlib;[print(p) for p in sorted(pathlib.Path('events').glob('*/*/*.geojson'))]"); do grep -q "$(basename $f)" docs/manual/06-data-and-evidence.md || echo "MISSING: $f"; done`
Expected: no output.

- [ ] **Step 6: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 7: Commit**

```bash
git add docs/manual/06-data-and-evidence.md
git commit -m "docs(manual): every data source and grid field, and what was excluded"
```

---

### Task 10: `docs/manual/07-gateway-and-agent.md`

**Files:**
- Create: `docs/manual/07-gateway-and-agent.md`

**Sources to read:** `src/geosteward/gateway/steward.py`, `src/geosteward/gateway/llm.py`, `src/geosteward/gateway/context.py`, `gateway/main.py`, `scripts/ask_steward.py`, `tests/test_gateway_steward.py`, `tests/test_gateway_live.py`.

**Required structure — these headings, verbatim:**

```
# 07 · The agent, and the harness around it
## The request lifecycle
## The model never decides its own authorization
## The four response types
## Provider-agnostic by construction
## The adversarial test suite
## Not safe to host yet
```

**Required facts:**
- The lifecycle in order: `classify` → policy pre-check → evidence retrieval from manifest-listed artifacts only, each fact tagged with its sha256-derived artifact ID → generation → `check_claims` post-check → audit. Up to three attempts, then a fail-closed refusal.
- Citation forms: `[artifact:HASH12]` and `[live:HASH12]`, matched by `_CITATION` and `_LIVE_CITATION`. An answer citing a live lookup must also cite an artifact — "cited-only cannot stand alone", made computable.
- The four response types the app must render: cited answer, rule-ID refusal, declared no-evidence, declared outage.
- Policy decides **before** anything is fetched, so an unauthorized question never reaches a third party — no billing surface, no disclosure. A source configured without a recorder is refused outright.
- `src/geosteward/gateway/llm.py` is stdlib-only and OpenAI-compatible; local Ollama with `gpt-oss:20b` is the default and any hosted provider is a change to `STEWARD_LLM_BASE_URL` / `_MODEL` / `_API_KEY`. Verified on the owner's RTX 3090 at roughly 154 tok/s. No Gemini key is required for development or adversarial evaluation.
- The adversarial suite covers out-of-AOI, fabricated citations, uncited numerics, parcel elicitation, LLM outage, retry repair, and audit completeness. State the count by running the file, not by copying it.
- **Not safe to host:** `gateway/main.py` defaults CORS to `*`, and `steward.py` records exact lat/lon and the verbatim question. Origin allowlist, rate limiting, and log redaction must land before any public deployment. This is also on the critical path for any keyed third-party API.

**Questions the finished file must answer:** What happens between my question and the answer? What stops the model from authorizing itself? What are the ways it can refuse? Can I put this on the internet today?

- [ ] **Step 1: Read the seven sources**
- [ ] **Step 2: Count the adversarial tests**

Run: `python -m unittest tests.test_gateway_steward -v 2>&1 | tail -3`
Record the actual count.

- [ ] **Step 3: Write the file** to the verbatim skeleton
- [ ] **Step 4: Verify the hosting warning is present**

Run: `grep -n "CORS\|rate limit\|redaction" docs/manual/07-gateway-and-agent.md`
Expected: at least one match.

- [ ] **Step 5: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 6: Commit**

```bash
git add docs/manual/07-gateway-and-agent.md
git commit -m "docs(manual): the agent request lifecycle and its adversarial tests"
```

---

### Task 11: `docs/manual/08-app-pwa.md`

**Files:**
- Create: `docs/manual/08-app-pwa.md`

**Sources to read:** `app/src/App.jsx`, all six files in `app/src/components/`, all five non-test files in `app/src/lib/`, `app/scripts/sync-artifacts.mjs`, `app/vite.config.js`.

**Required structure — these headings, verbatim:**

```
# 08 · The front end
## Two modes, one map
## The layer catalogue
## Coverage has three states, not two
## The watch badge reports what it dropped
## Validity badges and the lineage panel
## Citations, and how a live chip differs
## Artifacts are vendored at build time
```

**Required facts:**
- The exported functions by their real names: `buildCoverageIndex`, `lookupCoverage`, `eventsOf`, `mergedProps` in `app/src/lib/coverage.js`; `watchSummary` in `app/src/lib/watch.js`; `parseCitations`, `verifiabilityLabel` in `app/src/lib/citations.js`; `stageValidity`, `artifactLineage`, `priorityScores`, `topCells`, `geocodeAddress` in `app/src/lib/data.js`; `EVENTS`, `VIEWS`, `RAMP` in `app/src/lib/views.js`.
- **Why coverage has three states.** `covered` / `not_covered` / `unknown`. The third exists because an unreadable or unread layer previously produced a confident negative: 156 of Eaton's 265 evaluated tiles were told they were outside the evaluated areas, since `grids` was keyed by event and the narrowest layer won. Coverage is now a union index across layers.
- The watch badge reports mapped-of-total plus the declared unknowns, not just the mapped count. State the pre-fix behaviour: "918 active hazards" while `watch_status.json` declared 199 more it could not map.
- Validity badges read the committed audit logs and report the **latest** run, keeping superseded runs visible.
- A live chip is visually distinct and says "re-derivable, not retained"; the answer reports its own weakest-link verifiability; attribution comes from the gateway's field so the app cannot show content while forgetting the credit.
- Planner slider moves are audit-logged locally until the gateway ships, and the UI says so. They do not persist past the session.
- `sync-artifacts.mjs` vendors artifacts from `events/` at build time, so the app serves exactly the committed, hashed products. State the incident connection: this script previously copied whole directories, which is how the parcel file reached the site, and `published_events` moved out of it into `policy_v1.yaml` because a governance decision should not live as build-script trivia.
- Basemap is MapLibre GL with OpenFreeMap, keyless and offline-capable, and this is a deliberate non-goal for Google integration rather than an omission.
- The app test count, from running the suite.

**Questions the finished file must answer:** What are the two modes and what does each show? If my address returns nothing, does that mean I am safe? Why is the hazard count a fraction? How do I get from a map layer to the hash of the file behind it?

- [ ] **Step 1: Read the sources**
- [ ] **Step 2: Run the app suite and record the count**

Run: `cd app && npm ci && npm test 2>&1 | tail -5`

- [ ] **Step 3: Write the file** to the verbatim skeleton
- [ ] **Step 4: Verify the three coverage states are all named**

Run: `for s in covered not_covered unknown; do grep -q "$s" docs/manual/08-app-pwa.md || echo "MISSING: $s"; done`
Expected: no output.

- [ ] **Step 5: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 6: Commit**

```bash
git add docs/manual/08-app-pwa.md
git commit -m "docs(manual): the front end, and the three coverage states"
```

---

### Task 12: `docs/manual/09-module-reference.md`

**Files:**
- Create: `docs/manual/09-module-reference.md`

**Sources to read:** every file under `src/geosteward/`, `gateway/`, `scripts/`, and `app/src/`. Generate the list rather than typing it.

**Required structure — these headings, verbatim:**

```
# 09 · Module reference
## src/geosteward/harness/
## src/geosteward/sources/
## src/geosteward/deepcase/
## src/geosteward/live/
## src/geosteward/gateway/
## src/geosteward/agents/
## src/geosteward/ — top level
## gateway/
## scripts/
## app/src/
## Legacy, pending retirement
```

**Required facts:**
- One table row per file: path (anchored) · responsibility in one line · what it depends on · its tests.
- **`## src/geosteward/agents/` must explain why it exists and is not on the deep-case path.** `base.py`, `watcher.py`, `dossier.py`, `exposure.py`, `evidence.py`, `decision.py` are real and present, they were the organising structure of the pre-rework system, and the three deep cases are built by `scripts/build_*_case.py` without going through them. A reader who finds `agents/watcher.py` and assumes it is live would misread the whole system. This is the single most likely misreading in the repository, so it gets its own paragraph, not a footnote.
- **`## Legacy, pending retirement`** covers `src/geosteward/sources/zj_typhoon.py` and `src/geosteward/hazards/typhoon.py`. A typhoon API in a US-only system is confusing without explanation: they are pre-rework code kept until the pipeline agents are rewired, tracked in `docs/STATUS.md`.
- Generate the file list mechanically so nothing is missed.

**Questions the finished file must answer:** What is this file for? What calls it? What tests it? Why is there a typhoon module in a US-only system? Is `agents/` live?

- [ ] **Step 1: Generate the authoritative file list**

Run:
```bash
git ls-files src/geosteward gateway scripts app/src | grep -vE '\.test\.js$|__pycache__|\.css$' | sort
```

- [ ] **Step 2: Read each file's head** to state its responsibility accurately, not by guessing from its name
- [ ] **Step 3: Write the file** to the verbatim skeleton
- [ ] **Step 4: Verify no file was skipped**

Run:
```bash
for f in $(git ls-files src/geosteward gateway scripts app/src | grep -vE '\.test\.js$|__pycache__|\.css$|__init__.py'); do
  grep -q "$f" docs/manual/09-module-reference.md || echo "MISSING: $f"
done
```
Expected: no output.

- [ ] **Step 5: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 6: Commit**

```bash
git add docs/manual/09-module-reference.md
git commit -m "docs(manual): file-by-file module reference, including what is not live"
```

---

### Task 13: `docs/manual/10-getting-started.md` and `11-limits-and-gaps.md`

Two files, one task: the honest-limits file is the natural companion to the onboarding file, and a reviewer who accepts one would accept both.

**Files:**
- Create: `docs/manual/10-getting-started.md`
- Create: `docs/manual/11-limits-and-gaps.md`

**Sources to read:** `README.md` (quick start), `pyproject.toml`, `app/package.json`, `.github/workflows/test.yml`, `docs/STATUS.md` (`Next`, `Blocked`, `Known limitations`), and the limitation statements written in Tasks 5–11.

**Required structure for `10-getting-started.md` — verbatim:**

```
# 10 · Getting started
## Install
## Run the tests
## Run the app
## Run the agent gateway
## Rebuild a deep case — and why you probably cannot
## Check your own work
```

**Required facts for `10`:**
- Real commands, each executed before being written down: `python -m pip install -e ".[deepcase]"`, `python -m unittest discover -s tests`, `cd app && npm ci && npm test && npm run dev`, `ollama pull gpt-oss:20b`, `python -m pip install -e ".[deepcase,gateway]"`, `uvicorn gateway.main:app --port 8080`.
- The app works with no keys and no services because it serves committed artifacts.
- The rebuild section states plainly that the deep-case builders read a private ~33 GB corpus on the maintainer's workstation, so `events/` cannot be regenerated from a fresh clone. What a third party can verify is the committed artifacts, their hashes, and their audit logs.
- `## Check your own work` lists the gates a contributor should run before pushing: the Python suite, `npm test`, `python scripts/publication_boundary.py plan --check`, and `python scripts/manual_anchors.py check docs README.md src/geosteward/live/__init__.py`.
- Test counts from the actual runs in this task, not from `README.md`.

**Required structure for `11-limits-and-gaps.md` — verbatim:**

```
# 11 · Limits and gaps
## Where competence ends geographically
## Implemented but never executed
## Implemented but not safe to deploy
## Not implemented
## Known defects and rough edges
## Where to check whether this list is current
```

**Required facts for `11`:**
- Geographic: watch is nationwide; exposure, vulnerability and damage exist only inside the three AOIs; an address outside them is told so and an unresolvable address is told that instead of being guessed at.
- Never executed: both live adapters, for want of a GMP key; `events/live_evidence.jsonl` does not exist outside tests.
- Not safe to deploy: the gateway's CORS default, absent auth and rate limiting, and unredacted lat/lon and question text in the audit.
- Not implemented: citation click-through, persisted planner adjustments, budget-constrained inspection routing, PMTiles/vector tiles (the debris layer ships as a 5.8 MB GeoJSON), Playwright smoke tests, releases, CHANGELOG, `CITATION.cff`, contributor docs.
- Known defects: NWS zone/county alerts without polygon geometry are counted but not displayed; `check_uncertainty_present` passes on a `None` value; the legacy typhoon modules; run grouping for logs written before `run_id` existed is recovered by the reader and those logs are not rewritten.
- The last section points at `docs/STATUS.md` as the dated ledger and states that this chapter explains the limits while `STATUS.md` tracks their status — the division of labour from spec §8.

**Questions the finished two files must answer:** How do I get this running in ten minutes? What will I *not* be able to do from a fresh clone? What in here is real, what is scaffolding, and what is absent?

- [ ] **Step 1: Execute every command** in `10`'s Install / Run sections and record the real output
- [ ] **Step 2: Write `10-getting-started.md`**
- [ ] **Step 3: Write `11-limits-and-gaps.md`**, cross-checking against every limitation written in Tasks 5–11 so the two accounts agree
- [ ] **Step 4: Verify the gate** — `python scripts/manual_anchors.py check docs/manual`, expect exit 0
- [ ] **Step 5: Commit**

```bash
git add docs/manual/10-getting-started.md docs/manual/11-limits-and-gaps.md
git commit -m "docs(manual): getting started, and an honest inventory of the gaps"
```

---

### Task 14: Retire the contradicting documents and close the loop

Last, because Tasks 5 and 9 must have absorbed the surviving content first. Deleting earlier would leave a window with neither the old description nor the new one.

**Files:**
- Delete: `docs/architecture.md`
- Move: `docs/methodology.md` → `docs/archive/methodology-bavi.md`
- Modify: `docs/archive/methodology-bavi.md` (add a superseded-by header)
- Modify: `README.md` (repository map gains `docs/manual/`)
- Modify: `docs/manual/README.md` (convert the chapter table's plain names into anchors)
- Modify: `docs/STATUS.md` (record the change; file any defects found while writing)

- [ ] **Step 1: Confirm the absorption actually happened**

Run:
```bash
grep -l "artifact_manifest.jsonl\|append-only" docs/manual/02-harness-outcome-audit.md
grep -l "witnesses with different competence\|reliability gate" docs/manual/06-data-and-evidence.md
```
Expected: both files listed. If either is empty, the content was not absorbed — go back to Task 5 or Task 9 rather than deleting the source.

- [ ] **Step 2: Delete `docs/architecture.md`**

```bash
git rm docs/architecture.md
```

- [ ] **Step 3: Move `docs/methodology.md` and add its header**

```bash
mkdir -p docs/archive && git mv docs/methodology.md docs/archive/methodology-bavi.md
```

Prepend a header stating: this describes the pre-rework three-phase method built around Super Typhoon Bavi 2026, archived on 2026-08-23 alongside `events/archive/bavi-2026/`; its cross-view methodological lineage survives in `docs/manual/06-data-and-evidence.md`; the budget-constrained inspection routing it describes was never implemented. Bilingual, per the global constraints.

- [ ] **Step 4: Point `README.md` at the manual**

In the repository map, add `docs/manual/` with a one-line description. In the paragraph above the map, add one sentence: the manual is the authority on architecture and mechanism, and this README is the entry point.

- [ ] **Step 5: Anchor the chapter list in `docs/manual/README.md`**

Convert the plain filenames left by Task 3 into Markdown links now that every chapter exists.

- [ ] **Step 6: Record the change and any findings in `docs/STATUS.md`**

Update the `Updated:` date. Add a `Done` entry for the manual. Remove the `docs/architecture.md still describes the pre-rework pipeline` line from `Known limitations`, since it is no longer true. Add any defects discovered while writing to `Next` or `Known limitations` — that is where they go, per the global constraints.

- [ ] **Step 7: Verify nothing points at the deleted or moved files**

```bash
grep -rn "docs/architecture.md\|docs/methodology.md" --include="*.md" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.jsx" --include="*.js" . | grep -v node_modules | grep -v docs/design/
```
Expected: no output outside `docs/design/` (the specs and plans legitimately discuss these files by name as historical record). Fix any live reference found.

- [ ] **Step 8: Run every gate**

```bash
python -m unittest discover -s tests
python scripts/publication_boundary.py plan --check
python scripts/manual_anchors.py check docs README.md src/geosteward/live/__init__.py
cd app && npm test && cd ..
```
Expected: all pass.

- [ ] **Step 9: Terminology consistency check**

For each glossary term, confirm the manual uses exactly one Chinese rendering:
```bash
python3 - <<'PY'
import pathlib, re
glossary = pathlib.Path('docs/manual/12-glossary.md').read_text()
terms = re.findall(r'^\|\s*`?([A-Za-z][\w /()-]+?)`?\s*\|\s*([^|]+?)\s*\|', glossary, re.M)
files = [p for p in pathlib.Path('docs/manual').glob('*.md') if p.name != '12-glossary.md']
body = "\n".join(p.read_text() for p in files)
for en, zh in terms:
    zh = zh.strip()
    if zh and zh not in body:
        print(f"glossary rendering never used in the manual: {en} -> {zh}")
PY
```
A term whose Chinese rendering appears nowhere else is either an unused glossary entry or a sign that some chapter coined its own wording. Investigate each before proceeding.

- [ ] **Step 10: Fresh-reader test**

Give the thirteen files, and nothing else, to a reader with no prior context — a colleague, or a subagent if the owner asks for one. Ask four questions: what does this repository do; where does its competence end; what does it refuse to do; what is not implemented. Wrong or unsupported answers are gaps in the manual, not reader error. Fix them and re-run.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "docs: retire the two documents the manual supersedes"
```

---

## Self-Review

**Spec coverage.** §1 problem → Tasks 5, 9, 14. §2 readers → Task 3 reading paths. §3 two-documents ruling → global constraints (no patent language); the memo itself is out of scope per §11. §4 thirteen files → Tasks 2–13, all thirteen filenames accounted for. §5 bilingual conventions → global constraints, enforced by Task 14 Step 9. §6 sourcing and anchor script → Task 1, plus the "read from artifacts" steps in Tasks 4, 6, 7, 9, 10, 11, 13. §7 retirement → Task 14, gated on Step 1 proving absorption. §8 division of labour → Task 3's `What this manual is not` and Task 13's `11` final section. §9 per-file specs → Tasks 2–13 one-to-one. §10 verification → each task's gate step, plus Task 14 Steps 8–10. §11 out of scope → honoured; no task rewrites the README beyond a pointer, and no task fixes code. §12 risks → mitigations are the anchor gate (Task 1), reader routing (Task 3), and the absorption gate (Task 14 Step 1). §13 definition of done → Task 14 Steps 8–11.

**One spec amendment, made deliberately.** Spec §6 scoped the anchor gate to `docs/manual/*.md`. Task 1 widens it to accept arbitrary roots, and CI passes `docs README.md src/geosteward/live/__init__.py`. Reason: the 2026-08-23 folder move found two stale doc paths **in source files**, which is the same failure class the gate exists for, and the wider scope costs nothing. The script's known misses — bare prose paths, and the line-wrapped path in `src/geosteward/harness/policy_v1.yaml` — are documented rather than papered over.

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". Each content task names its sources, its verbatim headings, its required facts, and its verification command. Task 1 carries complete test code and a complete CI snippet.

**Type and name consistency.** `extract_anchors` / `Anchor` / `resolve` / `collect` / `main` are used identically in Task 1's tests, implementation notes, and CI step. Filenames `01`–`12` are fixed in Task 3 and referenced unchanged in Tasks 4–14. Function names cited in the content tasks were read from the source, not inferred: `check_crs`, `check_join_integrity`, `check_bounds`, `check_uncertainty_present`, `CheckResult`, `sha256_file`, `new_run_id`, `AuditLog.record`, `verifiability_rank`, `weakest`, `PolicyRequest`, `PolicyDecision`, `PolicyEngine.evaluate`, `validate_rules`, `default_deny`, `ArtifactRef`, `DistributionPolicy.evaluate`, `plan_publication`, `write_allowlist`, `redact`, `verify_site`, `_sort_key`, `classify`, `check_claims`, `is_non_assertive`, `response_digest`, `build_payload`, `RecordShapeError`, `LiveEvidenceRecorder`, `compare_digests`, `LiveRequest`, `LiveResult`, `GroundedResult`, `buildCoverageIndex`, `lookupCoverage`, `eventsOf`, `mergedProps`, `watchSummary`, `parseCitations`, `verifiabilityLabel`, `stageValidity`, `artifactLineage`, `priorityScores`, `topCells`, `geocodeAddress`, `EVENTS`, `VIEWS`, `RAMP`.

**Natural checkpoint.** Tasks 1–4 leave the repository in a valid, useful state: the gate exists, terminology is fixed, and a reader can already answer "what does this do". If the work is interrupted, stopping after Task 4 is coherent; stopping mid-Task-14 is not, because the retirement steps must complete together.
