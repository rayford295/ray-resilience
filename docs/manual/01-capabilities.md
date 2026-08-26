# 1. Capabilities

Ten things this system does, in the order a reader meets them: a nationwide
hazard watch; three real disasters analyzed in depth; the two front-end modes
built on top of that analysis; three surfaces that make every claim checkable;
the operating properties that let the whole thing run without a key or a live
network connection; and a way to ask about a drawn rectangle rather than only
a point. Every entry carries five fields in the same order —
what it does, where it is valid, what backs it, where it is implemented, and
what it refuses — because the fifth is the point of this catalogue, not an
afterthought to it.
This project's distinguishing property is not how much it does; it is that
each thing it does has an articulated boundary of what it will not say, and
that boundary is enforced in code, not left as a caveat in prose. Where an
enforcement mechanism exists — a policy rule, a declared-unknown string, a
regex check — this chapter quotes or names it, so the refusal is something a
reader can go and find rather than take on faith.

> **中文。** 本章按读者遇到它们的顺序列出十项能力：全美灾害监测；三个被深入分析的
> 真实灾害案例；建立在这些分析之上的两种前端模式；让每条结论都可核查的三个界面；
> 让整套系统无需密钥、无需实时联网即可运行的运行特性；以及一种针对一整块画出的
> 矩形区域、而不只是单个点提问的方式。每一项都按同样的顺序携带
> 五个字段——**Does（做什么）**、**Valid where（在哪里有效）**、
> **Backed by（凭什么支撑）**、**Implemented in（代码位置）**、
> **Refuses（拒绝什么）**——因为第五项才是这份目录存在的理由，而不是聊备一格的
> 附注。这个项目最独特之处不是它做了多少事，而是它做的每一件事都有一条被写进代码而
> 非只停留在文字说明里的"拒绝边界"。凡是能找到具体执行机制的地方——一条策略规则、
> 一句声明未知项、一处正则校验——本章都会原样引用或点名它，让读者能够去核实，而不是
> 只能相信。

### 1. Nationwide Tier-1 hazard watch

**Does** — Pulls four keyless US government feeds — USGS earthquakes, NWS
active alerts (paginated, bounded, fails closed rather than silently
truncating), NHC current tropical cyclones, and [NIFC/WFIGS](12-glossary.md)
current wildfires — into one national watch product, run hourly by CI. Each
source is fetched and parsed independently; a source that fails is recorded as
`source_failed` in the run's [audit log](12-glossary.md) and reported by name,
never silently dropped or reported as "zero hazards" for that hazard type.

**Valid where** — Any US location, at any time, regardless of
[AOI](12-glossary.md) membership — the broadest scope anything in this system
has. This is [Tier 1](12-glossary.md) (Watch) on the evidence ladder.

**Backed by** — Per-source audit rows (`source_ok` / `source_failed`) written
on every run, and a [declared unknowns](12-glossary.md) list attached to the
product itself rather than left implicit.

**Implemented in** — `src/geosteward/sources/usgs.py`,
`src/geosteward/sources/nws.py`, `src/geosteward/sources/nhc.py`,
`src/geosteward/sources/nifc.py`, `scripts/run_watch.py`.

**Refuses** — Any damage or exposure conclusion from watch data. Every run of
`build_watch_product` (`src/geosteward/watch.py`) stamps the product with this
exact declared-unknown string, unconditionally, regardless of how many hazards
were mapped: *"Watch data supports monitoring only; no damage or exposure
conclusions."* The claim plane backs this at request time too — a
`damage_assessment` purpose is a different code path entirely and is never
served from watch data.

> **中文。** 本项能力每小时从四个免密钥的美国政府数据源抓取数据并合并为一份全国监测
> 产品：USGS 地震、NWS 天气预警（分页、有页数上限，一旦超出上限会主动报错拒绝，
> 而不是悄悄截断结果）、NHC 当前热带气旋，以及 NIFC/WFIGS（国家跨部门消防中心野火地理服务）当前野火
> 事件。四个数据源各自独立抓取和解析；某一个源失败时，会在本次运行的审计日志里记为
> `source_failed` 并点名该源，绝不会悄悄丢弃，也不会把"该类灾害零起"当作正常结果
> 报告出去。这项能力在全美任何地点、任何时间都有效，与关注区域（AOI）无关——是本系统
> 覆盖面最广的一项，对应证据阶梯——层级（1/2/3 级）——中的 1 级（Watch）。每次构建
> 监测产品时都会附带同一句声明未知项，无论本次抓到多少条灾害都不例外："监测数据仅支持
> 观察，不支持损毁或暴露度结论"（原文英文见左侧引用）；断言平面在请求侧也保证了这一点
> ——"损毁评估"这一请求目的走的是完全不同的代码路径，永远不会用监测数据来回答。

### 2. Three deep cases

**Does** — Builds tile-level ([H3 r9](12-glossary.md), ~0.1 km² per cell)
exposure, vulnerability, and evidence products for three real, distinct
disasters, each carried through the Steward Harness end to end:

- **Eaton Fire 2025** (Altadena/Pasadena, Los Angeles County, CA): a 265-cell
  damage grid from [CAL FIRE DINS](12-glossary.md) structure points, a
  265-cell exposure×vulnerability context grid with [CDC SVI](12-glossary.md)
  2022 ranks joined from Census tracts, and a 109-cell cross-view evidence
  coverage grid from reliability-gated matched samples.
- **Hurricane Milton 2024** (Horseshoe Beach + Pinellas County, FL): a 15-cell
  bi-temporal street-view evidence grid at Horseshoe Beach, and a 5,618-cell
  debris-exposure grid of Pinellas County debris-program volumes. The
  Horseshoe Beach post-event imagery is 2024-season cumulative (Debby +
  Helene + Milton), so damage there is **not attributable to Milton alone** —
  a caveat the case's dossier states per feature, not once in a footnote.
- **Hurricane Ian 2022** (Fort Myers, FL): a 190-cell cross-view evidence grid
  from reliability-gated matched samples, and a 413-cell street-view
  sample-density grid built from 4,121 individual positions. The density grid
  is **density only**: no verifiable per-point severity link exists between a
  position and a damage label, so none is claimed — it shows where evidence
  exists, not what it concludes.

Every count above was re-verified directly against the committed GeoJSON
(`python3 -c "import json;print(len(json.load(open(PATH))['features']))"`),
not read from `README.md` or `docs/STATUS.md`.

**Valid where** — Only inside these three AOIs. A place outside all three gets
told so, not extrapolated to.

**Backed by** — Committed, hashed H3 r9 GeoJSON grids recorded in each event's
artifact manifest, plus each event's dossier (`event_record.json`) declaring
uncertainty and gaps with the same prominence as findings. One dossier is
worth flagging here rather than silently trusting: Eaton's `event_record.json`
still lists *"social-vulnerability join (SVI x exposure) pending: no
vulnerability claims yet"* under `declared_unknowns`, but the joined artifact
it describes as pending — `events/eaton-2025/exposure/svi_h3_r9_context.geojson`,
265 cells, `RPL_THEME1`–`RPL_THEME4` populated — already exists, built by
`scripts/build_eaton_svi.py`. The dossier predates that join and was never
updated; the artifact on disk is the current fact, and this chapter describes
the artifact rather than repeating the stale sentence.

**Implemented in** — `events/eaton-2025/`, `events/milton-2024/`,
`events/ian-2022/`, `scripts/build_eaton_case.py`,
`scripts/build_milton_case.py`, `scripts/build_ian_case.py`.

**Refuses** — Analysis outside the three AOIs. A `damage_assessment` request
with `in_aoi: false` matches `deny-outside-aoi` in the [claim
plane](12-glossary.md) (`src/geosteward/harness/policy_v1.yaml`) ahead of every
other rule, and the app's own coverage lookup (capability 3) tells a resident
the same thing in plain language rather than guessing at a place it never
evaluated.

> **中文。** 本项能力为三个真实存在、彼此独立的灾害逐一建立瓦片级（H3 r9，每格约
> 0.1 平方公里）的暴露度、脆弱性与证据产品，且每个案例都完整走过一遍
> Steward Harness（问责框架）：
>
> - **2025 年 Eaton 火灾**（加州洛杉矶县 Altadena/Pasadena）：由
>   CAL FIRE DINS（损毁勘查）——加州消防局对每处建筑逐一实地核查的火后损毁
>   勘察——建筑点生成的 265 格损毁网格；一份 265 格的暴露度×脆弱性关联网格，
>   其中已从人口普查区块联接了 CDC SVI（社会脆弱性指数）——美国疾控中心/ATSDR
>   发布的社会脆弱性指数——2022 年版分位排名；以及一份基于可靠性筛选后匹配样本的
>   109 格跨视角证据覆盖网格。
> - **2024 年 Milton 飓风**（Horseshoe Beach 与 Pinellas 县，佛罗里达州）：
>   Horseshoe Beach 一份 15 格的双时相街景证据网格，以及 Pinellas 县一份 5,618
>   格的县级清运项目体量暴露度网格。Horseshoe Beach 的灾后影像是 2024 年整个飓风
>   季的累计结果（Debby + Helene + Milton 三场风暴叠加），因此那里的损毁**不能只
>   归因于 Milton**——这条说明是逐格声明的，不是脚注里的一句话。
> - **2022 年 Ian 飓风**（佛罗里达州 Fort Myers）：一份基于可靠性筛选匹配样本的
>   190 格跨视角证据网格，以及一份由 4,121 个采样点聚合而成的 413 格街景采样密度
>   网格。密度网格**只表示密度**：单个采样点与损毁等级之间不存在可验证的对应关系，
>   因此不作任何损毁结论——它只说明证据存在于何处，不说明证据能得出什么结论。
>
> 以上每个数字都是直接对已提交的 GeoJSON 文件重新计数验证过的，而不是照抄
> `README.md` 或 `docs/STATUS.md`。这项能力只在这三个关注区域（AOI）内有效，之外
> 的地方会被明确告知超出范围，而不是被外推出结论。这里要特别指出一处过时记录：
> Eaton 的 `event_record.json` 仍把"社会脆弱性联接（SVI×暴露度）尚待完成"列为
> 声明未知项，但它描述为"尚待完成"的联接产物——265 格、已填充
> `RPL_THEME1`–`RPL_THEME4` 字段的 SVI 关联网格——其实已经存在，由
> `scripts/build_eaton_svi.py` 生成；这份档案文件的文字早于该联接完成、此后未再
> 更新，本章以磁盘上的实际产物为准，而不重复这句已经过时的声明。任何"损毁评估"
> 类请求只要落在关注区域之外，就会在断言平面（`policy_v1.yaml`）里先于其他规则命中
> `deny-outside-aoi` 而被拒绝；应用自身的覆盖查询（见能力 3）也会用平实语言告诉
> 居民同样的结论，而不是对一个从未评估过的地方妄加猜测。

### 3. Resident mode

**Does** — Takes a US address, geocodes it against the free, keyless US
Census geocoder, converts the match to an H3 r9 cell, and looks that cell up
against every layer's coverage at once — not just whichever layer the map
happens to be showing — to render a plain-language dossier: what was found,
plus every applicable event's declared unknowns, shown with the same
prominence as the findings.

**Valid where** — Any address the Census geocoder can resolve; the answer is
only substantive where the cell falls inside deep-case coverage, which is why
the lookup has three outcomes rather than two (see Refuses).

**Backed by** — `buildCoverageIndex()` / `lookupCoverage()`, which index every
loaded layer's cells into one union rather than the map's currently-selected
layer. This replaced a defect fixed in the 2026-08-20 correctness pass: when
coverage was keyed by event with the last-loaded layer winning, 156 of
Eaton's 265 evaluated tiles came back as "outside the evaluated deep-case
areas" purely because a narrower layer had overwritten a wider one in the same
event — told to a resident about their own address, a confidently wrong
answer about a place the app actually had data for.

**Implemented in** — `app/src/components/ResidentPanel.jsx`,
`app/src/lib/coverage.js`.

**Refuses** — Two things, both enforced in code. First, damage assessment for
residents: a `resident` role requesting `damage_assessment` purpose matches
`deny-resident-damage-assessment` in the claim plane — residents get exposure
context and guidance, never a raw damage assessment. Second, a confident
negative for addresses it could not evaluate: `lookupCoverage()` returns one
of three states, `covered` / `not_covered` / `unknown`, and reports
`not_covered` only once every layer has actually loaded and none contains the
cell — an address whose coverage layers failed to load or have not finished
loading gets `unknown`, never a guess dressed as "outside the evaluated
areas."

> **中文。** 居民模式接收一个美国地址，交给免费、免密钥的美国人口普查局地理编码
> 服务解析，把匹配结果换算成一个 H3 r9（分辨率 9 级网格）格，然后一次性对照
> **所有**图层的覆盖范围查询这个格——而不只是地图当前正显示的那一层——最终生成一份
> 平实语言的概况：找到了什么，以及每个相关案例的声明未知项，与结论同等醒目地展示。
> 这项能力对人口普查地理编码器能解析的任何地址都可以运行，但只有落在深度案例覆盖
> 范围内的地址才会得到实质性结论，这正是查询结果被设计成三种而非两种状态的原因
> （见"拒绝什么"）。当前的实现把每个已加载图层的格子并集作为覆盖范围，用来修复
> 2026-08-20 那次正确性排查中发现的一个缺陷：此前覆盖范围按事件建索引、由最后加载
> 的图层"胜出"覆盖前面的结果，导致 Eaton 事件 265 个已评估瓦片里有 156 个被误判为
> "超出评估范围"——原因仅仅是同一事件里一个覆盖面更窄的图层覆盖掉了更宽的图层；
> 如果把这样的结论告诉一位居民本人的地址，就是对一个应用其实握有数据的地方给出了
> 一个自信的错误答案。这项能力在代码里强制拒绝两件事：其一，不对居民做损毁评估——
> 角色为 resident 且请求目的为 damage_assessment 时，会在断言平面命中
> `deny-resident-damage-assessment` 规则，居民只能得到暴露度背景与行动建议，
> 永远得不到原始损毁评估；其二，不对无法评估的地址给出自信的否定结论——覆盖查询
> 返回 `covered`（已覆盖）、`not_covered`（未覆盖）、`unknown`（未定）三态之一，
> 只有在所有图层都真正加载完成、且没有一层包含该格时才会返回"未覆盖"；只要有图层
> 加载失败或尚未加载完，结果就是"未定"，绝不会把"读不到数据"包装成"这里超出
> 评估范围"这样一句听起来像结论的话。

### 4. Planner mode with the trade-off slider

**Does** — Re-weights per-tile priority scores client-side as a planner drags
a slider: `priority = t × destroyed_rate + (1 − t) × RPL_THEMES`, recomputed
instantly (no round trip) and ranked into a top-10 list. Every slider move is
recorded to a local, session-only audit trail, and cells missing either input
are counted as partial and shown as such — a missing value contributes 0 to
the score but is declared, never silently imputed.

**Valid where** — Applies only to the "Damage × SVI priority" layer (Eaton),
inside the AOI; every other layer shows an explanatory message instead of a
slider.

**Backed by** — `priorityScores()` / `topCells()` / `recordAdjustment()`,
which score, rank, and log adjustments purely in the browser.

**Implemented in** — `app/src/components/PlannerPanel.jsx`,
`app/src/lib/data.js`.

**Refuses** — Parcel-level output at any weighting. The claim plane's
`deny-parcel-any-role` rule matches on `resolution: parcel` alone — it does
not look at role, purpose, or the slider's value — so no setting of `t` can
produce a claim finer than the H3 r9 tile the underlying grids are built at.

> **中文。** 规划者模式让规划者拖动一个滑杆，在浏览器端即时（无需请求服务器）重新
> 计算每个瓦片的优先级分数：`优先级 = t × 损毁率 + (1 − t) × SVI 综合排名`，
> 并据此排出优先级前十名列表。每一次滑杆移动都会记录到一份仅存在于当前会话、尚未
> 提交到网关的本地审计轨迹里；任一输入缺失的格子会被计入"部分评分"并明确展示——
> 缺失值在计分时按 0 处理，但这一处理会被声明出来，绝不会被悄悄当作真实值填补。
> 这项能力只对"损毁×SVI 优先级"这一图层（Eaton 事件）生效，且仅限关注区域内；
> 其他图层会显示说明文字而不是滑杆。断言平面里的 `deny-parcel-any-role` 规则只看
> `resolution: parcel` 这一个匹配条件——不看角色、不看请求目的、也不看滑杆的取值——
> 所以无论 `t` 取何值，输出精度都不可能细于底层网格本身的 H3 r9 瓦片分辨率。

### 5. Validity badges

**Does** — Shows the harness's own check results for the layer currently on
screen — e.g. "✓ latest run: 6/6 checks passed" — read live from the
committed, append-only audit log, scoped to the **latest run** of that
pipeline stage; any superseded run is shown alongside, separately, rather than
merged into the total.

**Valid where** — Any layer whose stage has audit rows in its event's
`audit_log.jsonl`.

**Backed by** — `stageValidity()`, which groups audit rows into runs using a
`run_id` where the log carries one, and a sequence-restart heuristic for
older, pre-`run_id` rows (a repeated first-check name marks a new attempt
that started over).

**Implemented in** — `app/src/components/Badges.jsx`, `app/src/lib/data.js`.

**Refuses** — Summing checks across runs. `events/eaton-2025/audit_log.jsonl`
still carries the exact run pair this bug summed over, for the
`exposure.svi_context` stage: an aborted attempt at `20260820T022423Z` logged
3 checks, one `join_integrity` check marked `"passed": false`; a successful
re-run at `20260820T022620Z` then logged 6 checks, all `"passed": true`,
closed by a `stage` row with `"status": "ok"`. The pre-2026-08-20 behaviour
summed every check row ever written for the stage (3 + 6 = 9) and took
pass/fail from the last row, rendering "✓ 9 checks passed" for a run that
never happened — no six-check run ever produced nine passing checks, and no
nine-check run ever passed outright. Correctness required stamping new audit
rows with a `run_id` so a stage's attempts stay distinguishable, and now the
badge speaks about one run because, as the code comment on `stageValidity()`
puts it, that is the only thing a count can be true of.

> **中文。** 有效性徽章把 harness 对当前所看图层的检查结果实时展示出来——例如
> "✓ 最近一次运行：6/6 项检查通过"——数据直接来自已提交、只增不改的审计日志，且只
> 统计该处理阶段**最近一次运行**；之前被取代的运行结果会另行单独展示，而不是并入
> 总数。只要一个处理阶段的事件在 `audit_log.jsonl` 里留有审计记录，这项能力就能
> 对该图层生效。其实现依据日志中的 `run_id` 字段对审计行分组；对没有
> `run_id` 的旧日志，则用"某项检查名称与本轮首项检查重名"这一启发式规则识别出
> "上一轮尝试半途夭折、新一轮重新开始"。`events/eaton-2025/audit_log.jsonl` 里
> 至今仍留着这个缺陷曾经累加过的那两次运行的原始记录，都属于
> `exposure.svi_context` 阶段：一次在 `20260820T022423Z` 中途夭折的尝试，记录了
> 3 项检查，其中一项 `join_integrity` 检查标记为 `"passed": false`；随后在
> `20260820T022620Z` 的一次成功重跑，记录了 6 项检查、全部
> `"passed": true`，并以一行 `"status": "ok"` 的 `stage` 记录收尾。2026-08-20
> 之前的行为恰恰是被拒绝的那种做法：把这个阶段历史上写过的所有检查行累加求和
> （3 + 6 = 9），再用最后一行判定通过与否——这样便显示出"✓ 9 项检查通过"，但那是
> 一次从未真实发生过的"运行"：既没有哪一次六项检查的运行产生过九项通过，也没有
> 哪一次九项检查的运行真正整体通过过。修正的办法是给新写入的审计行盖上 `run_id`，
> 让同一阶段的多次尝试彼此可区分；现在徽章只谈论"最近一次运行"，因为正如
> `stageValidity()` 代码注释所说，一个计数只能对某一次具体的运行为真。

### 6. Lineage viewer

**Does** — Shows, for the artifact behind the layer on screen, every manifest
row for it (an artifact rebuilt more than once has more than one row, oldest
to newest) — producing agent, timestamp, sha256, and up to four inputs (with
a "+N more" count) — plus the harness check pass/fail record per run from the
same audit data the validity badge reads, and any local slider adjustments
made this session.

**Valid where** — Any layer with an `artifact_manifest.jsonl` for its event.

**Backed by** — `artifactLineage()`, which matches manifest rows to the active
layer's artifact by filename.

**Implemented in** — `app/src/components/LineagePanel.jsx`.

**Refuses** — Showing full workstation paths. `src/geosteward/harness/publication.py`
declares `REDACTED_PREFIX = "<workstation>"` and a `WORKSTATION_PATH` regex
matching absolute `/Users/…`, `/home/…`, and Windows user paths; the
`redact_workstation_paths` flag it computes for the `artifact_manifest`
artifact kind is applied at sync time in `app/scripts/sync-artifacts.mjs`,
which rewrites any matching path to `<workstation>` before the manifest ever
reaches the published site the lineage viewer reads from. `verify_site()`'s
`_leaked_paths()` check enforces the boundary a second way, at deploy time: it
scans the assembled site tree for the same pattern and fails the build if any
survive. The repository's own working copy keeps full paths; only the
published copy is redacted. The sha256 is unaffected either way and remains
the verifiable anchor.

> **中文。** 溯源查看器针对当前图层背后的产物，展示它在制品清单（artifact
> manifest）里的每一行记录——若某产物被多次重建，就会有多条按时间先后排列的记录——
> 包括生成它的 agent、时间戳、sha256 哈希，以及最多四项输入（超出部分显示"还有
> N 项"）；同时展示与有效性徽章同源的、按运行分组的 harness 检查通过/失败记录，
> 以及本次会话里发生过的本地滑杆调整。只要一个事件存在
> `artifact_manifest.jsonl`，其任意图层都可以使用这项能力。这项能力被设计为**不**
> 展示完整的工作站路径：`src/geosteward/harness/publication.py` 定义了
> `REDACTED_PREFIX = "<workstation>"` 常量和一个匹配 `/Users/…`、`/home/…`
> 及 Windows 用户路径的 `WORKSTATION_PATH` 正则；它为 `artifact_manifest` 这一
> 产物类别计算出的 `redact_workstation_paths` 标志，在同步产物到发布目录时由
> `app/scripts/sync-artifacts.mjs` 实际执行替换，把匹配到的路径改写为
> `<workstation>`，然后溯源查看器读取的已发布制品清单才会生成——也就是说替换发生
> 在发布前。`verify_site()` 里的 `_leaked_paths()` 检查则是第二道防线，在部署时
> 扫描整个待发布的站点目录，一旦发现同样的路径模式残留就会让构建失败。仓库自身的
> 工作副本保留完整路径，只有发布出去的副本会被脱敏；无论是否脱敏，sha256 都不受
> 影响，始终是可验证的锚点。

### 7. The agent chat loop

**Does** — Answers a located question through one pipeline — policy pre-check
→ evidence retrieval from manifest-listed artifacts only → LLM generation →
claim post-check → audit — and always returns one of exactly four structured
response types: a cited answer, a rule-ID refusal, a declared no-evidence
response, or a declared outage (agent unavailable, or the requested live
source unavailable). Deterministic code, not the LLM, classifies the
request's purpose and resolution and verifies every draft before it is
returned; a draft that still fails after three attempts is refused rather than
relaxed.

**Valid where** — Works locally against any OpenAI-compatible endpoint
(Ollama by default, verified against `gpt-oss:20b`). It is **not hosted**: the
public site has no chat backend, and the gateway itself has no auth, rate
limiting, or log redaction yet, so it is not meant to be exposed as-is.

**Backed by** — `check_claims()`, the claim post-check that inspects the
model's draft against the evidence it was given, and the full audit trail
(`gateway_request`, `gateway_post_check`, `gateway_response` /
`gateway_refusal`) written on every path through `answer()`.

**Implemented in** — `src/geosteward/gateway/steward.py`,
`app/src/components/ChatPanel.jsx`.

**Refuses** — Six distinct violations, all caught by `check_claims()` before
an answer is returned, none of them optional: a draft failing any one is sent
back for revision, and one still failing after three attempts is refused
outright (`claim-post-check`).

1. No citations of either kind anywhere in the draft — `"no citations at
   all"`.
2. An uncited factual sentence — every sentence must carry a citation tag
   unless it matches a closed set of non-assertive forms (a question,
   imperative advice, or a statement about the answer's own declared limits)
   — `"uncited assertion: …"`.
3. A cited artifact ID not present in the evidence given to the model —
   `"fabricated citation ids: […]"`.
4. A cited live-lookup ID not present in the evidence given to the model —
   `"fabricated live citation ids: […]"`.
5. A live citation with no retained citation anywhere in the same answer —
   `"live citations with no retained citation: a non-retainable source
   cannot be the only support for an answer"`; a
   [re-derivable](12-glossary.md), non-retained source may add context to a
   retained finding, never stand in for one alone.
6. Any parcel-level statement surviving in the answer, citation or not —
   `"parcel-level statement in the answer"`. This is the same resolution
   boundary capabilities 4 and 8 enforce, appearing a third time at the point
   where the model itself speaks: a citation makes a tile-level claim
   checkable, it does not make a parcel-level claim authorized.

> **中文。** agent 对话回路沿着同一条流水线回答一个带地理位置的问题——策略预检查
> → 只从制品清单里登记过的产物中检索证据 → 大语言模型生成草稿 → 断言后检查 →
> 写入审计——并且只会返回四种结构化响应之一：带引用的回答、带规则编号的拒绝、
> 声明"无证据"、或声明系统不可用（agent 本身不可用，或所请求的实时数据源不可用）。
> 判断请求属于什么目的、什么分辨率的是确定性代码而非大模型本身；每一份草稿在返回
> 前都要经过校验，三次尝试后仍未通过就直接拒绝，而不会放宽标准迁就它。这项能力可以
> 在本地针对任意兼容 OpenAI 接口的模型服务运行（默认用 Ollama，已用 `gpt-oss:20b`
> 验证过），但**尚未对外部署**：公开网站没有配套的对话后端，网关本身也还没有鉴权、
> 限流或日志脱敏，因此不适合原样暴露给公众访问。这项能力在代码里拒绝六种不同的
> 违规，全部由 `check_claims()` 在回答返回前拦截，没有一项是可选的：任何一项没
> 通过，草稿都会被打回重写，三次尝试后仍未通过就直接拒绝（规则
> `claim-post-check`）。
>
> 1. 整份草稿完全没有任何一种引用——标记为"完全没有引用"。
> 2. 存在无引用的事实性句子——除了一个封闭的"非断言"句型集合（疑问句、行动建议、
>    关于回答自身声明局限的陈述）之外，每句话都必须带引用标签——标记为
>    "无引用断言：……"。
> 3. 引用了一个不在提供给模型的证据里的制品 ID——标记为"伪造引用 ID：[…]"。
> 4. 引用了一个不在提供给模型的证据里的实时查询 ID——标记为
>    "伪造实时引用 ID：[…]"。
> 5. 引用了实时查询却在同一份回答里没有引用任何留存产物——标记为"存在无留存引用
>    陪伴的实时引用：不可留存的来源不能单独支撑一条回答"；一个
>    可验证性（retained 留存 / re-derivable 可复现 / cited-only 仅可引证）中
>    "可复现"级别的、未被留存的来源，只能为一条已有留存证据支撑的结论补充背景，
>    不能单独撑起结论本身。
> 6. 回答中残留任何 parcel（地块）级陈述，无论是否带了引用标签——标记为
>    "回答中出现 parcel 级陈述"。这正是能力 4 与能力 8 所强制的同一条分辨率
>    边界，第三次出现在模型本身开口说话的这个环节：引用只能让一条瓦片级结论
>    变得可核查，不能让一条 parcel 级结论变得被允许。

### 8. The publication boundary

**Does** — Computes, from the [distribution plane](12-glossary.md) alone,
which committed artifacts a build may serve; writes that decision to
`publication_allowlist.json` (`plan`, with a `--check` mode that fails if the
committed allowlist has drifted from the policy); and verifies an assembled
site tree against that allowlist by set difference (`verify`) before deploy —
the gate that matters most, because it inspects what is about to ship rather
than the intent that produced it.

**Valid where** — Every artifact under `events/`, both at plan time and, more
importantly, at deploy time in CI.

**Backed by** — `DistributionPolicy`'s ordered rules and `artifact_classes`
declarations in `policy_v1.yaml`; an artifact `kind` absent from that
declaration is denied by default, so a new product cannot widen the public
surface until someone classifies it.

**Implemented in** — `scripts/publication_boundary.py`,
`src/geosteward/harness/distribution.py`.

**Refuses** — Publishing four classes of artifact, each its own rule, checked
in this order: third-party-restricted-license content
(`deny-publish-third-party-restricted`, checked first because it is a legal
constraint, not a project judgment); parcel-resolution artifacts
(`deny-publish-parcel-resolution`); internal-audience artifacts
(`deny-publish-internal-audience`, which support reproduction on the
maintainer's workstation, not publication); and lineage-audience artifacts
(`deny-publish-lineage-audience`, reachable by hash through the manifest, not
by URL). This plane exists because the claim plane alone was not enough: on
2026-08-20 a parcel-level CAL FIRE DINS source reached the public site while
satisfying every claim-plane rule, because nothing had ever claimed it — the
build simply copied it.

> **中文。** 发布边界完全依据发布平面来计算哪些已提交产物可以被一次构建对外发布，
> 把这个决定写入 `publication_allowlist.json`（`plan` 命令，另有 `--check` 模式，
> 一旦已提交的许可清单与当前策略出现偏差就会失败）；并在部署前用集合差运算
> （`verify` 命令）核对即将发布的完整站点目录是否与该许可清单一致——这才是真正
> 起作用的关卡，因为它检查的是"即将发布出去的东西"本身，而不是生成这份东西时的
> 意图。这项能力覆盖 `events/` 下的每一个产物，在规划阶段和（更重要的）CI 部署阶段
> 都会执行。它依据 `policy_v1.yaml` 里 `DistributionPolicy` 的有序规则与
> `artifact_classes` 声明来判断：一个产物种类如果没有在其中声明，就默认被拒绝
> 发布，所以新增一种产物在被人分类之前，无法扩大公开发布面。这项能力在代码里
> 拒绝发布四类产物，每类各有一条规则、按以下顺序检查：第三方限制授权内容
> （`deny-publish-third-party-restricted`，因为这是法律约束而非项目自身判断，
> 所以最先检查）；parcel（地块）级分辨率产物（`deny-publish-parcel-resolution`）；
> 仅供内部使用的产物（`deny-publish-internal-audience`，这类产物用于在维护者
> 工作站上复现结果，不用于对外发布）；以及仅供溯源使用的产物
> （`deny-publish-lineage-audience`，只能通过制品清单按哈希追溯，不能通过 URL
> 直接访问）。设立这第二道平面的原因是：仅靠断言平面并不够——2026-08-20 那次事故
> 中，一份 parcel 级的 CAL FIRE DINS 源文件在满足断言平面每一条规则的情况下依然
> 出现在了公开网站上，原因是从来没有任何规则真正"断言"过它——构建流程只是把它
> 原样复制了过去。

### 9. Offline and installable operation

**Does** — Installs as a Progressive Web App (a web manifest plus a service
worker via `vite-plugin-pwa`) and works fully offline against cached,
committed deep-case artifacts, using a stale-while-revalidate cache for
`/events/**/*.{geojson,json,jsonl}` and a cache-first, 30-day cache for
basemap tiles.

**Valid where** — Anywhere the app has been loaded once before, for maps and
analysis — no account, no API key, and no backend server required; only the
optional agent chat (capability 7) needs a locally running gateway.

**Backed by** — `vite-plugin-pwa`'s `workbox` configuration: explicit
`runtimeCaching` rules per resource type, and a keyless basemap provider
(OpenFreeMap) chosen specifically so the cache-first rule never depends on a
credential.

**Implemented in** — `app/vite.config.js`, `app/src/lib/data.js`.

**Refuses** — Nothing at runtime — this is the one capability with no request
this project's own policy turns down. But it has a deliberate cost worth
recording rather than treating as a limitation stumbled into: there is no
keyed, higher-fidelity commercial basemap option, because a keyless basemap is
a property this project claims on purpose, not a fallback it settled for.
Choosing OpenFreeMap over a keyed provider is the trade that makes "installs
and runs with no keys and no services" (`README.md`) true at all.

> **中文。** 本项能力让应用可以作为渐进式网页应用（PWA）安装——通过
> `vite-plugin-pwa` 生成网页应用清单和一个 service worker——并且在完全离线的
> 情况下依然可以使用已缓存、已提交的深度案例产物：对
> `/events/**/*.{geojson,json,jsonl}` 采用"先给旧缓存、同时后台刷新"的缓存策略，
> 对底图瓦片采用"优先用缓存"、缓存 30 天的策略。只要应用曾经被加载过一次，此后在
> 地图与分析功能上，任何地方都无需账号、无需 API 密钥、也无需后端服务器即可使用；
> 唯一的例外是可选的 agent 对话功能（见能力 7），它需要本地运行一个网关服务。
> 这项能力在运行时不拒绝任何请求——是十项能力里唯一一个"项目自身策略从不回绝"的
> 能力。但它有一个值得记录、而非被当作缺陷带过的代价：本系统没有提供需要密钥、
> 精度更高的商业底图选项，因为"无需密钥即可运行"是这个项目主动选择要具备的特性，
> 而不是退而求其次的将就。选择 OpenFreeMap 而非需要密钥的底图供应商，正是让
> `README.md` 里"无需密钥、无需任何外部服务即可安装运行"这句话成立的那个取舍。

### 10. Asking about a drawn area, not just a point

**Does** — Answers a question about a rectangle rather than only a point:
`/ask` accepts either `{lat, lon}` or `{area}` (a WGS84 bounding box), never
both and never neither (`gateway/main.py`'s `AskRequest.exactly_one_location`
validator, and the same check again inside `Steward.answer` itself). For an
area, evidence retrieval walks every deep-case AOI the rectangle touches —
`EvidenceStore.locate_area` — retrieves tile-level facts from each event
independently, and returns the H3 r9 cell IDs the answer actually drew on in
an `answer` response's `cells` field, so a client can show exactly which
tiles the words are about rather than the whole rectangle that was drawn.

**Valid where** — Wherever the rectangle intersects at least one of the three
deep-case AOIs capability 2 describes; a rectangle spanning two AOIs draws on
both, each kept as its own event with its own facts, never combined into one.

**Backed by** — `EvidenceStore.evidence_for_area()`'s per-event loop
(`src/geosteward/gateway/context.py`), which appends one "selection coverage"
fact per touched event stating how many evaluated tiles matched inside that
event's grids; and the same edge-inclusive, centre-in-box comparison
implemented twice, independently — once inside that loop, once in
`cellsInBox` (`app/src/lib/area.js`). A matching predicate on its own is not
enough to make the tile count the app shows before a question is asked agree
with the cells the answer ends up citing — both sides also have to test the
same input set, which is why `App.jsx` fetches every view's layer as soon as
planner mode is entered rather than only the one on screen: `evidence_for_area`
walks every grid of every event the selection touches, and `areaCells` has to
be the same union or the two counts can diverge even though the predicate
comparing a cell's centre to the box is identical on both sides.

**Implemented in** — `src/geosteward/gateway/context.py`,
`src/geosteward/gateway/steward.py`, `gateway/main.py`, `app/src/lib/area.js`,
`app/src/components/MapView.jsx`.

**Refuses** — Four things. A selection touching no AOI at all: `locate_area`
returns no events, `evidence_for_area` reports `in_aoi: false`, and
`deny-outside-aoi` (`purpose: damage_assessment, in_aoi: false`) denies the
request the same way it denies an out-of-AOI point (capability 2). Merged
statistics across events: each touched event keeps its own facts and its own
"selection coverage" count in the evidence block handed to the model — no two
disasters' tile counts are ever folded into one number. Anything past the
matched tiles: the "selection coverage" fact states in words that the answer
speaks only for the tiles matched inside the selection, not the whole
rectangle drawn — no coverage fraction of the drawn area is computed or
implied, because doing so would need a geometry of evaluated ground this
project does not have; `context.py`'s own comment states this reasoning
directly rather than leaving it to be inferred. And `facility_context` asked
over an area: a
rectangle has no single point for a live radius lookup, and no centroid or
other substitute stands in for one — `Steward.answer` returns a declared
`live_source_unavailable` response before ever reaching `_lookup`, checked
ahead of whether a live source is even configured, so the gap is never
latent behind a capability check.

> **中文。** 本项能力回答的是关于一整块矩形区域的问题，而不只是一个点：`/ask`
> 接口接受 `{lat, lon}` 或 `{area}`（一个 WGS84 经纬度矩形框）二者之一，绝不
> 同时给出两者，也绝不两者都不给（`gateway/main.py` 里的
> `AskRequest.exactly_one_location` 校验器，以及 `Steward.answer` 内部再次执行
> 的同一项检查）。对于一次区域提问，证据检索会遍历这个矩形所触及的每一个深度案例
> 关注区域——`EvidenceStore.locate_area`——分别独立地从每个事件里检索瓦片级事实，
> 并把这条回答实际用到的 H3 r9 格 ID 写进 `answer` 响应的 `cells` 字段，让客户端
> 能够准确展示这些话是关于哪些瓦片的，而不是整个被画出的矩形。这项能力在这个矩形
> 与能力 2 所述三个深度案例关注区域中至少一个相交的地方有效；一个跨越两个关注
> 区域的矩形会同时用到两者，各自作为独立事件、携带各自的事实，绝不合并成一个。
> 其支撑是 `EvidenceStore.evidence_for_area()`
> （`src/geosteward/gateway/context.py`）里逐事件执行的循环，它为每一个被触及的
> 事件追加一条"选区覆盖"事实，
> 说明该事件网格里有多少已评估瓦片落在选区内；以及同一个"边界计入、以格心是否落在
> 框内判断"的比较被独立实现了两次——一次在这个循环内部，一次在 `cellsInBox`
> （`app/src/lib/area.js`）里。但两边用的判断规则一致，并不足以让提问之前应用
> 展示的瓦片数量，与回答最终引用的瓦片对得上——两边还必须在同一个输入集合上做
> 判断：`evidence_for_area` 遍历的是选区触及的每一个事件的每一张网格，所以
> `App.jsx` 一进入规划者模式就把每个图层都取一遍，而不只是取当前屏幕上的那一个，
> 让 `areaCells` 覆盖同一个并集——否则哪怕判断规则完全相同，两个数字也可能对不上。
> 这项能力拒绝四件事。选区完全没有触及任何关注区域：
> `locate_area` 返回空事件列表，`evidence_for_area` 报告 `in_aoi: false`，
> `deny-outside-aoi`（匹配条件 `purpose: damage_assessment, in_aoi: false`）
> 会以拒绝一个关注区域之外的点同样的方式拒绝这次请求（见能力 2）。跨事件合并
> 统计：每个被触及的事件在交给模型的证据块里，都保留各自的事实和各自的"选区覆盖"
> 计数——两场灾害的瓦片计数永远不会被并成一个数字。超出已匹配瓦片范围的结论："选区
> 覆盖"这条事实用文字明确声明，这条回答只能代表选区内已匹配的瓦片，不代表整个被
> 画出的矩形——不计算、也不暗示所画区域的任何覆盖比例，因为这样做需要一份本项目
> 并不掌握的"已评估地面"几何数据；`context.py` 自己的注释直接写明了这个理由，而不是
> 留给读者去推断。以及对一片区域提出的 `facility_context`（设施背景）
> 问题：一个矩形没有单一的点可供实时半径查询使用，也没有用质心或其他替代物顶替这个
> 点——`Steward.answer` 会在触达 `_lookup` 之前就返回一条声明式的
> `live_source_unavailable`（实时数据源不可用）响应，且这项检查先于"是否配置了
> 实时数据源"本身，所以这个能力缺口不会藏在一项能力检查的背后不被发现。
