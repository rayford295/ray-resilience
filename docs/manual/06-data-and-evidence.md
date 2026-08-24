# 06 · Data and evidence

Every other chapter in this manual describes a mechanism — the
[Steward Harness](12-glossary.md), the two policy planes, what a reader can
independently check. This chapter
describes the thing those mechanisms operate on: where every number on the
map actually comes from, what every field in every committed grid means, and
what was deliberately left out of each product rather than silently
skipped. Two evidence tiers appear below. [Tier 1](12-glossary.md) (Watch) is
one nationwide product rebuilt hourly from four keyless government feeds.
[Tier 2 and 3](12-glossary.md) (Analysis and Evidence) are tile-level
products for three real disasters, each built once from a private corpus and
then committed, hashed, and frozen. The two tiers are read the same way —
open the cited path, look at the field, read what its `uncertainty` value
says it does not support — but they are produced by entirely different
pipelines, and this chapter keeps that distinction visible throughout rather
than blurring the two into one undifferentiated "the data."

> **中文。** 本手册其余各章讲的都是机制——Steward Harness（问责框架）、两个策略
> 平面、读者能独立核实
> 到什么程度。本章讲的是这些机制作用的对象本身：地图上每一个数字究竟从哪里来，
> 每一份已提交网格里的每一个字段是什么意思，以及每份产物里哪些内容是被主动排除
> 而非疏漏掉的。下面出现两个证据层级（1/2/3 级）：1 级（Watch）是每小时从四个
> 免密钥的美国政府数据源重新构建出来的一份全国性产物；2 级和 3 级（Analysis 与
> Evidence）是针对三场真实灾害的瓦片级产物，每一份都从一个私有语料库一次性构建，
> 随后被提交、哈希、冻结。这两个层级的阅读方式是一样的——打开被引用的路径，看
> 某个字段，再看它的 `uncertainty` 值声明了这份数据不支持什么——但产出它们的流水线
> 完全不同，本章会让这个区别始终可见，而不是把两者混成一团不加区分的"数据"。

## Tier 1 — the nationwide watch

Four connectors feed the watch product, each an independent module under
`src/geosteward/sources/`, each normalizing its source into the same
`WatchEvent` shape (`src/geosteward/sources/watchbase.py`) before
`scripts/run_watch.py` merges them:

| Source | Hazard | Connector | Endpoint |
|---|---|---|---|
| `usgs` | earthquake | `src/geosteward/sources/usgs.py` | USGS all-day earthquake GeoJSON feed |
| `nws` | weather_alert | `src/geosteward/sources/nws.py` | `api.weather.gov/alerts/active`, paginated |
| `nhc` | tropical_cyclone | `src/geosteward/sources/nhc.py` | NHC `CurrentStorms.json` |
| `nifc` | wildfire | `src/geosteward/sources/nifc.py` | NIFC/WFIGS ArcGIS FeatureServer query |

`run_watch` (`scripts/run_watch.py`) calls each connector's `fetch()` then
`parse()` inside its own `try/except`; any exception — network failure,
malformed payload, or a connector's own [fail-closed](12-glossary.md) check — is caught,
recorded as `source_failed` in the run's audit log with the exception's
message, and the source is dropped from that run's `parsed` dict entirely.
`build_watch_product` (`src/geosteward/watch.py`) then reads `failures`
separately from `parsed`: a failed source gets `{"status": "failed",
"events": 0, "error": "<message>"}` in the product, never a events list
quietly left empty. Two of the four connectors carry their own fail-closed
check beyond the generic try/except, and the distinction between them and a
plain exception is worth being precise about:

- **NWS** (`src/geosteward/sources/nws.py`) pages at 500 features per
  request and follows `pagination.next` until the feed stops offering one.
  `MAX_PAGES = 10` bounds that walk; if the tenth page still has a `next`
  link, `fetch()` raises `RuntimeError("NWS pagination exceeded page cap")`
  rather than returning the ten pages it did manage to collect as if they
  were the whole list. An under-count silently presented as complete would
  be the same failure mode active-alert volume during a major multi-state
  event is most likely to trigger.
- **NIFC** (`src/geosteward/sources/nifc.py`) queries an ArcGIS
  `FeatureServer`, which answers a malformed request with HTTP 200 and a
  JSON body shaped `{"error": {"code": ..., "details": [...]}}` — no HTTP
  error, no missing-key exception, just a document with no `"features"` key.
  `raise_on_arcgis_error` inspects the payload for that `error` key before
  `parse()` ever runs, and raises rather than letting `parse()` read zero
  features and report the source as healthy. The module's own docstring
  names the failure mode this prevents: "a fail-open masked as ok."

The two checks guard against the same underlying mistake from two different
angles, and it is worth stating plainly why an error reported as an error
matters more than it might look: a hazard feed that silently returns zero
features is indistinguishable, downstream, from a hazard feed correctly
reporting that nothing is happening right now. Both render the same way on a
map — no markers — and a resident or planner reading that map has no way to
tell "checked, and there is nothing" from "did not actually check." A
connector that fails closed converts the second case into a visible,
named `source_failed` row instead, which is the only way the watch product's
own declared unknowns (below) can tell the reader the difference between an
all-clear and an outage.

`build_watch_product` (`src/geosteward/watch.py`) attaches one fixed
declared-unknown string to every run, regardless of how many hazards were
found: *"Watch data supports monitoring only; no damage or exposure
conclusions."* It appends a second line naming every currently failed
source by name when any exist, and a third line stating how many features
were not displayed — no mappable geometry (an NWS alert issued against a
forecast zone rather than a drawn polygon carries `geometry: null` by
design, per `nws.py`'s own module docstring) or a bounds check failure — so
"fewer markers than expected" is never left for the reader to notice and
wonder about unprompted.

`watch_status.json` is republished hourly to `live/products/watch_status.json`
on the `live-data` branch — a branch this one does not carry, since it is
generated output rather than committed source. Reading it fresh
(`git show origin/live-data:live/products/watch_status.json`) rather than
copying a number out of this manual or `docs/STATUS.md` gives, at the time
this chapter was written, `generated_utc: "20260824T055838Z"`: `usgs` 317
events, `nws` 28 events with 188 features skipped (no mappable geometry),
`nhc` 3 events, `nifc` 596 events — all four sources `status: "ok"`, so the
"sources currently failed" line is absent from that run's `declared_unknowns`
and only the monitoring-only string and the 188-skipped line appear. Because
the product is rebuilt hourly, a reader checking this later will see
different counts and possibly a different set of `ok` sources; the point of
citing the path rather than the numbers is that the check is repeatable, not
that these particular figures are.

> **中文。** 四个数据源连接器为监测产品供数，每个都是 `src/geosteward/sources/`
> 下一个独立模块，各自把数据源归一化成同一种 `WatchEvent` 形状
> （`src/geosteward/sources/watchbase.py`），再由 `scripts/run_watch.py` 合并：
> `usgs`（地震，USGS 逐日地震 GeoJSON 源）、`nws`（天气预警，
> `api.weather.gov/alerts/active`，分页）、`nhc`（热带气旋，NHC 的
> `CurrentStorms.json`）、`nifc`（野火，
> NIFC/WFIGS（国家跨部门消防中心野火地理服务）的 ArcGIS FeatureServer
> 查询）。`run_watch`
> （`scripts/run_watch.py`）对每个连接器各自的 `fetch()` 和 `parse()` 都单独包了一层
> `try/except`：任何异常——网络失败、载荷格式错误，或某个连接器自己的
> 失败即拒绝（fail-closed）检查——都会被捕获，连同异常信息一起记为这次运行审计日志里的
> `source_failed`，该数据源在这次运行的 `parsed` 字典里被整个丢弃。
> `build_watch_product`（`src/geosteward/watch.py`）随后把 `failures` 和 `parsed`
> 分开读取：失败的数据源在产物里得到的是
> `{"status": "failed", "events": 0, "error": "<信息>"}`，绝不会是一份被悄悄留空的
> 事件列表。四个连接器里有两个在通用的 try/except 之外还带着自己的失败即拒绝检查，
> 它们和普通异常的区别值得说清楚：**NWS**（`src/geosteward/sources/nws.py`）每页
> 500 条、沿着 `pagination.next` 一直翻页，`MAX_PAGES = 10` 给这次翻页设了上限；
> 如果第十页仍然带着 `next` 链接，`fetch()` 会直接抛出
> "NWS pagination exceeded page cap" 异常，而不是把已经翻到的十页当作完整列表
> 返回——一次重大多州事件期间预警数量激增，正是最可能触发这个上限的场景，而
> 悄悄报出一个偏低的计数正是这里要防的失败模式。**NIFC**
> （`src/geosteward/sources/nifc.py`）查询的是一个 ArcGIS FeatureServer，它对一个
> 格式错误的请求给出的应答是 HTTP 200 加一段形如
> `{"error": {"code": ..., "details": [...]}}` 的 JSON——没有 HTTP 错误，没有缺键
> 异常，只是一份没有 `"features"` 键的文档。`raise_on_arcgis_error` 在
> `parse()` 运行之前就检查载荷里有没有这个 `error` 键，一旦有就直接报错，而不是任由
> `parse()` 读出零条记录、把这个数据源标记为健康——这个模块自己的文档字符串点名了
> 这里要防的失败模式："一次被伪装成正常的失败即通过（fail-open）"。这两处检查从
> 两个不同角度防的是同一类错误，值得说清楚"把错误当错误报出来"为什么比看上去更
> 重要：一个悄悄返回零条记录的灾害数据源，在下游看来和一个如实报告"此刻确实什么都
> 没发生"的数据源毫无区别——两者在地图上渲染出来的样子完全一样（没有任何标记），
> 而看这张地图的居民或规划者完全无法分辨"查过了，确实没有"和"其实根本没查成"。
> 一个失败即拒绝的连接器把第二种情况转成一条可见的、点名的 `source_failed` 记录，
> 这正是监测产品自身的声明未知项（下文）唯一能向读者说清"一切正常"和"服务中断"之
> 区别的方式。`build_watch_product`（`src/geosteward/watch.py`）为每次运行固定附上
> 一句声明未知项，无论本次抓到多少条灾害都不例外："监测数据仅支持观察，不支持损毁
> 或暴露度结论"；只要存在当前失败的数据源，就会追加一行点名它们；还会追加一行说明
> 有多少条记录未被显示——没有可映射的几何（按 `nws.py` 自己文档字符串所说，一条
> 针对预报区域、而非具体绘制多边形发出的 NWS 预警，其 `geometry` 字段按设计就是
> `null`）或未通过边界检查——这样"标记比预期少"就不会被留给读者自己去发现和纳闷。
> `watch_status.json` 每小时重新发布到 `live-data` 分支上的
> `live/products/watch_status.json`——这个分支本身不携带这份文件，因为它是生成产物
> 而非已提交的源码。直接重新读取它（`git show
> origin/live-data:live/products/watch_status.json`），而不是照抄本手册或
> `docs/STATUS.md` 里的数字，在撰写本章时读到的是：`generated_utc` 为
> `"20260824T055838Z"`，`usgs` 317 条、`nws` 28 条（188 条因无可映射几何被跳过）、
> `nhc` 3 条、`nifc` 596 条——四个数据源全部 `status: "ok"`，所以那次运行的
> `declared_unknowns` 里没有"当前失败的数据源"这一行，只有监测专用声明和"188 条
> 被跳过"这两行。由于这份产物每小时重建一次，之后再查的读者会看到不同的计数、
> 甚至不同的健康数据源集合；引用路径而非数字本身的意义在于——这项核查是可重复的，
> 这几个具体数字则不是。

## Tier 2 and 3 — the three deep cases

Everything in this section is scoped to one of three [AOIs](12-glossary.md)
— Eaton Fire (2025), Hurricane Milton (2024), Hurricane Ian (2022) — built
once by a dedicated `scripts/build_*_case.py` script that reads a private
corpus on the maintainer's workstation and writes [H3 r9](12-glossary.md)
GeoJSON grids under `events/<event-id>/`. Every grid below carries a
`crs_declared` (or the harness's `check_crs` result recorded in that stage's
audit rows) of `EPSG:4326`, a `resolution_cap` of `tile`, and an
`uncertainty` object on every single feature — `check_uncertainty_present`
(`src/geosteward/harness/checks/outcome.py`, covered in full in
[`02`](02-harness-outcome-audit.md)) fails the build stage closed if even one
feature is missing it, so its presence is not a convention this chapter is
merely describing but a build-time guarantee. What varies case to case, and
what this chapter exists to make legible, is what each grid's fields and
each `uncertainty` object actually say.

> **中文。** 本节所有内容都限定在三个关注区域（AOI）之一内——2025 年 Eaton
> 火灾、2024 年 Milton 飓风、2022 年 Ian 飓风——分别由一个专门的
> `scripts/build_*_case.py` 脚本一次性构建，脚本读取维护者工作站上的一个私有语料库，
> 把 H3 r9（分辨率 9 级网格）GeoJSON 网格写到 `events/<event-id>/` 下。下面的每一份
> 网格都携带 `crs_declared`（或者该阶段审计记录里 `check_crs` 的结果）为
> `EPSG:4326`，`resolution_cap` 为 `tile`，并且**每一个**要素都带有一个
> `uncertainty` 对象——`check_uncertainty_present`（`src/geosteward/harness/checks/outcome.py`，
> 完整讲解见 `02`）只要发现哪怕一个要素缺失这个字段就会让构建阶段失败即拒绝，
> 所以它的存在不是本章顺带描述的一项约定，而是构建时就被保证的事实。真正因案例
> 而异、也是本章存在的意义所在的，是每份网格的字段和每个 `uncertainty` 对象具体
> 说了什么。

### Eaton Fire, 2025

**AOI** — `min_lat: 34.10, max_lat: 34.30, min_lon: -118.20, max_lon: -117.95`
(Altadena / Pasadena, Los Angeles County, CA), enforced as a `check_bounds`
outcome check against every point loaded, not merely stated in the dossier.

**Inputs** — [CAL FIRE DINS](12-glossary.md) per-class CSV exports (`Eaton_Fire_*_points.csv`,
18,428 points total: `n_none` 7,893, `n_minor` 858, `n_moderate` 148,
`n_severe` 70, `n_destroyed` 9,419, `n_unknown` 40 — the registry's own
`Eaton_Fire_profile.json` label counts, which this chapter re-summed rather
than took on faith); the `EATON_wildfire_mapillary_matched` manifest of
reliability-gated cross-view samples; and, for the SVI join,
Census 2020 tract boundaries (TIGERweb, captured for the AOI envelope) and
the CDC/ATSDR SVI 2022 California tract CSV. All three feed
`scripts/build_eaton_case.py` and `scripts/build_eaton_svi.py`, and all three
are frozen as source snapshots under `events/eaton-2025/snapshots/`.

**`dins_h3_r9_damage_grid.geojson`** (265 cells) aggregates the 18,428 DINS
points into H3 r9 cells via `src/geosteward/deepcase/dins.py`. Its fields:

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `n_structures` | DINS points aggregated into this cell |
| `n_none`, `n_minor`, `n_moderate`, `n_severe`, `n_destroyed`, `n_unknown` | count of structures at each canonical severity |
| `destroyed_rate` | `n_destroyed` divided by *assessed* structures (`n_structures − n_unknown`); `null` where every point in the cell is `Inaccessible` |
| `uncertainty` | `n_unassessed` (the cell's `n_unknown` count again, named for what it costs the rate rather than what it is), `low_n` (true when the cell has fewer than 3 structures — too few for a stable rate, and small enough to edge toward parcel identifiability), and a `source` note |

The six severity counts are CAL FIRE's own `DAMAGE` field passed through
`label_crosswalk.json`'s Eaton mapping (`No Damage → none`, `Affected (1-9%)
→ minor`, `Minor (10-25%) → moderate`, `Major (26-50%) → severe`, `Destroyed
(>50%) → destroyed`, `Inaccessible → unknown`) onto the project's canonical
`human_damage_perception` scale — a percent-loss category renamed into a
perception-scale label, which the crosswalk's own note calls "approximate"
and flags for owner review before any cross-dataset claim. The 40 points
DINS itself marked `Inaccessible` become `n_unknown`, never folded into
`none` or dropped: a structure nobody could reach is not evidence it was
undamaged, and `destroyed_rate`'s denominator excludes them for exactly that
reason. The parcel-level source points themselves are registered as a
resolution-capped lineage artifact
(`events/eaton-2025/exposure/dins_points_restricted.csv.gz`, `kind:
damage_points_restricted`) rather than shipped anywhere resident-facing;
`src/geosteward/harness/policy_v1.yaml`'s `artifact_classes` table declares
that kind `{resolution_cap: parcel, audience: lineage}`, and the
[distribution plane](12-glossary.md) (`04`) denies publishing anything at parcel resolution
regardless of what a build intended.

**`svi_h3_r9_context.geojson`** (265 cells, same count as the damage grid,
built by `scripts/build_eaton_svi.py` from the committed damage grid plus
two captured sources) adds a downscaling join on top of every damage-grid
row:

| Field | Meaning |
|---|---|
| `tract_geoid` | the Census 2020 tract the cell's centroid falls inside, by point-in-polygon (`src/geosteward/deepcase/svi.py`) |
| `RPL_THEMES` | CDC SVI 2022 overall percentile rank for that tract |
| `RPL_THEME1`–`RPL_THEME4` | the four SVI theme percentile ranks (socioeconomic status, household characteristics, racial/ethnic minority status, housing/transportation) for the same tract |
| `h3_cell`, `n_structures`, `n_destroyed`, `destroyed_rate` | carried over unchanged from the damage grid |
| `uncertainty` | the damage grid's own `uncertainty` object nested inside, plus `svi_vintage` (states the join is a 2022, pre-fire vintage attached to a tile as a downscaling approximation) and `svi_missing` (true when the assigned tract has no CDC row) |

Every one of the 265 cells resolves to one of 20 Census tracts intersecting
the AOI, and every one of those 20 tracts has a CDC SVI 2022 row —
`n_cells_svi_missing: 0` in the grid's own top-level `properties`, and
`svi_missing: false` on every feature this chapter checked. A tract-level
percentile attached to a roughly 0.1 km² tile is still an approximation
regardless of how complete the join is, which is exactly why `svi_vintage`
states it on every row rather than once in a header.

**`crossview_h3_r9_coverage.geojson`** (109 cells) is the case's Tier-3
evidence layer, built from the `EATON_wildfire_mapillary_matched` manifest —
2,244 matched cross-view samples, all 2,244 of which pass the reliability
gate (`match_quality ∈ {good, usable}`) in this manifest:

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `n_matched_samples` | gated samples aggregated into this cell |
| `labels` | a dict of native label → count (`no_or_trace_damage`, `damaged_repairable`, `destroyed`) |
| `match_quality` | a dict of quality tier → count within the cell (`good` / `usable`) |
| `uncertainty` | `reliability_gate` (states the gate condition) and a `note` |

Across the 109 cells the label totals are 1,474 `no_or_trace_damage`, 740
`destroyed`, and exactly 30 `damaged_repairable` — the `damaged_repairable`
class the case's dossier and every cell's own `uncertainty.note` both flag
by name: *"class `damaged_repairable` has n=30 overall — insufficient
statistical power; declared, not hidden."* Thirty samples spread across 109
tile-level cells is not treated as absent — the samples and their labels are
in the published grid — but no tile-level rate is claimed from that class
specifically, and the same 30 appears in the dossier's own
`declared_unknowns` for a reader who never opens the grid at all.

**Declared unknowns** (`events/eaton-2025/dossier/event_record.json`) list
three items: the 40 `Inaccessible` DINS points already covered above; the
`damaged_repairable` n=30 caveat already covered above; and *"social-vulnerability
join (SVI x exposure) pending: no vulnerability claims yet."* That third
line is stale, and this chapter says so plainly rather than repeating it:
`events/eaton-2025/exposure/svi_h3_r9_context.geojson` exists, is committed,
carries 265 features with `RPL_THEME1`–`RPL_THEME4` populated as described
above, and was built by `scripts/build_eaton_svi.py` — work the dossier's
own text still describes as not yet done. The dossier was written before
that join landed and was never revised afterward; the artifact on disk, not
the sentence in the dossier, is the current fact, and a reader relying on
this manual rather than the raw dossier file gets the corrected statement.
No file was edited to produce this correction — `event_record.json` is a
published artifact, and rewriting it retroactively would itself be a
provenance problem; the fix belongs to whoever next rebuilds the dossier
stage, and until then this manual is where the correction lives.

> **中文。** **关注区域**：`min_lat: 34.10, max_lat: 34.30, min_lon: -118.20,
> max_lon: -117.95`（加州洛杉矶县 Altadena/Pasadena），这个边界是对每一个加载进来
> 的点做 `check_bounds` 结果有效性检查强制执行的，不只是写在档案文件里的一句话。
> **输入数据**：CAL FIRE DINS（损毁勘查）按损毁等级分类导出的 CSV
> （`Eaton_Fire_*_points.csv`，
> 共 18,428 个点：无损毁 7,893、轻微 858、中等 148、严重 70、损毁 9,419、
> 不可达 40——这是登记表自己的 `Eaton_Fire_profile.json` 里的等级计数，本章重新
> 核加过、而不是直接采信）；`EATON_wildfire_mapillary_matched` 这份经可靠性筛选的
> 跨视角匹配样本清单；以及用于 SVI 联接的 Census 2020 人口普查区块边界（TIGERweb，
> 针对关注区域外包框捕获）和 CDC/ATSDR SVI 2022 加州区块 CSV。这三者都喂给
> `scripts/build_eaton_case.py` 和 `scripts/build_eaton_svi.py`，并都作为源快照冻结在
> `events/eaton-2025/snapshots/` 下。**`dins_h3_r9_damage_grid.geojson`**（265 格）
> 由 `src/geosteward/deepcase/dins.py` 把这 18,428 个 DINS 点聚合进 H3 r9 格。六个
> 损毁等级计数取自 CAL FIRE 自己的 `DAMAGE` 字段，经 `label_crosswalk.json` 里 Eaton
> 的映射规则（"无损毁"→none，"受影响（1-9%）"→minor，"轻微（10-25%）"→moderate，
> "严重（26-50%）"→severe，"损毁（>50%）"→destroyed，"不可达"→unknown）转换到本项目
> 统一的 `human_damage_perception` 标度上——这是把一个"损失百分比"等级改名成一个
> "感知等级"标签，交叉映射表自己的说明称之为"近似"，并标记为需项目负责人在任何
> 跨数据集断言之前复核。DINS 自己标记为"不可达"的 40 个点被计入 `n_unknown`，
> 从不并入 `none` 或被丢弃：一处无法实地核查的建筑，不能作为它"未受损"的证据，
> `destroyed_rate` 的分母正是因此把它们排除在外。地块级源点本身被登记为一份限定了
> 分辨率上限的溯源产物（`events/eaton-2025/exposure/dins_points_restricted.csv.gz`，
> 种类为 `damage_points_restricted`），而不会被发到任何面向居民的界面上——
> `src/geosteward/harness/policy_v1.yaml` 的 `artifact_classes` 表把这个种类声明为
> `{resolution_cap: parcel, audience: lineage}`，发布平面（`04`）会拒绝发布任何
> parcel（地块）分辨率的产物，无论构建时的本意是什么。**`svi_h3_r9_context.geojson`**
> （265 格，与损毁网格格数相同，由 `scripts/build_eaton_svi.py` 在已提交的损毁网格上
> 加两份捕获来源联接而成）在每一行损毁网格数据之上加了一层降尺度联接：`tract_geoid`
> 是该格中心点按点在多边形内判定落入的 Census 2020 区块；`RPL_THEMES` 是该区块的
> CDC SVI 2022 总体百分位排名；`RPL_THEME1`–`RPL_THEME4` 是同一区块的四个 SVI
> 主题百分位排名（社会经济地位、家庭构成、种族/族裔少数群体身份、住房与交通）；
> `uncertainty` 里嵌套了损毁网格自身的 `uncertainty` 对象，并加上 `svi_vintage`
> （声明这是把 2022 年、火灾前版本的联接结果按降尺度近似附加到一个瓦片上）和
> `svi_missing`（该格所属区块若没有 CDC 记录则为真）。265 个格全部落入与关注区域
> 相交的 20 个 Census 区块之一，这 20 个区块每一个都有 CDC SVI 2022 记录——网格
> 顶层 `properties` 里的 `n_cells_svi_missing` 为 0，本章核查过的每一个要素的
> `svi_missing` 也都是 `false`。但无论联接多完整，把一个区块级百分位排名附加到一个
> 约 0.1 平方公里的瓦片上依然是一种近似，这正是 `svi_vintage` 要在每一行都声明、
> 而不是只在表头写一次的原因。**`crossview_h3_r9_coverage.geojson`**（109 格）是
> 本案例的 3 级证据层，由 `EATON_wildfire_mapillary_matched` 清单构建——2,244 个
> 匹配的跨视角样本，这份清单里全部 2,244 个都通过了可靠性筛选门槛
> （`match_quality` 属于 `{good, usable}`）。109 个格里的标签合计为 1,474 个
> "无损毁或轻微痕迹"、740 个"已损毁"，以及恰好 30 个"可修复损毁"——这个
> `damaged_repairable` 类别在案例档案和每个格自身的 `uncertainty.note` 里都被点名：
> "`damaged_repairable` 类别总计 n=30——统计效力不足；已声明，未隐藏。"30 个样本
> 分散在 109 个瓦片级的格子里，并未被当作"不存在"处理——这些样本和它们的标签都在
> 已发布的网格里——但没有专门针对这个类别给出任何瓦片级比率结论，同样的 30 这个数字
> 也出现在档案自己的声明未知项里，供从不打开网格文件的读者看到。**声明未知项**
> （`events/eaton-2025/dossier/event_record.json`）列了三项：上文已经讲过的 40 个
> "不可达" DINS 点；上文已经讲过的 `damaged_repairable` n=30 说明；以及"社会脆弱性
> 联接（SVI×暴露度）尚待完成：暂无脆弱性结论"。第三项已经过时，本章在这里明确
> 指出，而不是照抄一遍：`events/eaton-2025/exposure/svi_h3_r9_context.geojson`
> 确实存在、已提交，携带 265 个要素、如上文所述已填充
> `RPL_THEME1`–`RPL_THEME4`，由 `scripts/build_eaton_svi.py` 构建完成——这正是
> 档案文字仍然描述为"尚未完成"的那项工作。档案是在这次联接落地之前写的，此后再未
> 更新过；磁盘上的产物、而非档案里的那句话，才是当前的事实，依赖本手册而非直接读
> 原始档案文件的读者，看到的是这里更正后的说法。这里没有为了这次更正去编辑任何
> 文件——`event_record.json` 是一份已发布的产物，事后回改它本身就会造成一个溯源
> 问题；这项修复应该留给下一次重建档案阶段的人去做，在那之前，这份更正就先记在
> 本手册里。

### Hurricane Milton, 2024

**Two AOIs, one case.** Horseshoe Beach (`min_lat: 29.35, max_lat: 29.55,
min_lon: -83.40, max_lon: -83.20`, Big Bend) carries the street-view
evidence; Pinellas County (`min_lat: 27.55, max_lat: 28.25, min_lon: -82.95,
max_lon: -82.50`) carries the debris exposure grid. `scripts/build_milton_case.py`
enforces each grid's points against its own AOI bounds independently — the
two layers are never checked against a shared box, because they cover
different ground.

**`bitemporal_h3_r9_grid.geojson`** (15 cells, Horseshoe Beach) aggregates
2,556 labeled before/after image pairs from the published Bi-Temporal
street-view set (Figshare `10.6084/m9.figshare.28801208.v2`):

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `n_samples` | labeled pairs aggregated into this cell |
| `labels` | a dict of canonical severity → count (`minor` 657, `moderate` 1,196, `severe` 703 across the 15 cells; the source's own `mild`/`moderate`/`severe` scale renamed `mild → minor` for the project's canonical labels) |
| `uncertainty` | `event_attribution` and `label_source` |

`uncertainty.event_attribution` reads *"2024-season cumulative, not
Milton-specific,"* and it is worth being exact about why that caveat sits on
every feature rather than in a header note once: the post-event imagery
underlying this grid was captured after Horseshoe Beach had already been
hit by Debby and Helene earlier in the same season, so a `severe` label on
a cell says the site shows severe damage as of the post image, not that
Milton caused it. The grid's own top-level `properties.attribution_caveat`
repeats the same statement, and the dossier's `declared_unknowns` state it a
third time — three places a reader could land and still see the same
sentence, which is the point.

**`debris_h3_r9_grid.geojson`** (5,618 cells, Pinellas County) is exposure
rather than evidence: county debris-collection program volumes joined to
Milton-specific storm covariates, from `Rayford-AI/debris-estimate`'s
`h9_debrisv6_matched_baseline_n5618.csv`, frozen as a gzip snapshot with its
own sha256 at ingest:

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `VolCD` | debris volume, construction & demolition category |
| `VolVG` | debris volume, vegetative category |
| `VolCD_sum`, `VolVG_sum` | the cell's cumulative (summed) volume in each category; `VolCD ≤ VolCD_sum` and `VolVG ≤ VolVG_sum` hold on every one of the 5,618 rows this chapter checked, so the plain and `_sum` fields are related but not identical measures — the upstream repository, not this project, defines what additional dimension the `_sum` variants accumulate over |
| `VolBoth_sum` | `VolCD_sum + VolVG_sum` exactly, verified across all 5,618 rows |
| `windgust_M`, `rainfall_M`, `dist_htrack_M` | Milton-specific wind, rainfall, and distance-to-track covariates |
| `uncertainty` | a `source` note and `missing_fields` (empty on every one of the 5,618 cells checked) |

The upstream source CSV, inspected directly rather than assumed from the
published field names alone, carries a second, unpublished set of storm
covariates suffixed `_H` alongside the `_M` (Milton) ones checked into this
grid — `windgust_H`, `rainfall_H`, `dist_htrack_H` — which this case's build
script deliberately excludes from `DEBRIS_COLUMNS`. That is the same
single-event-attribution discipline the bi-temporal grid states explicitly,
applied silently here: Pinellas County's debris volumes reflect its full
2024-season response, but only the Milton-specific covariates are published
alongside them, so a reader is not handed a second storm's wind and rainfall
figures unlabeled next to Milton's.

**GenDisasterSVI**, a third registered source, is excluded in part and
admitted in part — covered in full in
[Sources that were excluded, and why](#sources-that-were-excluded-and-why)
below, because its ruling is one this chapter treats as a case study in its
own right rather than a footnote to Milton specifically.

**Declared unknowns**
(`events/milton-2024/dossier/event_record.json`) list three items: the
Horseshoe Beach attribution caveat already covered above; *"no parcel-level
claims anywhere: all products are tile (H3 r9) resolution"*; and a
social-vulnerability join stated as pending — unlike Eaton's equivalent
line, this one is current: no SVI-joined grid exists anywhere under
`events/milton-2024/`, so nothing here corrects it.

> **中文。** **两个关注区域，一个案例。** Horseshoe Beach（`min_lat: 29.35,
> max_lat: 29.55, min_lon: -83.40, max_lon: -83.20`，Big Bend 地区）承载街景证据；
> Pinellas 县（`min_lat: 27.55, max_lat: 28.25, min_lon: -82.95, max_lon:
> -82.50`）承载清运暴露度网格。`scripts/build_milton_case.py`
> 对两份网格的坐标点分别独立按各自的关注区域边界做检查——两个图层从不放进同一个
> 外包框里核对，因为它们本来就覆盖不同的地面范围。**`bitemporal_h3_r9_grid.geojson`**
> （15 格，Horseshoe Beach）聚合了来自已发表的双时相街景数据集（Figshare
> `10.6084/m9.figshare.28801208.v2`）的 2,556 对带标签的前后影像对：15 个格上的标签
> 合计为 657 个"轻微"、1,196 个"中等"、703 个"严重"（源数据自己的
> mild/moderate/severe 标度，其中 mild 改名为项目统一标签里的 minor）。
> `uncertainty.event_attribution` 写的是"2024 年整个飓风季累计，非 Milton 特有"——
> 这条说明为什么要挂在每一个要素上、而不是只在表头写一次注释，值得讲清楚：这份
> 网格所依据的灾后影像拍摄时，Horseshoe Beach 在同一个季节里已经先后遭遇过 Debby
> 和 Helene，所以某个格上的"严重"标签说的是"该处灾后影像显示严重损毁"，而不是
> "Milton 造成了这处损毁"。网格自身顶层的 `properties.attribution_caveat` 重复了
> 同一句话，案例档案的 `declared_unknowns` 又讲了第三遍——读者无论落在哪一处，看到
> 的都是同一句话，这正是重点所在。**`debris_h3_r9_grid.geojson`**（5,618 格，
> Pinellas 县）是暴露度而非证据：把县级清运项目体量数据联接到 Milton 特有的风暴
> 协变量上，数据来自 `Rayford-AI/debris-estimate` 的
> `h9_debrisv6_matched_baseline_n5618.csv`，摄入时冻结为一份带自身 sha256 的 gzip
> 快照。`VolBoth_sum` 恰好等于 `VolCD_sum + VolVG_sum`，本章对全部 5,618 行都做了
> 核实；而 `VolCD` 与 `VolVG` 这两个"原始"字段在全部 5,618 行里都不大于各自的
> `_sum` 版本，说明二者相关但不是同一个量——`_sum` 变体究竟是在哪个额外维度上累加
> 得出的，定义权在上游那个仓库，不在本项目。直接查看了上游源 CSV 而非只凭已发布的
> 字段名猜测：源文件里还带着一整套后缀为 `_H` 的暴风协变量（`windgust_H`、
> `rainfall_H`、`dist_htrack_H`），与本网格实际收录的 `_M`（Milton）协变量并列，
> 而本案例的构建脚本刻意把它们排除在 `DEBRIS_COLUMNS` 之外——这正是双时相网格明文
> 声明的那条"单一灾害归因"纪律，在这里的一次无声应用：Pinellas 县的清运体量反映的
> 是它整个 2024 飓风季的响应，但发布出来与之并列的只有 Milton 专属的协变量，读者
> 不会拿到一份未加标注、混在 Milton 数据旁边的另一场风暴的风雨数据。**GenDisasterSVI**
> 是第三个被登记的来源，一部分被排除、一部分被采纳——完整内容见下文"被排除的数据源
> 及排除理由"一节，因为它的裁定本身值得单独当作一个案例讲清楚，而不只是 Milton
> 案例里的一条脚注。**声明未知项**（`events/milton-2024/dossier/event_record.json`）
> 列了三项：上文已讲过的 Horseshoe Beach 归因说明；"任何地方都没有地块级断言：
> 全部产物都是 H3 r9 瓦片分辨率"；以及一项声明为"尚待完成"的社会脆弱性联接——与
> Eaton 那条同类声明不同，这一条目前仍然属实：`events/milton-2024/` 下不存在任何
> 已联接 SVI 的网格，因此这里没有需要更正的地方。

### Hurricane Ian, 2022

**AOI** — `min_lat: 26.30, max_lat: 26.80, min_lon: -82.40, max_lon: -81.70`
(Fort Myers / Lee County, FL). Ian is evidence-tier only: no exposure grid
exists for this case, because no ground-truth structure-damage source
(the DINS equivalent) has been ingested — the dossier states this directly
rather than leaving a reader to notice the absence of an exposure layer on
their own.

**`crossview_h3_r9_grid.geojson`** (190 cells) is built the same way as
Eaton's crossview grid — `IAN_hurricane_mapillary_matched`, 886
reliability-gated samples (`match_quality ∈ {good, usable}`) — with the
same field shape:

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `n_samples` | gated samples aggregated into this cell |
| `labels` | a dict of canonical severity → count (`minor` 512, `moderate` 288, `severe` 86 across the 190 cells, from the source's own `0_MinorDamage` / `1_ModerateDamage` / `2_SevereDamage` scale) |
| `uncertainty` | `reliability_gate` and `label_source` |

**`svi_density_h3_r9_grid.geojson`** (413 cells) is named for the
`CVIAN_position.geojson` source file it aggregates, and that name is worth a
direct warning: despite carrying `svi` in its filename, this grid has
nothing to do with [CDC SVI](12-glossary.md) — it is 4,121 individual
street-view sample positions from the CVIAN research line, aggregated to
sample-density counts per cell, with no severity labels anywhere in it.

| Field | Meaning |
|---|---|
| `h3_cell` | H3 r9 cell index |
| `n_samples` | street-view positions aggregated into this cell |
| `labels` | always `{"svi_sample": <count>}` — a single placeholder key, not a severity histogram; it exists so this grid shares the same `labels`-dict shape as every other evidence grid in this manual, not because it carries distinct label classes |
| `uncertainty` | `content`, stating plainly that this is density only |

`uncertainty.content` reads *"sample density only; severity labels
intentionally not joined (no verifiable key) — candor over coverage,"* and
the reason is structural rather than an oversight: the 4,121 CVIAN positions
have no reliable join key back to the manifest that carries per-sample
severity labels (`pairs.csv`), so a position on this grid shows where a
street-view sample exists, never what condition it recorded. The dossier
states the same limit for a reader who never opens the grid: *"the
4,121-position layer has no verifiable per-point severity link — it shows
where evidence exists, not what it concludes."* Publishing the positions
without inventing a severity value for them is the candor choice this
project makes consistently elsewhere in this chapter (Eaton's
`damaged_repairable`, Milton's Horseshoe Beach attribution) — coverage the
grid could have claimed by joining on an unreliable key, traded for a claim
that only says what the data can actually support.

**Declared unknowns**
(`events/ian-2022/dossier/event_record.json`) list four items: the density-only
limit on the 4,121-position layer, just covered; the absence of an exposure
layer, just covered; a social-vulnerability join stated pending (current,
like Milton's — no SVI grid exists for Ian either); and the same
tile-only, no-parcel-claims statement Milton's dossier carries.

> **中文。** **关注区域**：`min_lat: 26.30, max_lat: 26.80, min_lon: -82.40,
> max_lon: -81.70`（佛罗里达州 Fort Myers / Lee 县）。Ian 只有证据层：本案例
> 没有暴露度网格，因为没有摄入任何地面实测的建筑损毁来源（相当于 DINS 的角色）——
> 档案对此直接说明，而不是让读者自己去发现"怎么没有暴露度图层"。
> **`crossview_h3_r9_grid.geojson`**（190 格）构建方式与 Eaton 的跨视角网格相同——
> 来自 `IAN_hurricane_mapillary_matched`，886 个经可靠性筛选的样本
> （`match_quality` 属于 `{good, usable}`）——字段形状也一致：190 个格上的标签
> 合计为 512 个"轻微"、288 个"中等"、86 个"严重"，取自源数据自己的
> 0_MinorDamage/1_ModerateDamage/2_SevereDamage 三级标度。
> **`svi_density_h3_r9_grid.geojson`**（413 格）之所以叫这个名字，是因为它聚合的
> 源文件是 `CVIAN_position.geojson`，这个文件名本身值得直接提醒一句：尽管文件名里
> 带着 `svi`，这份网格和 CDC SVI（社会脆弱性指数）毫无关系——它是把 CVIAN 研究
> 系列的 4,121 个独立街景采样点聚合成每格的采样密度计数，里面完全不包含任何损毁
> 等级标签。`labels` 字段固定为 `{"svi_sample": <计数>}`——一个占位用的单一键，
> 不是损毁等级直方图；它存在只是为了让这份网格和本手册里其他每一份证据网格共享
> 同样的 `labels` 字典形状，而不是因为它真的携带了不同的标签类别。
> `uncertainty.content` 写的是"仅表示样本密度；损毁等级标签故意未联接（没有可验证
> 的联接键）——坦诚优先于覆盖面"，原因是结构性的、不是疏漏：这 4,121 个 CVIAN
> 采样点没有可靠的联接键能回连到携带逐样本损毁等级标签的清单（`pairs.csv`），所以
> 这份网格上的一个点只能说明"这里存在一次街景采样"，从不说明"这次采样记录了什么
> 状况"。档案用同样的话讲给从不打开网格文件的读者听："这个 4,121 点的图层没有可
> 验证的逐点损毁关联——它只说明证据存在于何处，不说明证据能得出什么结论。"不为这些
> 采样点臆造损毁等级、原样发布，是本项目在本章其他地方也一贯做出的坦诚选择
> （Eaton 的 `damaged_repairable`、Milton 的 Horseshoe Beach 归因说明）——放弃了本可
> 通过联接一个不可靠的键换来的覆盖面，换取一条只陈述数据真正能支持之事的结论。
> **声明未知项**（`events/ian-2022/dossier/event_record.json`）列了四项：刚讲过的
> 4,121 点图层的密度限定；刚讲过的暴露度图层缺失；一项声明为"尚待完成"的社会
> 脆弱性联接（与 Milton 一样目前仍然属实——Ian 同样不存在任何 SVI 网格）；以及和
> Milton 档案相同的"仅瓦片级、无地块级断言"声明。

## The methodological lineage

`docs/methodology.md` — a pre-rework document scheduled to be archived
(a later step in this manual's own build moves it under docs/archive) —
describes a three-phase method built
for an earlier, Bavi-era case rather than for the three deep cases this
chapter has just walked through. Parts of it describe work this project has
since implemented differently, and one part describes work never
implemented at all: Phase 3's *"budget-constrained route: ordered inspection
plan under stops/distance budgets"* has no corresponding code anywhere in
`src/geosteward/` or `scripts/` today, and this manual does not claim it —
the planner mode `01` describes re-weights and ranks tiles client-side, it
does not route an inspection vehicle. What that document is right about, and
what this section absorbs before the file moves, is the intellectual lineage
behind the reliability gate every cross-view evidence grid above actually
runs:

- **Views as witnesses with different competence.** An overhead (satellite
  or aerial) view attests roof condition and inundation extent; a
  street-level view attests facade and water-line damage. Neither is a
  degraded copy of the other — they see different things, and a grid that
  privileged one uniformly over the other would be discarding evidence the
  other view alone can supply.
- **A reliability gate, not symmetric fusion.** Every crossview grid above
  gates per sample on `match_quality ∈ {good, usable}` before a sample
  contributes to a cell at all (`scripts/build_eaton_case.py`,
  `scripts/build_ian_case.py`) — an arbitration decision made per sample,
  not an average taken across every sample regardless of how well-matched
  it was.
- **Abstain plus acquire/inspect, not a forced label, where neither view can
  attest.** This project's concrete form of that principle is the density
  grids and the `unknown` severity bucket: Ian's `svi_density_h3_r9_grid.geojson`
  ships positions with no label rather than inventing one, and DINS's own
  `Inaccessible` points become `n_unknown` rather than `none`. Neither
  product forces a conclusion a view could not actually support.
- **Spatially blocked splits for anything fitted, cluster-aware
  uncertainty.** No model in any of the three deep cases is fitted and
  evaluated on the same tiles — every grid in this chapter is a direct
  aggregation of labeled or measured points, not a trained predictor scored
  against itself — so this discipline currently has nothing in this
  project's own pipeline to bind to; it is inherited principle, not yet a
  claim this manual can point at running code for.
- **Disagreement between views reported as its own layer.** None of the
  three deep cases currently publishes a dedicated cross-view disagreement
  layer; the closest analogue committed today is `match_quality` itself,
  which records how well a sample matched rather than whether two views
  disagreed about it. The principle is retained here because it is still
  the intended shape of a future evidence product, not because a grid
  matching it exists yet.

Two honesty rules this chapter has, until now, cited as
`docs/methodology.md`'s are actually written in `docs/architecture.md`, and
that correction is worth making precisely because both documents retire
soon — `docs/methodology.md` moves under docs/archive, `docs/architecture.md`
is deleted outright — and once that happens this chapter becomes the only
surviving place a reader can check which document said what.
`docs/architecture.md`'s own list, headed *"Honesty rules (inherited from
the CrossViewGate research line),"* states as its third and fourth items:
*"Unknowns are declared in every decision product, not omitted"* and *"No
damage estimate without imagery: the evidence agent raises rather than
interpolates."* Those are the two rules this chapter has been following
throughout — `uncertainty` on every feature, `declared_unknowns` on every
dossier, the fixed monitoring-only string on every watch run, and Ian's
missing exposure layer plus its unlabeled density grid — and they belong to
`docs/architecture.md`, not to `docs/methodology.md`.

`docs/methodology.md`'s own `## Claim rules` section is a separate list of
four items, and this chapter accounts for all four rather than resting on
the one it already leaned on. *"Forecast-conditioned vs observed products
are never mixed in one table"* is the rule already covered above and still
true today: no grid in this chapter blends a Tier-1 nowcast with a
Tier-2/3 observed product. *"Any statistical claim carries its
spatial-dependence treatment (block bootstrap at minimum) or is labeled
descriptive"* is inherited principle with nothing currently bound to it:
the string `bootstrap` appears nowhere under `src/geosteward/` or
`scripts/`, because none of the three deep cases fits a statistical model
at all — every value in every grid above is a direct count or ratio over
labeled or measured points, so neither branch of this rule is currently
exercised. *"Casualty/damage figures cite official releases only and carry
access dates"* is likewise unbound today: none of Eaton's, Milton's, or
Ian's dossiers states a casualty figure, and no `access_date`-shaped field
exists anywhere in the current codebase — the one case that ever reported
casualties is the archived Bavi typhoon case, outside the three this
chapter covers. *"Negative validation results (watchlist misses) are
published, not pruned"* is unbound everywhere in the repository, Bavi
included — and it is worth being precise about how that was checked, because
the phrase "a watchlist validation scorecard" appears in exactly three
places (`scripts/close_event.py`, and the closure artifacts it produced for
the archived Bavi case, `events/archive/bavi-2026/closure/event_close.json`
and `events/archive/bavi-2026/closure/CLOSURE.md`), and all three read, in
full, *"A watchlist validation
scorecard; observed damage labels are not available"* — inside a
`declared_unknowns` list, under a heading that in `CLOSURE.md` literally
reads "What This Does Not Establish." That sentence documents the
scorecard's absence, not its existence: `close_event.py` reads a final
track snapshot and writes a closure record, and scores nothing. A separate
search for scoring logic, a hit/miss table, or any comparison of a
watchlist against an outcome turns up nothing anywhere in the repository.
So this rule, like the two before it, has no code bound to it — not in any
of the three deep cases, and not in the archived Bavi case either.

> **中文。** `docs/methodology.md`——一份即将被归档的重构前文档（本手册自身构建
> 的后续一个任务会把它移到 docs/archive 目录下）——描述的是为更早的
> Bavi 时代案例搭建的一套三阶段方法，而不是本章刚刚讲过的这三个深度案例。其中一些
> 内容描述的是本项目后来用不同方式实现的工作，还有一部分描述的是根本从未实现过的
> 工作：第三阶段里"预算约束路线：在停靠点/距离预算下的有序巡查计划"，在今天的
> `src/geosteward/` 或 `scripts/` 里没有任何对应代码，本手册也不对此作出断言——
> `01` 章描述的规划者模式在浏览器端重新加权、排序瓦片，并不为巡查车辆规划路线。
> 这份文档讲对的部分、也是本节要在该文件迁移前吸收进来的部分，是上文每一份跨视角
> 证据网格实际运行的可靠性筛选背后的思想脉络：**把视角当作能力各异的证人**——
> 俯视（卫星或航拍）视角能证明屋顶状况与积水范围，街景视角能证明立面与水位线损毁；
> 两者不是彼此的低配副本，它们看到的是不同的东西，一份让某一视角一律压过另一视角
> 的网格，等于扔掉了唯有另一视角才能提供的证据。**用可靠性筛选、而非对称融合来
> 仲裁**——上文每一份跨视角网格都先按 `match_quality` 属于 `{good, usable}` 逐样本
> 筛选，样本才能计入某个格（`scripts/build_eaton_case.py`、
> `scripts/build_ian_case.py`）——这是逐样本做出的仲裁决定，而不是不论匹配程度
> 好坏、对所有样本一概取平均。**在任何一个视角都无法证明时，弃权加"待采集/待核查"
> 标记，而非强加一个标签**——本项目对这条原则的具体落地，就是密度网格和
> `unknown` 损毁等级桶：Ian 的 `svi_density_h3_r9_grid.geojson` 只发布采样点、不
> 编造标签，DINS 自己标记为"不可达"的点计入 `n_unknown` 而非 `none`。这两份产物
> 都没有强行给出一个某个视角实际上支撑不了的结论。**对任何拟合过的东西采用空间
> 分块划分、并做出对聚簇敏感的不确定性估计**——三个深度案例里没有任何一个模型是
> 在同一批瓦片上拟合又评估的——本章里的每一份网格都是对已标注或已实测点的直接
> 聚合，不是一个在自身上打分的训练出来的预测器——所以这条纪律目前在本项目自己的
> 流水线里没有可以绑定的对象；它是继承下来的原则，还不是本手册能够指向具体在跑的
> 代码去支撑的一项断言。**视角间的分歧作为独立的一层单独报告**——三个深度案例目前
> 都没有发布一个专门的跨视角分歧图层；今天已提交的最接近的对应物是
> `match_quality` 本身，它记录的是一个样本匹配得有多好，而不是两个视角是否对它
> 产生了分歧。这条原则之所以保留在这里，是因为它仍然是未来某个证据产物应有的样子，
> 而不是因为已经存在一份与之匹配的网格。本章此前一直把两条诚实规则算作
> `docs/methodology.md` 里的内容，其实它们写在 `docs/architecture.md` 里——这个
> 更正值得专门做出，正是因为这两份文档都即将退场：`docs/methodology.md` 会被移到
> docs/archive 目录下，`docs/architecture.md` 则会被直接删除；那之后，本章就成了
> 读者唯一能核对"哪句话出自哪份文档"的地方。`docs/architecture.md` 自己那份标题为
> "继承自 CrossViewGate 研究脉络的诚实规则"的清单，第三条和第四条分别写着："每一份
> 决策产物里的未知项都要被声明，不能省略"和"没有影像就没有损毁估计：证据 agent
> 遇到这种情况会报错，而不是插值填补"。本章从头到尾遵循的正是这两条规则——每个
> 要素上的 `uncertainty`、每份档案里的 `declared_unknowns`、每次监测运行里那句固定
> 的"仅支持观察"声明，以及 Ian 缺失的暴露度图层和它不带标签发布的密度网格——它们
> 属于 `docs/architecture.md`，不属于 `docs/methodology.md`。
>
> `docs/methodology.md` 自己的 `## Claim rules` 一节是另外一份独立的四条清单，
> 本章要把四条都讲清楚，而不是只靠已经用过的那一条。"预测条件下的产物和实测产物
> 从不混进同一张表"就是上文已经讲过、且今天依然成立的那条规则：本章里没有任何一份
> 网格把 1 级临近预报和 2/3 级实测产物混在一起。"任何统计断言都要携带其空间相关性
> 处理（至少是分块自助法 block bootstrap）、否则就标注为描述性结论"是继承下来的
> 原则，目前没有任何代码与之绑定：`src/geosteward/` 或 `scripts/` 下任何地方都找不到
> `bootstrap` 这个词，因为三个深度案例里没有一个真正拟合过统计模型——上文每一份
> 网格里的每一个值，都是对已标注或已实测点的直接计数或比率，这条规则的两个分支
> 目前都没有被触发过。"伤亡/损毁数字只能引用官方发布、并携带获取日期"同样目前没有
> 绑定：Eaton、Milton、Ian 三份档案里没有任何一份陈述过伤亡数字，当前代码库里也
> 找不到任何形如 `access_date` 的字段——唯一报告过伤亡数字的是已归档的 Bavi 台风
> 案例，不在本章覆盖的三个案例之内。"负面验证结果（观察名单误判）要照实发布，
> 不能剔除"这一条，在整个仓库里都没有代码与之绑定，Bavi 案例也不例外——这一点
> 值得说清楚是怎么核实的："观察名单验证记分卡"这个短语在仓库里恰好出现三次
> （`scripts/close_event.py`，以及它为已归档 Bavi 案例生成的两份收尾产物
> `events/archive/bavi-2026/closure/event_close.json` 和
> `events/archive/bavi-2026/closure/CLOSURE.md`），三处的完整原文都是"一份观察
> 名单验证记分卡；未能获得实测损毁标签"——都出现在一份 `declared_unknowns`
> 列表里，`CLOSURE.md` 里这份列表所在的标题写的就是"本产物不能确立什么"。这句话
> 陈述的是这份记分卡**不存在**，而不是它存在：`close_event.py` 读取最终的一份
> 台风路径快照并写出一份收尾记录，不做任何打分。另外单独搜索过打分逻辑、命中/
> 误判对照表，或任何"观察名单对照实际结果"的比较代码，整个仓库里都没有找到。所以
> 这一条规则和前两条一样，没有任何代码与之绑定——不论是三个深度案例，还是已归档的
> Bavi 案例。

## The dataset registry, and what cannot be rebuilt

`docs/STATUS.md` records that the dataset registry built on the maintainer's
workstation (`disaster-dataset-Yifan-all/_registry/`) carries SHA-256
checksums for **134,272 files (~33 GB)** across the local disaster datasets
that feed all three deep cases — a figure this chapter states from that
record rather than re-deriving, because the corpus it counts is not itself
in this repository to count. What *is* in this repository, and what this
chapter's own field-by-field walk above was able to check directly, is a
per-dataset summary of that registry frozen into each event at build time:
`events/<event-id>/snapshots/registry/*_profile.json`, one file per source
dataset the case actually consumed (three for Eaton, two for Milton, two for
Ian), each carrying its own `n_files_hashed` and `total_bytes` — for
example `events/eaton-2025/snapshots/registry/Eaton_Fire_profile.json`
records `"n_files_hashed": 19788` for the DINS points and their attachment
photos alone. These seven frozen profiles sum to roughly 130,000 of the
134,272 total; the remainder belongs to registry entries the three deep
cases here do not draw on, and this chapter does not guess at what they are.

Every one of those profile snapshots is committed to this repository and
readable by anyone with a clone — but committed is not the same as
published. `src/geosteward/harness/policy_v1.yaml`'s `artifact_classes`
table classifies `dataset_registry_snapshot` as `{resolution_cap: dataset,
audience: internal, license: project}`, and the distribution plane's
`deny-publish-internal-audience` rule (`04`) denies serving anything with
that `audience` value to the public site. The profiles exist in the
repository's git history for a reader auditing the build, not on the
deployed app, and the reason stated directly in the policy file's own
comment is the same reason this section exists: *"the registry profiles
describe a private 33 GB corpus, so they stay internal."*

That corpus itself — the 18,428 DINS points' source CSVs, the matched-sample
manifests, the raw imagery behind every cross-view grid — is not in this
repository and was never intended to be; `scripts/build_eaton_case.py`,
`scripts/build_milton_case.py`, and `scripts/build_ian_case.py` all take a
`--data-root` argument defaulting to a path on the maintainer's own
workstation (`disaster-dataset-Yifan-all/`), and none of the three ships a
copy of that directory anywhere in this repository. That means `events/`
**cannot be regenerated from a fresh clone** — running any of the three
build scripts today, without that private corpus, fails on a missing input
file rather than producing a plausible-looking substitute. What a third
party actually can verify, without that corpus, is threefold: the committed
artifacts themselves (every GeoJSON grid this chapter has walked field by
field); each artifact's sha256 in its event's `artifact_manifest.jsonl`
(`events/eaton-2025/artifact_manifest.jsonl`, 13 rows; Milton's, 14 rows;
Ian's, 6 rows); and each event's
`audit_log.jsonl`, the append-only record of which outcome checks ran,
against what, and whether they passed, for every stage that touched that
artifact. Reproducibility here means checking that the committed output is
what its own hash and audit trail say it is, not rerunning the pipeline that
produced it.

> **中文。** `docs/STATUS.md` 记录着：维护者工作站上构建的这份数据集登记表
> （`disaster-dataset-Yifan-all/_registry/`）为供给全部三个深度案例的本地灾害数据集
> 保存了 **134,272 个文件（约 33 GB）** 的 SHA-256 校验值——这个数字本章是从这份
> 记录里直接引用，而不是自己重新推导，因为它统计的那批语料本身根本不在本仓库里,
> 无从数起。真正在本仓库里、也是本章上文逐字段核查时能够直接核实的，是这份登记表
> 按数据集冻结进每个事件构建时的摘要：`events/<event-id>/snapshots/registry/*_profile.json`,
> 每个案例实际用到的每个源数据集各一份（Eaton 三份、Milton 两份、Ian 两份），各自
> 携带自己的 `n_files_hashed` 和 `total_bytes`——例如
> `events/eaton-2025/snapshots/registry/Eaton_Fire_profile.json` 单单为 DINS 点位
> 及其附件照片就记录了 `"n_files_hashed": 19788`。这七份冻结的摘要文件加起来约
> 13 万，占 134,272 总数的大部分；剩下的部分属于这三个深度案例没有用到的登记条目，
> 本章不对它们是什么做任何猜测。这些摘要快照文件每一份都已提交到本仓库、任何人
> clone 下来都能读到——但"已提交"不等于"已发布"。`src/geosteward/harness/policy_v1.yaml`
> 的 `artifact_classes` 表把 `dataset_registry_snapshot` 分类为
> `{resolution_cap: dataset, audience: internal, license: project}`，发布平面
> （`04`）的 `deny-publish-internal-audience` 规则会拒绝把任何带这个 `audience` 值
> 的内容发到公开网站上。这些摘要文件存在于仓库的 git 历史里，是给核查构建过程的
> 读者看的，不在已部署的应用里；策略文件自己注释里给出的理由，正是本节存在的
> 理由："这些登记表摘要描述的是一个私有的 33 GB 语料库，所以它们保持内部可见。"
> 而那个语料库本身——18,428 个 DINS 点的源 CSV、匹配样本清单、每一份跨视角网格
> 背后的原始影像——不在本仓库里，从设计上就没打算放进来；`scripts/build_eaton_case.py`、
> `scripts/build_milton_case.py`、`scripts/build_ian_case.py` 都接受一个
> `--data-root` 参数，默认指向维护者自己工作站上的一个路径
> （`disaster-dataset-Yifan-all/`），三者都没有在本仓库任何地方附带那个目录的副本。
> 这意味着 `events/` **无法从一份全新的克隆重新生成**——在没有那个私有语料库的
> 情况下，今天运行这三个构建脚本中的任何一个，都会因为缺失输入文件而失败，
> 而不会生成一份看起来说得过去的替代品。第三方在没有那个语料库的情况下真正能够
> 核实的有三样：已提交的产物本身（本章逐字段走过的每一份 GeoJSON 网格）；每个
> 产物在其事件 `artifact_manifest.jsonl` 里的 sha256（`events/eaton-2025/artifact_manifest.jsonl`
> 为 13 行；Milton 的对应文件为 14 行；Ian 的为 6 行）；以及每个事件的
> `audit_log.jsonl`——记录了针对该产物的每个处理阶段跑过哪些结果有效性检查、针对
> 什么、是否通过的只增不改的记录。这里的可复现性，指的是核对已提交的产出是否与它
> 自己的哈希和审计轨迹所声称的一致，而不是重新跑一遍生成它的那条流水线。

## Sources that were excluded, and why

**GenDisasterSVI street imagery** is the clearest exclusion in any of the
three deep cases, because the evidence for excluding it is itself
auditable rather than a judgment call taken on faith. Milton's dossier
(`events/milton-2024/dossier/event_record.json`) lists it under
`excluded_sources`: the dataset's post-event street images were generated
by InstructPix2Pix, not photographed, and the proof is in the data itself —
the registry's own `hurrican-milton-GenDisasterSVI_profile.json` was frozen
into `events/milton-2024/snapshots/registry/` specifically so that proof
travels with the case rather than living only on the maintainer's
workstation, and the dataset's own `dataset.csv` source paths reference
`experiment2_ip2p`, naming the generation method directly rather than
requiring an inference from indirect signals. `scripts/build_milton_case.py`'s
own module docstring states the rule the exclusion follows: *"candor rule
forbids generated imagery as evidence."* The registry profile carries the
tier this exclusion sits at, `generated_excluded`, so the exclusion itself
— not just its outcome — is a value another maintainer can find and check
by name, rather than a decision that happened once and left no trace.

The same dataset's 2,555 `post_sat` satellite images are a different
finding, not a partial exception carved into the same exclusion: the
dossier records that the owner confirmed these were real acquisitions on
2026-08-20, and moved them into `data_sources` rather than
`excluded_sources` — *"GenDisasterSVI post_sat satellite images (2,555;
owner-confirmed real acquisitions, ruling 2026-08-20 — usable as
evidence)."* The distinction the dossier draws is deliberately narrow: only
the street-imagery component of this one dataset is generated; its
satellite component is not, and treating an entire dataset as tainted
because one component of it failed a provenance check would throw away
evidence that passed the same check cleanly.

**The Eaton SVI join's stale declared unknown**, covered in full in this
chapter's Eaton section above, belongs here too, from the opposite
direction: it is not a source this project excluded, but a source this
project's own dossier still incorrectly describes as not yet included. A
reader checking "what was left out and how would I verify that" against the
raw dossier file alone would conclude the SVI join never happened; checking
the same claim against `events/eaton-2025/exposure/svi_h3_r9_context.geojson`
directly shows it did. The lesson this chapter draws from placing both
findings under one heading is that "excluded" and "not yet correctly
recorded as included" can look identical from a dossier's text alone, and
the only way to tell them apart is to check the artifact the dossier claims
does not exist.

**NOAA post-event orthoimagery** for Eaton (dated 2025-01-28, listed in
`events/eaton-2025/dossier/event_record.json`'s `data_sources` as
`"verified_official; imagery not committed"`) is a third, smaller case worth
naming precisely because it is neither of the two shapes above: it is not
excluded as evidence — its registry profile
(`events/eaton-2025/snapshots/registry/Altadena_Images_profile.json`)
records 91 orthoimagery tiles and 79,754 downloaded DINS attachment photos,
`evidence_tier: "verified_official"`, the same standing as the DINS points
themselves — and it is not incorrectly described as absent, either. It is
registered for lineage, at `dataset_registry_snapshot` `audience: internal`
like every other registry profile in this chapter's previous section, and
its multi-gigabyte imagery is never itself checked into any grid a reader
can open; only the DINS points derived from inspecting it are. A source
being real, verified, and cited is not the same as that source's raw
content being something this repository carries — the same distinction
`06`'s registry section draws about the corpus as a whole, here at the
level of one named imagery collection.

> **中文。** **GenDisasterSVI 街景影像**是三个深度案例里最清楚的一次排除，因为
> 排除它的证据本身是可核查的，不是一次凭信任做出的判断。Milton 的档案
> （`events/milton-2024/dossier/event_record.json`）把它列在 `excluded_sources`
> 下：这个数据集的灾后街景影像是由 InstructPix2Pix 生成的，不是实拍的，证据就在
> 数据本身里——登记表自己的 `hurrican-milton-GenDisasterSVI_profile.json` 被专门
> 冻结进了 `events/milton-2024/snapshots/registry/`，就是为了让这份证据随案例一起
> 流转，而不是只留在维护者的工作站上；数据集自己的 `dataset.csv` 源路径直接引用了
> `experiment2_ip2p`，点名了生成方法本身，而不需要靠间接信号去推断。
> `scripts/build_milton_case.py` 自己的模块文档字符串写明了这次排除所遵循的规则：
> "坦诚规则禁止把生成影像当作证据。"登记表摘要携带了这次排除所属的等级——
> `generated_excluded`——所以这次排除本身，而不只是它的结果，是任何一位维护者都能
> 按名字找到并核实的一个值，而不是一次发生过、却没留下痕迹的决定。同一个数据集里
> 的 2,555 张 `post_sat` 卫星影像是一个不同的结论，不是在同一次排除里挖出的一个
> 局部例外：档案记录着项目负责人在 2026-08-20 确认这些是真实获取的影像，并把它们
> 移入了 `data_sources` 而非 `excluded_sources`——"GenDisasterSVI 的 post_sat 卫星
> 影像（2,555 张；项目负责人确认为真实获取，裁定于 2026-08-20——可作为证据使用）"。
> 档案划的这条界线是刻意收窄的：只有这一个数据集里的街景影像部分是生成的；它的
> 卫星影像部分不是，如果因为一个数据集里某一部分未通过溯源核查就把整个数据集当作
> 受污染处理，等于把另一部分明明干净通过了同样核查的证据也一并扔掉。**Eaton SVI
> 联接那条已过时的声明未知项**，本章前面 Eaton 一节已经完整讲过，从另一个方向看
> 也属于这里：它不是本项目排除的一个来源，而是本项目自己的档案至今仍然错误地描述
> 为"尚未纳入"的一个来源。一个只依据原始档案文件去核对"哪些内容被排除在外、又该
> 如何核实"的读者，会得出"SVI 联接从未做过"的结论；直接核对
> `events/eaton-2025/exposure/svi_h3_r9_context.geojson` 就会发现它确实做过。把这两个
> 发现放在同一个标题下，本章想说明的道理是："被排除"和"已被纳入却尚未被正确记录"
> 单看档案文字可能长得一模一样，唯一的区分办法是去核对档案声称不存在的那份产物。
> **NOAA 灾后正射影像**（Eaton 案例的，拍摄于 2025-01-28，在
> `events/eaton-2025/dossier/event_record.json` 的 `data_sources` 里被列为
> "verified_official；影像本身未提交"）是第三种、规模更小、但值得专门点名的情况，
> 因为它既不属于上面两种情形中的任何一种：它没有被当作证据排除——它的登记表摘要
> （`events/eaton-2025/snapshots/registry/Altadena_Images_profile.json`）记录着 91 块
> 正射影像瓦片和 79,754 张下载的 DINS 附件照片，`evidence_tier` 同样是
> "verified_official"，和 DINS 点位本身地位相同——也没有被错误地描述为不存在。它是
> 作为溯源材料登记的，`audience` 同为 `internal`，和本章前一节里其他每一份登记表
> 摘要一样；它那几个 GB 的影像本身从未被收进任何一份读者能打开的网格里——只有
> 通过检视这些影像所得出的 DINS 点位才被收了进去。一个来源真实、经过核实、且被
> 引用，不等于这个来源的原始内容就是本仓库携带的东西——这正是本章"数据集登记表"
> 一节对整个语料库讲过的同一个区分，这里落到了一份具名影像集合的层面上。
