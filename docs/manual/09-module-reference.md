# 09 · Module reference

This chapter is an index, not an explanation. For every file under
`src/geosteward/`, `gateway/`, `scripts/`, and `app/src/`, it states one line
of responsibility, what the file depends on, and what tests it — so a
maintainer who finds a file on disk can look it up here rather than reading
the whole tree to learn what it is for. Where a file's *reason* — why the
harness is shaped this way, why a plane exists — is the subject of a chapter
of its own, the row points there instead of re-explaining it; chapters
`02`–`08` are the mechanism layer, this one is the file layer.

> **中文。** 本章是索引，不是讲解。对 `src/geosteward/`、`gateway/`、
> `scripts/`、`app/src/` 下的每一个文件，本章给出一行职责说明、它依赖什么、
> 由什么测试覆盖——这样维护者在磁盘上找到一个文件时，可以直接来这里查，而不用
> 通读整棵目录树才弄清它是做什么的。如果某个文件的"为什么"——harness 为什么这样
> 设计、某个平面为什么存在——本身就是某一章的主题，对应行会指向那一章，而不是
> 在这里重讲一遍；`02`–`08` 是机制层，本章是文件层。

A file with no test is marked `no direct test` rather than left blank: an
empty cell reads as an oversight, and knowing a file is untested is itself
useful information for a maintainer deciding where to add coverage.

> **中文。** 没有测试的文件在表格里写明"no direct test"（无直接测试），而不是
> 留空——空格看起来像是漏写了，而"这个文件没有测试"本身就是维护者判断该往哪里
> 补测试时有用的信息。

## src/geosteward/harness/

The Steward Harness — outcome, process, and institutional validity — is the
subject of chapters `02` (checks and audit), `03` (the claim plane), `04`
(the distribution plane), and `05` (verifiability). This table names the
files; the chapters explain why each one is shaped the way it is.

> **中文。** Steward Harness（问责框架）——结果、过程、制度三层有效性——是
> `02`（检查与审计）、`03`（断言平面）、`04`（发布平面）、`05`（可验证性）
> 四章的主题。这里的表格只列出文件，各章解释每个文件为什么是这个设计。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/harness/__init__.py` | Package docstring: names the harness as outcome + process + institutional validity around the agents. | — | no direct test (docstring only; exercised through its submodules) |
| `src/geosteward/harness/audit.py` | Append-only audit log: `AuditLog.record()` writes one immutable JSONL row per action, stamped with a `run_id`; `sha256_file()` and `new_run_id()` support artifact hashing. | stdlib only | `tests/test_harness_audit.py` |
| `src/geosteward/harness/checks/__init__.py` | Re-exports `outcome.py`'s check functions as the package's public surface. | `src/geosteward/harness/checks/outcome.py` | exercised via `tests/test_harness_checks.py` (which imports `outcome` directly) |
| `src/geosteward/harness/checks/outcome.py` | Outcome-validity checks: pure functions (`check_crs`, `check_join_integrity`, `check_bounds`, `check_uncertainty_present`) each returning a `CheckResult`; the caller decides whether a failure aborts the stage. | stdlib only | `tests/test_harness_checks.py` |
| `src/geosteward/harness/distribution.py` | The distribution plane: `DistributionPolicy` evaluates an `ArtifactRef` (kind, `resolution_cap`, `audience`, `license`) against ordered rules loaded from `policy_v1.yaml`, first-match-wins, fail-closed default. | `src/geosteward/harness/policy.py` (reuses `PolicyDecision`, `validate_rules`) | `tests/test_harness_distribution.py` |
| `src/geosteward/harness/policy_v1.yaml` | The one policy document: the claim-plane `rules` list plus the `distribution` rule list and `artifact_classes` map, sharing one grammar. | parsed by `src/geosteward/harness/policy.py` and `src/geosteward/harness/distribution.py` | `tests/test_policy_v1_matrix.py`, `tests/test_harness_distribution.py`, `tests/test_harness_publication.py`, `tests/test_gateway_steward.py` |
| `src/geosteward/harness/policy.py` | The claim plane: `PolicyEngine.evaluate()` runs ordered rules first-match-wins over a `PolicyRequest`, returning a `PolicyDecision`; also owns `verifiability_rank`, `weakest`, and `default_deny`. `from_yaml` additionally reads `published_events`, the scope the gateway's evidence store is built from, so the claim plane and the distribution plane publish from one list. | stdlib + PyYAML | `tests/test_harness_policy.py`, `tests/test_policy_v1_matrix.py`, `tests/test_gateway_governance.py` (the shared `published_events` list) |
| `src/geosteward/harness/publication.py` | Plans and verifies the public surface: `plan_publication()` walks `events/` against the distribution policy to build an allowlist; `verify_site()` checks an assembled site tree against that allowlist by set difference. Also defines `redact()` (see callout below). | `src/geosteward/harness/distribution.py` | `tests/test_harness_publication.py` |

**`redact()` has no callers, anywhere, including its own test file.** It is
defined at `publication.py` — `grep -rn "redact(" --include="*.py" .` across
the whole repository turns up exactly one line, the `def redact(text: str)`
itself. `tests/test_harness_publication.py` does exercise the neighboring
mechanism — `test_manifest_is_flagged_for_workstation_path_redaction` checks
the `redact_workstation_paths` flag `plan_publication()` sets, and
`test_redacted_manifest_passes` checks already-redacted manifest content —
but neither test, nor anything else in the file, calls `redact()` itself.
The redaction that actually runs in production lives in
`app/scripts/sync-artifacts.mjs`, which reads that same
`redact_workstation_paths` flag (set from `REDACTED_KINDS`) and does the
string replacement itself in JavaScript, against a `WORKSTATION_PATH`
pattern kept independently in step with the Python one. So the *decision* —
which files carry workstation paths and should be redacted — lives in the
policy layer here, and the *execution* lives in the build script;
`redact()` is a second, wholly unused implementation of the same
replacement — not exercised by its own tests, let alone called by the
pipeline.

> **中文。** `redact()` 没有任何调用方——包括它自己的测试文件在内。它定义在
> `publication.py` 里；对全仓库执行 `grep -rn "redact(" --include="*.py" .`，
> 只能找到 `def redact(text: str)` 这一行定义本身。
> `tests/test_harness_publication.py` 确实测试了与它相邻的机制——
> `test_manifest_is_flagged_for_workstation_path_redaction` 检查
> `plan_publication()` 设置的 `redact_workstation_paths` 标志，
> `test_redacted_manifest_passes` 检查已脱敏的清单内容——但无论是这两个测试，
> 还是文件里的其他任何地方，都没有调用 `redact()` 本身。真正在生产流程里执行
> 脱敏的是 `app/scripts/sync-artifacts.mjs`：它读取同一个
> `redact_workstation_paths` 标志（来自 `REDACTED_KINDS`），用 JavaScript 自己
> 做字符串替换，对应的 `WORKSTATION_PATH` 正则与 Python 版本各自独立维护、
> 保持一致。也就是说，"哪些文件带工作站路径、应该脱敏"这个**决策**在策略层
> （本文件），而**执行**在构建脚本里；`redact()` 是同一次替换的第二份实现，
> 完全没被用到——连自己的测试都没有调用它，更不用说被流水线调用。

## src/geosteward/sources/

The four Tier-1 watch connectors, normalized into one shape by
`watchbase.py` and merged by `src/geosteward/watch.py` — see chapter `06`
for the field-by-field product they build. `zj_typhoon.py` is the odd file
out here: it is not a Tier-1 connector and is covered under
[Legacy, pending retirement](#legacy-pending-retirement) below, not in this
table's mechanism cross-reference.

> **中文。** 这里是四个 1 级（Tier 1）Watch 数据源连接器，由
> `watchbase.py` 统一成同一种数据形状，再由 `src/geosteward/watch.py` 合并——
> 逐字段的产物说明见第 `06` 章。`zj_typhoon.py` 是这里唯一的例外：它不是 1 级
> 连接器，归入下面的"遗留，等待退役"一节，不参与本表指向机制章节的交叉引用。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/sources/__init__.py` | Package docstring only. | — | no direct test |
| `src/geosteward/sources/nhc.py` | NHC current tropical cyclones connector (keyless): `fetch()` + `parse()` into `WatchEvent` rows. | `src/geosteward/sources/watchbase.py` | `tests/test_connectors_nhc_nifc.py` |
| `src/geosteward/sources/nifc.py` | NIFC/WFIGS wildfire connector (keyless ArcGIS query); `raise_on_arcgis_error()` fails closed on an HTTP-200 ArcGIS error envelope instead of reporting zero events. | `src/geosteward/sources/watchbase.py` | `tests/test_connectors_nhc_nifc.py` |
| `src/geosteward/sources/nws.py` | NWS active alerts connector: paginates `alerts/active` up to `MAX_PAGES`, raising rather than silently under-reporting if the feed does not exhaust within the cap. | `src/geosteward/sources/watchbase.py` | `tests/test_connectors_usgs_nws.py` |
| `src/geosteward/sources/usgs.py` | USGS earthquake feed connector (keyless, updated every minute). | `src/geosteward/sources/watchbase.py` | `tests/test_connectors_usgs_nws.py` |
| `src/geosteward/sources/watchbase.py` | Shared foundations for all four connectors: `WatchEvent`, `fetch_json()`, `save_snapshot()`, `merge_pages()`. | stdlib only | `tests/test_watchbase.py` |
| `src/geosteward/sources/zj_typhoon.py` | Zhejiang Water Resources typhoon API client (`list_typhoons`, `active_typhoons`, `typhoon_detail`). Pre-rework; see [Legacy, pending retirement](#legacy-pending-retirement). | stdlib only | no direct test |

## src/geosteward/deepcase/

The offline Tier 2/3 builders: precomputed on the owner's workstation from
the local dataset registry and committed under `events/`. Chapter `06`
covers the fields these produce, per event.

> **中文。** 这是离线的 2/3 级构建模块：在拥有者本机上，基于本地数据集
> 注册表离线预计算，产物提交到 `events/` 下。这些字段逐事件的说明见第 `06` 章。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/deepcase/__init__.py` | Package docstring: deep cases are offline pipelines over committed datasets, every product passing through the Steward Harness. | — | no direct test |
| `src/geosteward/deepcase/dins.py` | CAL FIRE DINS ingest and H3 r9 aggregation for the Eaton Fire case: crosswalks native `DAMAGE` values to the canonical severity scale, aggregates points to H3 cells, computes severity totals; the point layer is registered restricted-resolution and never shipped to the resident app. | `h3` | `tests/test_deepcase_dins.py` |
| `src/geosteward/deepcase/grids.py` | Generic H3 aggregation helpers reused by every deep-case builder: labeled points → H3 cell → label histogram, independent of hazard. | `h3` | `tests/test_deepcase_grids_svi.py` |
| `src/geosteward/deepcase/svi.py` | CDC/ATSDR SVI tract join: pure-Python even-odd point-in-polygon assigns H3 cells to census tracts and attaches SVI percentile ranks; CDC's `-999` missing sentinel becomes `None` and is counted, never dropped. | stdlib `csv` | `tests/test_deepcase_grids_svi.py` |
| `src/geosteward/deepcase/dossier.py` | Dossier maintenance: `retire_unknown()` moves a `declared_unknowns` line to `resolved_unknowns` once a *registered* artifact makes it untrue — refuses unregistered resolvers and never-declared lines, reissues `event_record.json` through `EventContext.write_json` (new manifest row, old row kept) and writes an audit `stage` row; idempotent on re-run. Added 2026-09-03 after the Eaton SVI staleness recorded in `11`. | `src/geosteward/agents/base.py`, `src/geosteward/harness/audit.py` | `tests/test_deepcase_dossier.py` |
| `src/geosteward/deepcase/vlm_severity.py` | Zero-shot vision-language severity grading ported from the RAPID line: RAPID's wildfire 5-class prompt verbatim (hashed into every record), strict fail-closed parsing (`unparseable` and `unknown_label` are recorded statuses, never coerced), RAPID's NCSE plus a confusion matrix, EXIF-GPS extraction and H3 r9 aggregation of truth-vs-prediction histograms (with a declared `location_source`), and the DINS-semantics collapse from the prompt's five classes to the Eaton matched set's three repairability classes. The network call is injected, so nothing here needs a model. | `src/geosteward/gateway/llm.py` (`image_part`, `text_part`), `src/geosteward/deepcase/dins.py` (`CANONICAL_SCALE`), `h3` | `tests/test_deepcase_vlm_severity.py`, `tests/test_deepcase_vlm_eaton.py` |

## src/geosteward/live/

The non-retainable-evidence contract, its two regimes, and the record that
makes a lookup accountable without keeping its content — chapter `05` is the
mechanism explanation; this table is only the files.

> **中文。** 这里是"内容不可留存"证据的契约、两种留存制度，以及让一次查询
> 在不留存内容的前提下仍可问责的记录结构——机制说明见第 `05` 章，本表只列文件。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/live/__init__.py` | Package docstring: sources whose licence forbids retaining content, so accountability rests on something other than a stored copy. | — | no direct test |
| `src/geosteward/live/base.py` | The contract: `LiveSource`/`GroundedSource` protocols, `LiveRequest`, `LiveResult`, `GroundedResult`, `response_digest()`, and the `re-derivable`/`cited-only` retention stances. | `src/geosteward/harness/policy.py` (`CITED_ONLY`, `RE_DERIVABLE`) | exercised via `tests/test_live_adapters.py`, `tests/test_live_record.py`, `tests/test_gateway_live.py` |
| `src/geosteward/live/fake.py` | Deterministic fakes (`FakeLiveSource`, `FakeGroundedSource`) whose default payload is deliberately loud — `POISON_STRINGS`/`POISON_PAYLOAD` make any accidental retention greppable. | `src/geosteward/live/base.py` | `tests/test_gateway_live.py`, `tests/test_live_record.py` |
| `src/geosteward/live/grounded.py` | `GroundedMapsSource`: the `cited-only` regime against the Gemini `generateContent` + `google_maps` tool response shape. Unverified against the live API — no key. | `src/geosteward/live/base.py`, stdlib | `tests/test_live_adapters.py` |
| `src/geosteward/live/places.py` | `PlacesSource`: the `re-derivable` regime against Google Places (New) `searchNearby`. Also unverified against the live API — no key. | `src/geosteward/live/base.py`, stdlib | `tests/test_live_adapters.py` |
| `src/geosteward/live/record.py` | `LiveEvidenceRecorder` / `build_payload()`: the publishable record of a non-retainable lookup — request plus response digest, built from a named key list rather than `asdict()`, so a future field addition cannot leak into the record silently. | `src/geosteward/live/base.py`, the live sources | `tests/test_live_record.py` |

## src/geosteward/gateway/

The Steward Harness wrapped around an LLM — chapter `07` is the request
lifecycle; this table is the files that implement it.

> **中文。** 这里是包裹在 LLM 外层的 Steward Harness——请求生命周期见第 `07` 章，
> 本表是实现它的文件。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/gateway/__init__.py` | Package docstring: deterministic code decides authorization and verifies output; the LLM only drafts prose from evidence it is handed. | — | no direct test |
| `src/geosteward/gateway/context.py` | Evidence retrieval: `EvidenceStore` / `EventEvidence` / `Fact` build manifest-listed facts, each carrying a 12-hex `artifact_id`; never fetches the open web. The store is scoped to the policy's `published_events` and skips any dossier or grid collection flagged `model_derived`, recording each exclusion (`excluded_events`, `excluded_grids`) rather than staying silent. | `h3` | `tests/test_gateway_governance.py` (scope and `model_derived` exclusions); exercised indirectly through `Steward` in `tests/test_gateway_steward.py` and `tests/test_gateway_live.py` |
| `src/geosteward/gateway/llm.py` | Provider-agnostic chat client over an OpenAI-compatible `/chat/completions` shape, stdlib only; local Ollama by default, any hosted provider by env var. | stdlib only | no dedicated test file — its `LLMUnavailable` path is exercised via `tests/test_gateway_steward.py` / `tests/test_gateway_live.py` |
| `src/geosteward/gateway/steward.py` | `Steward`: policy pre-check → evidence retrieval → LLM → claim post-check → audit; `classify()` and `check_claims()` are the deterministic gates on either side of the model. | `context.py`, `llm.py`, `src/geosteward/harness/audit.py`, `src/geosteward/harness/policy.py`, `src/geosteward/live/base.py`, `src/geosteward/live/record.py` | `tests/test_gateway_steward.py`, `tests/test_gateway_live.py`, `tests/test_gateway_governance.py` (refuses to start without a `published_events` scope) |

## src/geosteward/agents/

**The four agent *role* classes are not on the deep-case path; `base.py` is
not one of them.** `watcher.py`, `dossier.py`, `exposure.py`, and
`decision.py` — `TyphoonWatcher`, `TyphoonDossier`, `TyphoonExposure`,
`WatchBulletin` — are real, present, and imported by
`src/geosteward/pipeline.py`, where they are the organising structure of the
pre-rework, single-hazard (typhoon) pipeline. The three deep cases this
project actually ships — Eaton Fire, Hurricane Milton, Hurricane Ian — are
built by `scripts/build_eaton_case.py`, `scripts/build_milton_case.py`, and
`scripts/build_ian_case.py`, and none of those three scripts imports any of
those four role classes. `base.py` is a different kind of file: it is the
artifact-contract infrastructure (`Artifact`, `EventContext`, `utc_stamp`) —
current, not legacy — and all three build scripts import it directly
(`from geosteward.agents.base import Artifact, EventContext, utc_stamp`), the
same way chapter `02` documents it being reused "by every pipeline stage and
every deep-case build script." So the accurate statement is narrower than
"nothing here is used": the deep-case builders reuse `agents/base.py`'s
primitives and go *around* the role classes — which is also the answer to
why this subpackage is still here at all. A reader who finds
`agents/watcher.py`, sees it is a real, working, tested class, and assumes it
therefore sits somewhere on the path that produces the map the
resident-facing app renders, has misread the whole system: it does not.

> **中文。** **不在深度案例路径上的是四个 agent 角色类，`base.py` 不算在内。**
> `watcher.py`、`dossier.py`、`exposure.py`、`decision.py`——也就是
> `TyphoonWatcher`、`TyphoonDossier`、`TyphoonExposure`、`WatchBulletin`——
> 都是真实存在、被 `src/geosteward/pipeline.py` 引入的代码，是重构前那条单一
> 灾种（台风）流水线的组织结构。这个项目真正对外发布的三个深度案例——Eaton 火灾、
> Milton 飓风、Ian 飓风——分别由 `scripts/build_eaton_case.py`、
> `scripts/build_milton_case.py`、`scripts/build_ian_case.py` 构建，这三个脚本
> 没有一个导入上述四个角色类。`base.py` 是另一类文件：它是制品契约基础设施
> （`Artifact`、`EventContext`、`utc_stamp`）——是现役机制，不是遗留代码——三个
> 构建脚本都直接导入它（`from geosteward.agents.base import Artifact,
> EventContext, utc_stamp`），与第 `02` 章所写的"被每一个流水线阶段和每一个
> 深度案例构建脚本复用"完全一致。所以准确的说法比"这里的东西都没用上"更窄：
> 深度案例构建脚本复用了 `agents/base.py` 的基础设施，绕开的是那四个角色类——
> 这也回答了这个子包为什么还留在这里。如果读者发现 `agents/watcher.py` 是一个
> 真实、可运行、有测试的类，就认定它一定在生成居民端应用所渲染地图的路径上，
> 那就误读了整个系统：事实并非如此。

The one exception worth naming precisely is `evidence.py`'s
`CrossViewEvidence`. Its `.name` attribute is the string
`"evidence.crossview"`, and that exact string has **zero** occurrences in
any committed audit log in this repository — it is instantiated in exactly
one place, `tests/test_pipeline.py`, which drives it far enough to observe
that it fails closed (raises `FileNotFoundError` without an imagery
manifest, then `NotImplementedError` even with one). Do not confuse this
with the audit actors `evidence.crossview_grid` and
`evidence.crossview_coverage`, which do appear in real committed audit
logs: those come from `scripts/build_ian_case.py` and
`scripts/build_eaton_case.py` respectively — separate, build-script-local
pieces of code with similar-looking names and no relationship to
`agents/evidence.py` beyond the coincidence of vocabulary.

> **中文。** 唯一值得精确说明的例外是 `evidence.py` 里的 `CrossViewEvidence`。
> 它的 `.name` 属性是字符串 `"evidence.crossview"`，而这个字符串在本仓库任何
> 已提交的审计日志里出现次数为**零**——它只在一处被实例化，也就是
> `tests/test_pipeline.py`，用来验证它会失败即拒绝（fail-closed）：没有影像清单时抛
> `FileNotFoundError`，有清单时也抛 `NotImplementedError`。不要把它和确实出现在
> 真实审计日志里的 `evidence.crossview_grid`、`evidence.crossview_coverage`
> 这两个审计执行者名称搞混：它们分别来自 `scripts/build_ian_case.py` 和
> `scripts/build_eaton_case.py`——是各自构建脚本本地的独立实现，除了名字碰巧相似
> 之外，和 `agents/evidence.py` 没有任何关系。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/agents/__init__.py` | Package docstring only. | — | no direct test |
| `src/geosteward/agents/base.py` | Agent contract: `Artifact`, `EventContext`, the `Agent` protocol; a rerun writes a new timestamped artifact rather than overwriting. Current infrastructure, not legacy — imported directly by all three `scripts/build_*_case.py` deep-case builders, not just by the four role classes below. | stdlib only | `tests/test_harness_audit.py` (imports `Artifact`, `EventContext` directly); also exercised through the pipeline tests below |
| `src/geosteward/agents/watcher.py` | `TyphoonWatcher`: polls `zj_typhoon` for one `tfid`, snapshots the live track. | `src/geosteward/sources/zj_typhoon.py`, `base.py` | no dedicated unit test — exercised via `tests/test_pipeline.py` / `tests/test_pipeline_audit.py` through `run_pre_event` |
| `src/geosteward/agents/dossier.py` | `TyphoonDossier`: turns the latest snapshot into a structured, source-attributed event record. | `src/geosteward/hazards/typhoon.py`, `base.py` | same as above (pipeline tests) |
| `src/geosteward/agents/exposure.py` | `TyphoonExposure`: Beaufort-threshold (7/10/12) wind-sector polygons per track point, as GeoJSON. | `src/geosteward/hazards/typhoon.py`, `dossier.py` (`latest_snapshot`) | same as above (pipeline tests) |
| `src/geosteward/agents/evidence.py` | `CrossViewEvidence`: post-event cross-view damage-assessment interface. Fails closed — raises without an imagery manifest, raises `NotImplementedError` even with one. Not called from any deep-case build script; see the callout above. | `base.py` | instantiated only in `tests/test_pipeline.py` |
| `src/geosteward/agents/decision.py` | `WatchBulletin`: turns dossier + exposure artifacts into a Markdown bulletin plus a machine-readable action list, listing unknowns explicitly. | `base.py` | same as above (pipeline tests) |

## src/geosteward/ — top level

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/__init__.py` | Package docstring and `__version__`. | — | no direct test |
| `src/geosteward/pipeline.py` | `run_pre_event()`: orchestrates `PRE_EVENT_AGENTS = (TyphoonWatcher, TyphoonDossier, TyphoonExposure, WatchBulletin)` in sequence for one typhoon event. This is the pre-rework pipeline's entry point, invoked by `scripts/run_pre_event.py` — not part of building any of the three deep cases (see [src/geosteward/agents/](#srcgeostewardagents) above). | `src/geosteward/agents/base.py`, `src/geosteward/agents/watcher.py`, `src/geosteward/agents/dossier.py`, `src/geosteward/agents/exposure.py`, `src/geosteward/agents/decision.py`, `src/geosteward/harness/audit.py` | `tests/test_pipeline.py`, `tests/test_pipeline_audit.py` |
| `src/geosteward/watch.py` | `build_watch_product()`: the Tier-1 watch builder — merges normalized connector events into one national FeatureCollection, running outcome checks and declaring failures explicitly rather than reporting them as silently-missing data. | `src/geosteward/harness/checks/`, `src/geosteward/sources/watchbase.py` | `tests/test_watch_product.py` |

## gateway/

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `gateway/main.py` | Thin FastAPI HTTP skin over `Steward`: an `/ask` endpoint plus a health check. All accountability logic lives in `src/geosteward/gateway/steward.py`; this file only parses requests and serves JSON. | `fastapi`, `pydantic`, `src/geosteward/gateway/steward.py`, `src/geosteward/harness/audit.py`, `src/geosteward/harness/policy.py` | no direct test — no test file imports `gateway.main`; the `Steward` it wraps is tested directly in `tests/test_gateway_steward.py` |

## scripts/

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `scripts/ask_steward.py` | CLI: runs the full gateway chain locally (policy pre-check → evidence → LLM → claim post-check → audit) against a committed deep case. | `src/geosteward/gateway/steward.py`, `src/geosteward/harness/audit.py` | no direct test |
| `scripts/build_eaton_case.py` | Builds the Eaton Fire 2025 deep case (Tier 2 exposure + Tier 3 evidence) from the owner's local dataset registry; offline, fail-closed. | `src/geosteward/deepcase/dins.py`, `src/geosteward/harness/checks/`, `src/geosteward/harness/audit.py`, `src/geosteward/agents/base.py` (`Artifact`, `EventContext`, `utc_stamp` — not the role classes) | no direct test — offline pipeline requiring the private dataset registry |
| `scripts/build_eaton_svi.py` | Appends the CDC SVI join stage to the already-built Eaton case: assigns each cell to one census tract by centroid point-in-polygon, then retires the dossier's "SVI join pending" declared unknown that the new grid makes untrue. | `src/geosteward/deepcase/svi.py`, `src/geosteward/deepcase/dossier.py`, `src/geosteward/harness/audit.py` | no direct test (the retirement itself is tested in `tests/test_deepcase_dossier.py`) |
| `scripts/build_eaton_vlm.py` | Adds the zero-shot cross-view grading stage (`evidence.vlm_crossview`) to the already-built Eaton case from the owner's EATON_wildfire_mapillary_matched set: grades each sample's post-event field image with RAPID's wildfire 5-class prompt verbatim (the same `prompt_sha256` as the Palisades run), collapses the five DINS classes onto the set's three repairability labels by DINS semantics before scoring, keeps both predictions in every record, and takes location from the manifest's post-event point (not EXIF). Seeded stratified `--sample` per class; fails closed unless ≥ 95 % of graded samples fall inside the committed `crossview_h3_r9_coverage.geojson` cells. Writes the prompt, lineage-only sample records, an accuracy/NCSE summary and a per-tile agreement grid flagged `model_derived`; does not touch the dossier or the registry snapshot it reads. | `src/geosteward/deepcase/vlm_severity.py`, `src/geosteward/gateway/llm.py`, `src/geosteward/harness/checks/outcome.py`, `src/geosteward/harness/audit.py`, `h3` | `tests/test_deepcase_vlm_eaton.py` (sample loading, quality gate, stratification — no model); the grading it composes is tested in `tests/test_deepcase_vlm_severity.py` |
| `scripts/retire_dossier_unknown.py` | Retroactive form of the same retirement for artifacts that landed before builders did it themselves and cannot be rebuilt here; same function, so the resulting record, manifest row and audit row match a builder-issued one except for the stage name `dossier.retire_unknown`. Used once, 2026-09-03, on `events/eaton-2025/`. | `src/geosteward/deepcase/dossier.py` | `tests/test_deepcase_dossier.py` (the committed-dossier regression guard) |
| `scripts/build_palisades_vlm.py` | Builds `events/palisades-2025/` (an *evaluation* case, not in `published_events`): grades RAPID's 295-image LA DINS street-view set with whatever OpenAI-compatible vision endpoint `STEWARD_LLM_BASE_URL` names (local Ollama by default), writes per-image records (lineage-only: they carry EXIF coordinates), an accuracy/NCSE/confusion summary that quotes the paper's closed-model numbers beside it, a tile grid of agreement, and the dossier. Resumable by image sha256; aborts if more than 20 % of answers are off-schema. | `src/geosteward/deepcase/vlm_severity.py`, `src/geosteward/gateway/llm.py`, `src/geosteward/harness/checks/outcome.py`, `src/geosteward/harness/audit.py` | no direct test — needs a running vision model; the logic it composes is tested in `tests/test_deepcase_vlm_severity.py` |
| `scripts/build_milton_vlm_bitemporal.py` | Adds a zero-shot pre/post pair grading stage to the Milton case from the public Bi-Temporal set: images from the Hugging Face release, pair ids / coordinates / human labels from the Figshare pair table (the same table the committed `bitemporal_h3_r9_grid.geojson` was built from). RAPID's pre/post prompt verbatim; seeded stratified `--sample` per class; fails closed unless ≥ 95 % of graded pairs fall inside the committed grid's cells. Writes the registry profile, a coordinates-bearing pair-table snapshot (internal), the prompt, lineage-only pair records, an accuracy/NCSE summary and a per-tile agreement grid. | `src/geosteward/deepcase/vlm_severity.py`, `src/geosteward/gateway/llm.py`, `src/geosteward/harness/checks/outcome.py`, `src/geosteward/harness/audit.py`, `h3` | no direct test — needs a running vision model; pair parsing and record shape are tested in `tests/test_deepcase_vlm_severity.py` |
| `scripts/build_ian_case.py` | Builds the Hurricane Ian 2022 deep case (Tier 3 evidence): reliability-gated matched street-view severity samples, plus a sample-density-only layer where no reliable per-point label exists. | `src/geosteward/deepcase/grids.py`, `src/geosteward/harness/checks/`, `src/geosteward/harness/audit.py`, `src/geosteward/agents/base.py` (`Artifact`, `EventContext`, `utc_stamp` — not the role classes) | no direct test |
| `scripts/build_milton_case.py` | Builds the Hurricane Milton 2024 deep case (Tier 2/3) across two AOIs; explicitly excludes GenDisasterSVI street imagery (model-generated) while freezing its registry profile so the exclusion is auditable. | `src/geosteward/deepcase/grids.py`, `src/geosteward/harness/checks/`, `src/geosteward/harness/audit.py`, `src/geosteward/agents/base.py` (`Artifact`, `EventContext`, `utc_stamp` — not the role classes) | no direct test |
| `scripts/close_event.py` | Closes an event from its final committed source snapshot into a separate post-event closure artifact, without altering the frozen pre-event dossier/footprints/bulletin. | `src/geosteward/hazards/typhoon.py` | no direct test |
| `scripts/fetch_bavi_track.py` | CLI wrapper over the watcher's source connector: captures one append-only, UTC-stamped typhoon-track snapshot. | `src/geosteward/hazards/typhoon.py`, `src/geosteward/sources/zj_typhoon.py` | no direct test |
| `scripts/manual_anchors.py` | This manual's own gate: extracts path-shaped tokens from inline code spans and Markdown link targets and checks each resolves on disk, or is declared absent on purpose. | stdlib only | `tests/test_manual_anchors.py` |
| `scripts/publication_boundary.py` | Enforces the distribution plane at the two points it can be enforced: `plan` writes the public allowlist from the policy; `verify` checks an assembled site tree against it and fails the deploy on a violation. | `src/geosteward/harness/publication.py`, `src/geosteward/harness/distribution.py` (`DistributionPolicy`), `src/geosteward/harness/audit.py` | no dedicated pytest file — run directly in CI: `python scripts/publication_boundary.py plan --check` and `verify` in `.github/workflows/test.yml` and `.github/workflows/pages.yml` |
| `scripts/run_pre_event.py` | CLI wrapper: parses `--event-id` / `--tfid` / `--offline` and calls `run_pre_event()`. | `src/geosteward/pipeline.py` | no direct test of the CLI itself — the function it calls is `tests/test_pipeline.py` / `tests/test_pipeline_audit.py` |
| `scripts/run_watch.py` | Runs the Tier-1 watch loop once: fetches all four connectors, builds the national product; each source's failure is recorded and audited independently, never allowed to block the others. | `src/geosteward/sources/nhc.py`, `src/geosteward/sources/nifc.py`, `src/geosteward/sources/nws.py`, `src/geosteward/sources/usgs.py`, `src/geosteward/sources/watchbase.py`, `src/geosteward/watch.py`, `src/geosteward/harness/audit.py` | `tests/test_run_watch.py` (loads the script directly via `importlib`) |

## app/src/

The two-mode front end — chapter `08` covers the mechanism (resident vs.
planner mode, how a layer's validity badge is computed, how coverage is
distinguished from absence); this table is the files.

> **中文。** 这里是双模式前端——机制说明（居民模式与规划者模式的区别、图层
> 有效性徽章如何计算、"已覆盖"与"未覆盖"如何区分）见第 `08` 章，本表是文件。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `app/src/App.jsx` | Top-level component: mode/view state, data-fetching orchestration; wires the map and every panel together. | `app/src/components/`, `app/src/lib/` | no direct test |
| `app/src/main.jsx` | React root mount. | `app/src/App.jsx` | no direct test |
| `app/src/components/Badges.jsx` | `ValidityBadge` / `TierBadge` / `LiveWatchBadge`: renders harness state (checks recorded, tier, live-watch staleness) with the same visual prominence as the data itself. | — | no direct test |
| `app/src/components/ChatPanel.jsx` | "Ask the Steward" panel: renders every gateway response type — cited answer, rule-ID refusal, declared no-evidence, declared outage — as itself, nothing papered over. | `app/src/lib/citations.js` | no direct test |
| `app/src/components/LineagePanel.jsx` | Lineage viewer: the visible layer traced back to timestamped, hashed manifest rows, plus any local human-in-the-loop adjustments. | `app/src/lib/data.js` (`getLocalAudit`) | no direct test |
| `app/src/components/MapView.jsx` | MapLibre map: paints each layer's choropleth from its committed GeoJSON. | `app/src/lib/views.js`, `app/src/lib/data.js` | no direct test |
| `app/src/components/PlannerPanel.jsx` | Planner-mode trade-off sliders over the Damage × SVI priority layer. | `app/src/lib/data.js` | no direct test |
| `app/src/components/ResidentPanel.jsx` | Resident-mode address lookup against the coverage index; a three-state result (covered / not covered / unreadable), not a binary one. | `app/src/lib/coverage.js`, `app/src/lib/data.js` | no direct test |
| `app/src/lib/citations.js` | Parses `[artifact:HASH12]` / `[live:HASH12]` citation tokens out of answer prose into text/citation runs. | — | `app/src/lib/citations.test.js` |
| `app/src/lib/coverage.js` | Builds the cell → hits coverage index as a union across every loaded layer, distinguishing an unrequested layer from an errored one from an empty one. | — | `app/src/lib/coverage.test.js` |
| `app/src/lib/data.js` | Artifact fetching, manifest/audit parsing, geocoding, and the client-side priority score; every fetch failure surfaces as an explicit status object rather than a silent gap. | — | `app/src/lib/data.test.js` |
| `app/src/lib/views.js` | The layer catalog: one committed artifact mapped to one map layer, each tied to its harness audit stage. | — | no direct test |
| `app/src/lib/watch.js` | `watchSummary()`: merges the live watch layer with its status product; every count is nullable, and null means "not stated," never zero. | — | `app/src/lib/watch.test.js` |

## Legacy, pending retirement

A Zhejiang Water Resources typhoon API and a western-Pacific track parser
sitting inside a system whose live watch and three deep cases are all
US-based is confusing without the history: these two files are what
remains of the pre-rework, single-hazard pipeline the rest of `src/`
outgrew. `docs/STATUS.md` tracks the retirement plan directly: these
modules "remain until Plan 3 rewires the pipeline agents to the US
connectors, then retire to the archive." Until then they are still real,
still imported by `src/geosteward/agents/watcher.py`,
`src/geosteward/agents/dossier.py`, `src/geosteward/agents/exposure.py`, and
the two typhoon CLI scripts (`scripts/close_event.py`,
`scripts/fetch_bavi_track.py`) — none of which sit on the path that builds
any of the three shipped deep cases.

> **中文。** 一个浙江水利厅的台风 API 和一个西太平洋路径解析器，出现在一个
> 实时监测层和三个深度案例全部基于美国的系统里，如果不说明历史会让人困惑：
> 这两个文件是重构前那条单一灾种流水线留下的残余，`src/` 的其余部分已经超越
> 了它。`docs/STATUS.md` 直接记录了退役计划：这些模块"remain until Plan 3
> rewires the pipeline agents to the US connectors, then retire to the
> archive"（保留到 Plan 3 把流水线 agent 迁接到美国数据源为止，之后归档退役）。
> 在那之前它们仍然真实存在，仍被 `src/geosteward/agents/watcher.py`、
> `src/geosteward/agents/dossier.py`、`src/geosteward/agents/exposure.py`，
> 以及两个台风相关 CLI 脚本（`scripts/close_event.py`、
> `scripts/fetch_bavi_track.py`）引入——其中没有一个在构建三个已发布深度案例的
> 路径上。

| Path | Responsibility | Depends on | Tests |
|---|---|---|---|
| `src/geosteward/sources/zj_typhoon.py` | Zhejiang Water Resources typhoon API client: `list_typhoons`, `active_typhoons`, `typhoon_detail`. Polled by `agents/watcher.py`; the source connector behind `scripts/fetch_bavi_track.py`. | stdlib only | no direct test |
| `src/geosteward/hazards/typhoon.py` | Parses Zhejiang typhoon-API payloads into normalized tracks: `parse_track`, `wind_sector_polygon`, `track_summary`. Used by `agents/dossier.py`, `agents/exposure.py`, `scripts/close_event.py`, and `scripts/fetch_bavi_track.py`. | stdlib only | `tests/test_tracks.py` |
| `src/geosteward/hazards/__init__.py` | Package docstring only. | — | no direct test |
