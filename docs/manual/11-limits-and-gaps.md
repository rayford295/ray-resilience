# 11 · Limits and gaps

Every other chapter in this manual describes something that runs. This one
describes what does not, in five different senses that are easy to blur
together and important to keep apart: geography the system has no evidence
for, code that exists but has never executed, code that executes but is not
safe to expose, capability nobody has built yet, and defects in what has
been built. Confusing any two of these with each other is the specific
mistake this chapter exists to prevent — an *absence*, stated plainly in a
`declared_unknowns` list or a module docstring, can look like a description
of a working feature once it is lifted out of the list that says it is
missing. Every fact below was re-verified against the repository while this
chapter was written, by command or by direct inspection, not carried over
from an earlier note.

> **中文。** 本说明书的其余每一章都在讲"什么在运行"，这一章讲的是"什么不在运行"——
> 而且是五种容易混在一起、却必须分开的不同意义上的"不在运行"：这个系统完全没有证据
> 覆盖的地理范围；写出来了但从未真正执行过的代码；执行了但不适合对外暴露的代码；
> 还没有人做出来的能力；以及已经做出来的东西里的缺陷。把这几种混为一谈，正是本章
> 要防止的那个具体错误——一项在 `declared_unknowns` 列表或某个模块文档字符串里明明
> 白白写着"缺失"的**不存在**，一旦从那份写着"这是缺的"的列表里被单独摘出来，读起来
> 就可能像是在描述一项已经做好的功能。下面每一条事实，都是在写这一章的当下重新对照
> 仓库核实过的——用命令核实，或者直接查看文件——而不是从更早的笔记里照抄过来的。

## Where competence ends geographically

Hazard monitoring is nationwide: any US location gets the current Tier-1
watch layer, regardless of [AOI](12-glossary.md) membership. Exposure and
damage analysis — [tier](12-glossary.md) 2 and tier 3 — exist only inside
the three deep-case AOIs (Eaton Fire 2025, Hurricane Milton 2024, Hurricane
Ian 2022) and nowhere else. An address outside all three is told the location is
outside the evaluated areas; an address the app cannot yet resolve is told
that instead of being guessed at — two different failure modes, kept
distinct rather than collapsed into one generic "no result," and enforced by
the three-state `covered` / `not_covered` / `unknown` mechanism `01`
describes rather than left to a client-side guess.

Inside the three AOIs, coverage is not even across the tier ladder: SVI-based
vulnerability context currently exists for exactly one of the three cases.
`events/eaton-2025/exposure/svi_h3_r9_context.geojson` is real, committed,
and carries 265 cells — but neither Milton nor Ian has an equivalent file,
and both dossiers' `declared_unknowns` correctly say so today. Eaton's own
dossier, `events/eaton-2025/dossier/event_record.json`, still says otherwise:
its `declared_unknowns` list carries the line *"social-vulnerability join
(SVI x exposure) pending: no vulnerability claims yet,"* which was true when
written and has been false since `scripts/build_eaton_svi.py` ran — `06`
gives the full account and the reason the file itself was not edited to fix
it. Do not generalize the fix across events — Milton's and Ian's
identically-worded "pending" lines are current, not stale, because neither
case has the file that would make them untrue. This particular staleness
has a live consequence beyond the dossier text sitting inert on disk — see
"Known defects and rough edges" below for what the running gateway does
with it.

> **中文。** 灾害监测覆盖全美国：任何美国地点都能拿到当前的 1 级 Watch 图层，与
> 关注区域（AOI）无关。暴露度与损毁分析——层级（1/2/3 级）里的 2/3 级——只存在于
> 三个深度案例关注区域内（2025 年 Eaton 火灾、2024 年 Milton 飓风、2022 年 Ian
> 飓风），别处没有。三者之外的地址会被告知"该地点超出评估范围"；应用暂时无法解析的
> 地址则会被告知这一点，而不是被瞎猜出一个结果——这是两种不同的失败方式，`01` 章
> 描述的 `covered` / `not_covered` / `unknown` 三态机制把两者分开处理，而不是靠客户端
> 猜测合并成一个笼统的"无结果"。
>
> 三个关注区域内部，覆盖也不是齐平的：基于 CDC SVI（社会脆弱性指数）的脆弱性上下文
> 目前只存在于三个案例中的一个。`events/eaton-2025/exposure/svi_h3_r9_context.geojson`
> 是真实的、已提交的，装着 265 个格；但 Milton 和 Ian 都没有对应文件，两份档案的
> `declared_unknowns` 如今都如实这样写。Eaton 自己的档案
> （`events/eaton-2025/dossier/event_record.json`）却仍然写着相反的话：它的
> `declared_unknowns` 列表里有一行"社会脆弱性联接（SVI × 暴露度）尚待完成：暂无
> 脆弱性结论"——这句话在写下时是真的，但自 `scripts/build_eaton_svi.py` 跑完之后
> 就不再是真的了；`06` 章给出了完整说明，也解释了这份档案没有被改动来修正它的原因。
> 不要把这个修正方式套到别的事件上：Milton 和 Ian 措辞完全相同的"尚待完成"是当下
> 属实的，不是过时的，因为这两个案例都还没有能让这句话变假的那份文件。这一处过时
> 声明还有一个不止于档案文字静静躺在磁盘上的现实后果——正在运行的网关会拿它做什么，
> 见下文"已知缺陷与粗糙之处"一节。

## Implemented but never executed

Neither live adapter has ever run against a live API. `PlacesSource`
(`src/geosteward/live/places.py`) and `GroundedMapsSource`
(`src/geosteward/live/grounded.py`) exist, are tested, and say so in their
own module docstrings — there is no Google Maps Platform key and no Gemini
key configured anywhere this project runs, so `tests/test_live_adapters.py`
drives both against an in-process stub server it starts and tears down
itself, which establishes this code's behaviour and nothing about Google's.
`events/live_evidence.jsonl` — the record `05` describes at length — does
not exist outside tests; a repository-wide search finds it nowhere except a
test's own temporary directory, and `scripts/manual_anchors.py`'s
`DECLARED_ABSENT` list cites the path for exactly this reason, so naming its
absence here does not fail the anchor gate.

A second, unrelated instance of the same pattern: `CrossViewEvidence`
(`src/geosteward/agents/evidence.py`) is a real class with real fail-closed
behaviour — it raises `FileNotFoundError` without an imagery manifest and
`NotImplementedError` even with one — but it is instantiated in exactly one
place in this repository, `tests/test_pipeline.py`, and its `.name` string,
`"evidence.crossview"`, has zero occurrences in any committed
[audit log](12-glossary.md).
Do not confuse it with the audit actors `evidence.crossview_grid` and
`evidence.crossview_coverage`, which do the real work behind the Ian and
Eaton evidence grids `06` walks field by field — those are separate,
build-script-local implementations in `scripts/build_ian_case.py` and
`scripts/build_eaton_case.py` that share nothing with `agents/evidence.py`
but a coincidence of vocabulary. `09` gives the full account of both cases.

> **中文。** 两个实时适配器都从未针对真实 API 运行过。`PlacesSource`
> （`src/geosteward/live/places.py`）和 `GroundedMapsSource`
> （`src/geosteward/live/grounded.py`）都是真实存在、有测试的类，也都在各自的模块
> 文档字符串里写明了这一点——本项目运行的任何地方都没有配置 Google Maps Platform
> 密钥，也没有配置 Gemini 密钥，所以 `tests/test_live_adapters.py` 是拿这两个适配器
> 去对接一个它自己启动又关闭的进程内桩服务器——这只能验证这份代码自己的行为，对
> Google 的服务器会怎么响应什么都没证明。`events/live_evidence.jsonl`——`05` 章
> 详细描述过的那份记录——在测试之外并不存在；对整个仓库搜索，除了某次测试自己的
> 临时目录之外哪里都找不到它；`scripts/manual_anchors.py` 的 `DECLARED_ABSENT`
> 列表正是为此把这个路径登记在案，所以在这里指出它不存在，并不会让锚点检查失败。
>
> 另一个无关但同构的例子：`CrossViewEvidence`（`src/geosteward/agents/evidence.py`）
> 是一个真实存在、有真实失败即拒绝（fail-closed）行为的类——没有影像清单时抛
> `FileNotFoundError`，有清单时也抛 `NotImplementedError`——但它在本仓库里只在一处被实例化，也就是
> `tests/test_pipeline.py`，它的 `.name` 字符串 `"evidence.crossview"` 在任何已提交
> 的审计日志里出现次数为零。不要把它和真正在 Ian、Eaton 证据网格背后干活、被 `06`
> 章逐字段走过的审计执行者 `evidence.crossview_grid`、`evidence.crossview_coverage`
> 搞混——它们是 `scripts/build_ian_case.py` 和 `scripts/build_eaton_case.py` 里各自
> 独立的实现，和 `agents/evidence.py` 除了名字碰巧相似之外没有任何关系。`09` 章有
> 两者的完整说明。

## Implemented but not safe to deploy

Three concrete facts about `gateway/main.py`, verified directly in the code
rather than inferred, together mean the agent gateway is not safe to expose
publicly as it stands. **CORS defaults to allow any origin**:
`allow_origins=os.environ.get("STEWARD_CORS_ORIGINS", "*").split(",")` — an
operator has to actively narrow this. **There is no authentication and no
rate limiting anywhere in the file**: nothing bounds who may call `/ask` or
how often. **The audit log records the exact question and the exact
coordinates, unredacted** — `Steward.answer`'s `gateway_request` row writes
`lat`, `lon`, and `question` verbatim, a different mechanism entirely from
the workstation-path redaction `01` and `04` describe for artifact
manifests, which scrubs filesystem paths, not a person's location or the
words they typed. `07` gives the full account of all three, including why
they matter together rather than separately: a keyed third-party source
sitting behind this gateway would turn the same three gaps into a billing
and disclosure surface, not just a privacy one.

> **中文。** 关于 `gateway/main.py` 的三个具体事实——都是直接在代码里核实的，不是
> 推断出来的——合在一起意味着这套智能体网关目前原样对外暴露是不安全的。**CORS 默认
> 允许任意来源**：`allow_origins=os.environ.get("STEWARD_CORS_ORIGINS",
> "*").split(",")`，需要运维人员主动收紧。**文件里没有任何身份验证，也没有任何限流**：
> 没有任何机制限制谁可以调用 `/ask`、能调用多频繁。**审计日志把确切的问题和确切的
> 坐标原样记了下来，未脱敏**——`Steward.answer` 写入的 `gateway_request` 行原样携带
> `lat`、`lon`、`question`，这和 `01`、`04` 两章讲的针对制品清单的工作站路径脱敏是
> 完全不同的机制——那套脱敏擦掉的是文件系统路径，不是一个人的位置或他们打的字。`07`
> 章有这三点的完整说明，包括为什么要合在一起看而不是分开看：一旦背后接上一个需要
> 密钥的第三方数据源，这三个缺口会一起变成一个计费与信息披露层面的暴露面，而不只是
> 隐私层面的。

## Not implemented

- **Citation click-through.** Answers carry `[artifact:…]` IDs; the UI does
  not yet resolve one to its manifest row, inputs, and check results.
- **Persisted planner adjustments.** `recordAdjustment()` (`app/src/lib/
  data.js`) stamps every slider move `"delivery": "session-only; not
  persisted and not sent to the gateway"` — `08` describes the mechanism.
  Reloading the page discards every adjustment.
- **Budget-constrained inspection routing.** The pre-rework, now-archived
  `docs/archive/methodology-bavi.md` describes a *"budget-constrained route: ordered
  inspection plan under stops/distance budgets"* with no corresponding code
  anywhere in `src/geosteward/` or `scripts/` today; the planner mode `01`
  and `08` describe re-weights and ranks tiles client-side, it does not
  route a vehicle. `06` traces the lineage this document is otherwise right
  about.
- **PMTiles / vector tiles.** The Milton debris layer ships as one plain
  GeoJSON file, `events/milton-2024/exposure/debris_h3_r9_grid.geojson`
  (measured at 5.7 MB) — workable at this scale, not a tiled pipeline.
- **Playwright smoke tests.** The app's automated coverage is unit tests
  only — `10` walks through running them — 44 tests across six files as of
  this chapter's last check, re-verifiable at any time with
  `cd app && npm test`; nothing drives a real browser against a running
  instance.
- **The box-select gesture has no automated coverage.** The drag handling,
  click suppression, and blur/`Escape` cleanup inside
  `app/src/components/MapView.jsx`'s shift-drag effect run against a live
  MapLibre instance and real DOM mouse, keyboard, and window-blur events; no
  test in this repository drives any of it, because there is no browser
  interaction harness here, and adding one would mean new dependencies —
  `app/package.json` lists no browser-automation package or headless-browser
  binary today, for the app or for anything else. What the gesture calls out
  to is covered instead of the gesture itself: the box geometry,
  `bboxFromCorners()` and `cellsInBox()` (`app/src/lib/area.js`, exercised by
  `app/src/lib/area.test.js`), and the click-suppression boundary check,
  pulled out into `isClickSuppressed()` (`app/src/lib/clickSuppression.js`)
  and exercised by `app/src/lib/clickSuppression.test.js` across the
  deadline's four states — before it, exactly at it, after it, and the
  initial `until = 0` state, where nothing is ever suppressed. Everything
  that decides *when* that predicate is consulted — the mouse-move tracking,
  the `dragPan` enable/disable pairing, the `Escape`-key and window-blur
  recovery paths — is reasoned about only in the code's own comments; no
  test exercises any of it.
- **Releases, `CHANGELOG`, `CITATION.cff`, contributor docs.** None exist in
  this repository as of this chapter.

> **中文。** **引证的可点击跳转**：回答携带 `[artifact:…]` 这样的 ID，界面尚未把它
> 解析到对应的清单行、输入和检查结果上。**规划者调整的持久化**：`recordAdjustment()`
> （`app/src/lib/data.js`）给每一次滑块操作盖上 `"delivery": "session-only; not
> persisted and not sent to the gateway"`——`08` 章讲了这个机制；刷新页面会丢弃全部
> 调整。**受预算约束的巡检路线规划**：重建前遗留、如今已归档的
> `docs/archive/methodology-bavi.md` 描述过
> 一种"受站点数/距离预算约束的有序巡检路线规划"，但 `src/geosteward/` 或 `scripts/`
> 里今天都找不到与之对应的任何代码；`01`、`08` 两章描述的规划者模式做的是在客户端
> 给瓦片重新加权、排序，不会给车辆规划路线——`06` 章追溯过这份文档在其他地方讲对的
> 那部分脉络。**PMTiles / 矢量瓦片**：Milton 的债砾层是以单一 GeoJSON 文件形式发布的
> （`events/milton-2024/exposure/debris_h3_r9_grid.geojson`，实测 5.7 MB）——在目前
> 这个规模下能用，但不是一套瓦片化流水线。**Playwright 端到端冒烟测试**：应用的自动化
> 覆盖仅限于单元测试——`10` 章走过一遍如何运行它们——截至本章最近一次核实，一共是
> 六个文件、44 个测试，随时可以用 `cd app && npm test` 重新核实；没有任何测试真正
> 驱动一个浏览器去对接一个正在运行的实例。**框选手势没有任何自动化测试覆盖**：
> `app/src/components/MapView.jsx` 里 shift-drag（按住 Shift 拖拽）逻辑内部的拖拽
> 处理、点击抑制、失焦/`Escape` 清理，运行时依赖的是一个真实的 MapLibre 实例和真实
> 的 DOM 鼠标、键盘、窗口失焦事件；本仓库里没有任何测试驱动过这部分逻辑，原因是
> 这里根本没有浏览器交互测试框架，而添加一个就意味着引入新的依赖——
> `app/package.json` 目前无论是给这个应用还是给别的任何东西，都没有列出任何浏览器
> 自动化包或无头浏览器二进制文件。真正被覆盖的是这个手势所调用的东西，而不是手势
> 本身：
> 矩形几何计算——`bboxFromCorners()` 与 `cellsInBox()`（`app/src/lib/area.js`，由
> `app/src/lib/area.test.js` 覆盖）——以及点击抑制这条边界判断，它被抽取成了
> `isClickSuppressed()`（`app/src/lib/clickSuppression.js`），由
> `app/src/lib/clickSuppression.test.js` 覆盖了这条截止时刻的四种状态——截止之前、
> 恰好在截止那一刻、截止之后，以及初始的 `until = 0` 状态（此时永远不会抑制任何
> 点击）。至于*什么时候*会去查问这条判断——鼠标移动追踪、`dragPan` 的启用/禁用
> 配对、`Escape` 键与窗口失焦的恢复路径——这些都只在代码自己的注释里被讲清楚过；
> 没有任何测试覆盖过它们中的任何一个。**发布版本、`CHANGELOG`、`CITATION.cff`、
> 贡献者文档**：截至本章写作时
> 本仓库里一个都不存在。

## Known defects and rough edges

- **A stale declared-unknown is retrieved and cited exactly like a current,
  data-backed fact.** `EventContext.evidence_for()`
  (`src/geosteward/gateway/context.py:144`) loops over every string in a
  dossier's `declared_unknowns` and wraps each one in the same `Fact` class
  as every grid-derived fact — same citable artifact ID, appended to the
  same `evidence.facts` list the model is grounded on. Nothing in that
  loop records when a string was written or checks whether it is still
  true, so a stale declared-unknown reads to the retrieval code exactly
  like a current one. This is demonstrated, not hypothetical: the
  geographic section above shows Eaton's dossier still declaring its SVI
  join "pending" after `scripts/build_eaton_svi.py` made that false, and
  asking the running gateway a damage question at an Eaton tile (`10`
  records the run) returns a cited answer that repeats *"the social
  vulnerability join is pending, so no vulnerability claims are
  available"* verbatim. The error this produces is conservative rather
  than fabricated — the agent under-reports vulnerability data that exists
  rather than inventing data that does not — but it is still the
  accountable agent asserting something untrue to a user, in a system
  whose stated purpose is that it does not.
- **`check_uncertainty_present` passes on `None`.** The check
  (`src/geosteward/harness/checks/outcome.py`) tests `field in payload`, so
  `{"uncertainty": None}` passes exactly as readily as a populated
  uncertainty object — `02` names this directly. One committed grid already
  exercises the gap this leaves: every other `uncertainty` payload across
  the three deep cases is a multi-key dict describing a specific caveat
  (`n_unassessed`, `reliability_gate`, `event_attribution`, …), but
  `events/ian-2022/evidence/svi_density_h3_r9_grid.geojson`'s `uncertainty`
  is `{"content": "sample density only; …"}` — one generic key holding a
  prose string, a shape no other grid in this repository uses. The check
  would pass on either shape, or on `None`; only reading the payload tells
  the difference.
- **`redact()` has no callers anywhere, including its own test file.**
  Defined at `src/geosteward/harness/publication.py:191`, a repository-wide
  `grep -rn "redact(" --include="*.py" .` turns up exactly the one line
  defining it. Redaction that actually runs is performed by
  `app/scripts/sync-artifacts.mjs`, driven by the `redact_workstation_paths`
  flag `publication.py` itself sets — `redact()` is a second, orphaned
  implementation of the same substitution. `04` and `09` give the full
  account.
- **A design record cites paths that do not exist.**
  `docs/design/specs/2026-08-20-non-retainable-evidence-design.md` refers to
  *gateway/steward.py* and *gateway/llm.py* — not a real, resolvable path in
  this repository; the real paths, used correctly everywhere in this
  manual, are `src/geosteward/gateway/steward.py` and
  `src/geosteward/gateway/llm.py`. `docs/design/` is inside
  `scripts/manual_anchors.py`'s `SKIP_PATHS` — design records intentionally
  cite planned or historical paths that would otherwise fail the gate — so
  this particular citation error is not one the gate catches.
- **The legacy typhoon modules remain wired, not retired.**
  `src/geosteward/sources/zj_typhoon.py` and `src/geosteward/hazards/
  typhoon.py` still exist and are still imported — by `agents/watcher.py`,
  `agents/exposure.py`, `agents/dossier.py`, and the archived-case tooling
  (`scripts/fetch_bavi_track.py`, `scripts/close_event.py`) — not by any of
  the three current deep-case build scripts. `docs/STATUS.md` has tracked
  this as pending since Plan 3.
- **Run grouping for pre-`run_id` logs is reconstructed, not stored.** Audit
  logs written before `AuditLog` stamped a `run_id` on every row are
  regrouped at read time by detecting a repeated first check as a restart
  boundary; those logs are append-only and are not rewritten to carry a
  `run_id` they never had.
- **`scripts/manual_anchors.py`'s CLI tests print to stdout during the
  suite.** `tests/test_manual_anchors.py` runs the checker's own command
  line, so `python -m unittest discover -s tests` prints two `N anchor(s)
  checked, N failure(s)` lines mid-run — harmless, but not the clean output
  a test suite is otherwise expected to produce.

> **中文。** **一条已经过时的声明未知项，会被检索出来、像一条当下属实、有数据支撑
> 的事实一样被引证**：`EventContext.evidence_for()`
> （`src/geosteward/gateway/context.py:144`）遍历一份档案 `declared_unknowns`
> 里的每一句话，把每一句都包进和每一条网格衍生事实完全相同的 `Fact` 类——同样有
> 可引证的制品 ID，被追加进模型据以生成回答的同一份 `evidence.facts` 列表。这个循环里
> 没有任何地方记录某句话是何时写下的，也没有检查它是否依然属实，所以在检索代码
> 眼里，一句过时的声明未知项和一句当下的声明未知项没有任何区别。这不是假设：上文
> 地理一节已经展示过，Eaton 档案在 `scripts/build_eaton_svi.py` 让那句话变假之后
> 依然声明其 SVI 联接"尚待完成"；按 `10` 章记录的方法向正在运行的网关就 Eaton 的
> 某个 tile 提一个损毁问题，得到的带引证回答会逐字重复"社会脆弱性联接尚待完成，
> 暂无脆弱性结论"。这个错误的方向是保守的，不是捏造的——agent 少报告了确实存在的
> 脆弱性数据，而不是编造了不存在的数据——但这仍然是这个以"不这样做"为存在理由的
> 系统里，那个负责问责的 agent 在向用户断言一件不真实的事。
>
> **`check_uncertainty_present` 在 `None` 值上也会通过**：这项检查
> （`src/geosteward/harness/checks/outcome.py`）判断的是 `field in payload`，所以
> `{"uncertainty": None}` 和一个内容完整的不确定性对象一样能通过——`02` 章直接点明
> 了这一点。已有一份已提交的网格实际踩在这个缺口上：三个深度案例里其余每一份
> `uncertainty` payload 都是描述某个具体注意事项的多键字典（`n_unassessed`、
> `reliability_gate`、`event_attribution` 等等），而
> `events/ian-2022/evidence/svi_density_h3_r9_grid.geojson` 的 `uncertainty` 是
> `{"content": "sample density only; …"}`——一个通用键装着一段说明性文字，这是本仓库
> 里任何其他网格都没有用过的形状。不管是这种形状还是 `None`，这项检查都会放行；只有
> 真正读取 payload 内容才能分辨出区别。
>
> **`redact()` 没有任何调用方，包括它自己的测试文件在内**：定义于
> `src/geosteward/harness/publication.py:191`，对全仓库执行
> `grep -rn "redact(" --include="*.py" .` 只能找到定义它的那一行。真正在执行的脱敏
> 由 `app/scripts/sync-artifacts.mjs` 完成，靠的是 `publication.py` 自己设置的
> `redact_workstation_paths` 标记——`redact()` 是同一次替换的第二份、无人调用的实现。
> `04`、`09` 两章有完整说明。
>
> **一份设计记录引用了并不存在的路径**：
> `docs/design/specs/2026-08-20-non-retainable-evidence-design.md` 里写的是
> *gateway/steward.py* 和 *gateway/llm.py*——在本仓库里并不是一个能解析到的真实路径；
> 本说明书其余各处一直正确使用的真实路径是 `src/geosteward/gateway/steward.py` 和
> `src/geosteward/gateway/llm.py`。
> `docs/design/` 在 `scripts/manual_anchors.py` 的 `SKIP_PATHS` 之内——设计记录本来就
> 会故意引用计划中或历史上的路径，否则会被检查判为失败——所以这一处具体的引用错误
> 不在检查能捕捉到的范围内。
>
> **遗留的台风模块仍被引用，没有退役**：`src/geosteward/sources/zj_typhoon.py` 和
> `src/geosteward/hazards/typhoon.py` 依然存在，也依然被 `agents/watcher.py`、
> `agents/exposure.py`、`agents/dossier.py`，以及已归档案例的工具脚本
> （`scripts/fetch_bavi_track.py`、`scripts/close_event.py`）导入——但不被当前三个
> 深度案例构建脚本中的任何一个使用。`docs/STATUS.md` 自 Plan 3 起就把这一项记在
> 待办里。
>
> **`run_id` 出现之前写下的日志，其运行分组是重建出来的，不是存储下来的**：早于
> `AuditLog` 给每一行盖上 `run_id` 之前写下的审计日志，靠"检测到某次运行的第一项
> 检查被重复"来推断重启边界、在读取时重新分组；这些日志是追加式的，不会被改写来
> 补上它们从未拥有过的 `run_id`。
>
> **`scripts/manual_anchors.py` 的命令行测试会在测试过程中往 stdout 打印内容**：
> `tests/test_manual_anchors.py` 直接跑这个检查脚本自己的命令行入口，所以
> `python -m unittest discover -s tests` 运行过程中会打印两行
> `N anchor(s) checked, N failure(s)`——无害，但不是一套测试套件通常应有的干净输出。

## Where to check whether this list is current

`docs/STATUS.md` is the dated ledger — done, next, blocked — and is where a
newer resolution to anything above should show up first. This chapter and
`STATUS.md` carry different jobs by design (spec §8 of
`docs/design/specs/2026-08-23-bilingual-manual-design.md`): this chapter
explains what the limits *are* and why; `STATUS.md` tracks whether each one
is still open, on a date. When the two disagree, the artifacts — the
committed data, code, and test runs — decide, the same rule
`docs/manual/README.md` states for this manual as a whole.

Two caveats about the checking itself, not about any single limit above.
First, `scripts/manual_anchors.py check` passing does not mean every path
this manual cites is still accurate — it means every path-shaped token it
found resolves on disk. Its own extraction rule rejects a token containing
whitespace, so a command-shaped inline span naming more than one path (for
instance `` `python scripts/manual_anchors.py check docs README.md` ``,
several paths in one span) is silently not checked at all, for any of the
paths inside it — this chapter and `10` were written with that hole in
mind, keeping multi-path commands in fenced code blocks and single paths in
their own inline spans wherever the anchor gate needed to actually see them,
but a future edit that puts two paths back into one backticked span will
not be caught. Second, the 134,272-file dataset-registry figure
`docs/STATUS.md` and `06` both quote could not be reconciled from artifacts in
this repository before this manual's own build: the seven frozen registry
profiles under the three events' `snapshots/registry/` sum to
approximately 130,000, roughly 4,000 short of the stated total, and `06`
states this gap plainly rather than resolving it. Treat both of these as
standing limits on how much confidence a clean check should buy, not as
defects in the specific facts they touched.

> **中文。** `docs/STATUS.md` 是带日期的台账——已完成 / 下一步 / 被阻塞——上面任何
> 一条比本章更新的进展都应该最先出现在那里。本章和 `STATUS.md` 按设计承担不同职责
> （见 `docs/design/specs/2026-08-23-bilingual-manual-design.md` 第 8 节）：本章解释
> 这些限制*是什么*、为什么存在；`STATUS.md` 按日期跟踪每一条是否仍然成立。两者有分歧
> 时，以 artifact——已提交的数据、代码与测试结果——为准，这和 `docs/manual/README.md`
> 给整份说明书定下的规则一致。
>
> 关于检查机制本身，还有两点说明，与上面任何一条具体限制无关。第一，
> `scripts/manual_anchors.py check` 跑通，并不代表本说明书引用的每一个路径至今仍然
> 准确——它只代表它找到的每一个"看起来像路径"的词元在磁盘上能解析到。它自己的提取
> 规则会拒绝任何包含空白的词元，所以一个命令形状、里面写了不止一个路径的行内代码
> 片段（比如把 `python scripts/manual_anchors.py check docs README.md` 这样的好几个
> 路径写进同一对反引号里）会被整体静默跳过，里面任何一个路径都不会被检查——本章和
> `10` 章在写作时都留意了这个漏洞，把多路径命令放进代码块、把需要真正被锚点检查看到
> 的单个路径各自放进独立的行内片段，但未来如果有编辑把两个路径重新写回同一对反引号
> 里，检查是不会发现的。第二，`docs/STATUS.md` 和 `06` 都引用的 134,272 这个数据集
> 登记表文件数，在本说明书自己动笔之前，从未在仓库里被对照 artifact 核对过：三个
> 事件 `snapshots/registry/` 下冻结的七份登记表摘要加起来约 13 万，比这个总数少了大约
> 4,000，`06` 章如实写出了这个差距，而不是替它找一个解释。请把这两点当作"一次干净的
> 检查结果本身能换来多少信心"的固有上限，而不是它们所涉及的具体事实有什么问题。
