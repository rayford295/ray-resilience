# 08 · The front end

`app/src/App.jsx` is the one file that holds every other piece this chapter
describes: which mode is active, which layer is on screen, and what has been
fetched, failed, or is still loading. Nothing here decides what may be
claimed — the [claim plane](12-glossary.md) `03` covers does that, and the
[distribution plane](12-glossary.md) `04` covers decides what may ship at
all. What this chapter covers is narrower and more literal: what a person
sitting in front of the browser actually sees, and the specific place in the
code where the interface stops rather than implying something the harness
has not established. The logic behind every section below —
`app/src/lib/coverage.js`, `app/src/lib/watch.js`, `app/src/lib/citations.js`,
and `app/src/lib/data.js` — carries its own test file, and `npm test` (run
from `app/`) reports `Test Files  4 passed (4)`, `Tests  37 passed (37)`: 8
citation tests, 9 watch tests, 10 coverage tests, and 10 data tests, all
passing.

> **中文。** `app/src/App.jsx` 是把本章要讲的一切都攥在一起的那个文件：当前是
> 哪种模式、当前看的是哪个图层、什么已经取到、什么失败了、什么还在加载中。这里
> 不决定什么可以被断言——那是 `03` 章讲的断言平面的事——也不决定什么可以被
> 发布出去——那是 `04` 章讲的发布平面的事。本章要讲的更窄、也更实在：一个坐在
> 浏览器前的人实际会看到什么，以及代码里具体在哪个地方，界面选择停下来，而不是
> 暗示一个 harness 尚未确立的结论。下文每一节背后的逻辑——
> `app/src/lib/coverage.js`、`app/src/lib/watch.js`、
> `app/src/lib/citations.js`、`app/src/lib/data.js`——都各自带着自己的测试
> 文件，在 `app/` 目录下运行 `npm test`，输出 `Test Files  4 passed (4)`、
> `Tests  37 passed (37)`：8 个引证测试、9 个监测测试、10 个覆盖范围测试、
> 10 个数据测试，全部通过。

## Two modes, one map

`App.jsx` holds one `mode` state, `"resident"` or `"planner"`, switched by a
tab in the header; both modes share the same MapLibre GL map
(`app/src/components/MapView.jsx`) and the same layer selector, and
differ only in which panel fills the sidebar beneath it.

**Resident mode** (`app/src/components/ResidentPanel.jsx`) takes a US
address, resolves it through `geocodeAddress()`
(`app/src/lib/data.js`) — the free, keyless US Census geocoder, a US federal
government service that turns a mailing address into a coordinate pair — and
converts the match to an [H3 r9](12-glossary.md) cell. That cell is looked up
against every loaded layer's coverage at once, never just the layer the map
happens to be showing; the next section covers why that lookup has three
possible answers rather than two. A `resident` role asking for a damage
assessment is refused before it ever reaches the model — the claim plane's
`deny-resident-damage-assessment` rule, which `03` covers by rule number —
so this panel only ever states exposure context and guidance, never a raw
damage conclusion.

**Planner mode** (`app/src/components/PlannerPanel.jsx`) re-weights per-tile
priority scores with a slider, computed client-side by `priorityScores()`
and ranked by `topCells()` (both `app/src/lib/data.js`):
`priority = t × destroyed_rate + (1 − t) × RPL_THEMES`, recomputed instantly
with no round trip to any server. This only applies to the "Damage × SVI
priority" layer (`eaton-priority`); every other layer shows an explanatory
message instead of a slider, because the underlying grids for those layers
carry no comparable damage-and-vulnerability pair to re-weight. A cell
missing either input scores that side as 0 but is counted as partially
scored, not silently treated as zero risk — the panel states the count of
partially-scored tiles directly. Every drag calls `recordAdjustment()`
(`app/src/lib/data.js`), which appends to an in-memory array and stamps each
entry `"delivery": "session-only; not persisted and not sent to the
gateway"` — the panel's own text says the same thing: "every move is
audit-logged (local until the gateway ships)". Reloading the page discards
it; nothing here writes to disk or to the gateway. No slider position widens
what the layer can claim, either: the claim plane's `deny-parcel-any-role`
rule matches on resolution alone, so no value of `t` produces an output
finer than the H3 r9 tile the grid was built at.

Planner mode also carries a draw tool the resident mode does not: shift-drag
on the map (`app/src/components/MapView.jsx`) draws a rectangle instead of
panning, normalised into a WGS84 bounding box by `bboxFromCorners()`
(`app/src/lib/area.js`) and handed up as `selection` state in `App.jsx`. With
a selection active, the chat panel's header
(`app/src/components/ChatPanel.jsx`) switches from "about the map center" to
"about the selected area," names the box's corners, and states a live count
of evaluated cells
inside it — computed by `cellsInBox()` (`app/src/lib/area.js`) against the
same edge-inclusive, centre-in-box rule the gateway applies server-side. That
shared rule is necessary but not sufficient: it also has to run over the same
tiles the gateway sees, so entering planner mode fetches every view's layer
(`App.jsx`), not only the one on screen — `evidence_for_area` walks every grid
of every event a selection touches, and the app's own cell union has to match
that reach for the number shown before asking to agree with the tiles the
answer ends up citing. `App.jsx` restricts the draw tool to planner mode only —
residents' damage questions are refused whether asked by point or by area, so
offering the affordance would just invite a refusal they cannot use — and
drops any active selection the moment the mode switches away from planner.
Once an `answer` response comes back, its `cells` field (capability 10 in
`01`) is lifted into `App.jsx`'s own state and drawn by `MapView.jsx` as a
highlight layer above whichever grid is on screen, independent of the active
layer's own geometry — the highlight is built straight from the cell IDs via
H3's own cell-to-boundary conversion, not filtered out of the visible grid,
so it still renders correctly for a selection that spans an event the map
happens not to be showing. A refusal, a declared no-evidence response, or a
declared outage carries no `cells`, and the panel clears the highlight on
every one of those responses rather than leaving the previous answer's tiles
lit beside a refusal that was never about them.

Both modes share three more things beneath the panel: the tile detail view
(properties of whatever feature was last clicked on the map, plus its
mandatory `uncertainty` field verbatim), the chat panel covered in
[Citations, and how a live chip differs](#citations-and-how-a-live-chip-differs)
below, and the lineage toggle covered in
[Validity badges and the lineage panel](#validity-badges-and-the-lineage-panel).
The map itself is built on MapLibre GL against the OpenFreeMap `liberty`
style (`app/src/components/MapView.jsx`) — a keyless, open basemap. That
choice, and what it costs and buys, is covered in full where the caching
strategy that makes it work offline is covered:
[Artifacts are vendored at build time](#artifacts-are-vendored-at-build-time).

> **中文。** `App.jsx` 里维护着一个 `mode` 状态，取值为 `"resident"`（居民）或
> `"planner"`（规划者），由页头的一个切换按钮控制；两种模式共享同一张
> MapLibre GL 地图（`app/src/components/MapView.jsx`）和同一个图层选择器，
> 区别只在于地图下方侧栏里显示哪一个面板。**居民模式**
> （`app/src/components/ResidentPanel.jsx`）接收一个美国地址，交给
> `geocodeAddress()`（`app/src/lib/data.js`）解析——这是免费、免密钥的美国
> 人口普查局地理编码服务，一个美国联邦政府服务，把一个通讯地址转换成一对
> 坐标——再把匹配结果换算成一个 H3 r9（分辨率 9 级网格）格。这个格会一次性对照
> **所有**已加载图层的覆盖范围查询，而不只是地图当前正显示的那一层；下一节讲
> 为什么这次查询会有三种而非两种可能的答案。角色为 resident 且请求损毁评估的
> 请求，还没到达模型就会被拒绝——断言平面里的 `deny-resident-damage-assessment`
> 规则，具体规则编号 `03` 章讲过——所以这个面板只会陈述暴露度背景与行动建议，
> 永远不给出原始的损毁结论。**规划者模式**
> （`app/src/components/PlannerPanel.jsx`）用一个滑杆重新计算每个瓦片的
> 优先级分数，由 `priorityScores()` 计算、`topCells()` 排序（均在
> `app/src/lib/data.js`）：`优先级 = t × 损毁率 + (1 − t) × SVI 综合排名`，
> 即时重算，不需要请求任何服务器。这只对"损毁×SVI 优先级"这一图层
> （`eaton-priority`）生效；其他图层会显示一段说明文字而不是滑杆，因为那些图层
> 底层的网格并不携带可供重新加权的、可比的损毁-脆弱性配对。任一输入缺失的格子
> 会把那一侧按 0 计分，但会被计入"部分评分"，而不是被悄悄当作零风险——面板会
> 直接说明有多少瓦片属于部分评分。每一次拖动都会调用 `recordAdjustment()`
> （`app/src/lib/data.js`），它把记录追加到一个仅存在于内存的数组里，并给每条
> 记录盖上 `"delivery": "session-only; not persisted and not sent to the
> gateway"`（仅限本次会话；不持久化，也不发送到网关）——面板自己的文字说的是
> 同一件事："每一次移动都会被审计记录（在网关就绪之前，仅保存在本地）"。刷新
> 页面就会丢失这些记录；这里的任何东西都不会写入磁盘或网关。滑杆的任何取值也
> 不会扩大图层能断言的精度：断言平面里的 `deny-parcel-any-role` 规则只看分辨率
> 本身，所以无论 `t` 取何值，输出精度都不可能细于该网格本身构建时所用的
> H3 r9 瓦片。
>
> 规划者模式还带有一个居民模式没有的绘制工具：在地图上按住 Shift 拖拽
> （`app/src/components/MapView.jsx`）会画出一个矩形而不是平移地图，由
> `bboxFromCorners()`（`app/src/lib/area.js`）归一化成一个 WGS84 经纬度矩形框，
> 并作为 `selection` 状态交给 `App.jsx`。一旦存在选区，对话面板的提示语
> （`app/src/components/ChatPanel.jsx`）会从"about the map center"（关于地图
> 中心点）切换成"about the selected area"（关于所选区域），点名矩形的两个角
> 坐标，并实时给出选区内已评估瓦片的数量——由 `cellsInBox()`
> （`app/src/lib/area.js`）计算，用的是与网关服务端完全相同的"边界计入、以格心
> 是否落在框内判断"规则。但规则相同还不够，还得作用在同一批瓦片上：一进入规划者
> 模式，`App.jsx` 就会把每个图层都取一遍，而不只是当前屏幕上的那一个——
> `evidence_for_area` 遍历的是选区触及的每一个事件的每一张网格，应用这边的瓦片
> 并集必须覆盖同样的范围，提问之前展示的数字才会和回答最终引用的瓦片对得上。
> `App.jsx` 把这个绘制工具限定在规划者模式内——居民无论按点还是按区提问
> 损毁评估都会被拒绝，提供这个功能只会引来一个他们用不上的拒绝——并且一旦模式切出
> 规划者，就会立即丢弃任何激活中的选区。一旦一条 `answer`（回答）响应返回，它的
> `cells` 字段（`01` 章能力 10）会被提升进 `App.jsx` 自己的状态，并由
> `MapView.jsx` 在当前屏幕上无论显示哪个网格之上，都绘制成一个高亮图层——这个
> 高亮直接由格 ID 通过 H3 自身的"格转边界"换算构建出来，而不是从可见网格里筛选
> 出来的，所以哪怕选区跨到了地图当前并未展示的某个事件，也依然能正确渲染。一次
> 拒绝、一次声明式的无证据响应，或一次声明式的系统不可用响应都不携带 `cells`，
> 面板会在这些响应的每一种上清空高亮，而不是让上一条回答的瓦片继续亮着，好像和
> 一条与它们毫不相干的拒绝有关系似的。
>
> 两种模式在面板下方还共享三样东西：瓦片详情视图（最近一次点击的
> 地图要素的属性，外加其强制性的 `uncertainty` 字段原文）、下文
> "Citations, and how a live chip differs" 一节讲的对话面板，以及
> "Validity badges and the lineage panel" 一节讲的溯源开关。地图本身建立在
> MapLibre GL 之上，使用 OpenFreeMap 的 `liberty` 样式
> （`app/src/components/MapView.jsx`）——一个免密钥的开放底图。这个选择的
> 代价与收益，会和让它离线可用的缓存策略一起，放在本章末节
> "Artifacts are vendored at build time" 里讲。

## The layer catalogue

`app/src/lib/views.js` is the whole map layer catalogue: one committed
artifact maps to one map layer, and nothing in the app invents a layer that
is not listed here. It exports three things. `EVENTS` is a record of the
three disasters (`eaton-2025`, `milton-2024`, `ian-2022`), each with a
title, a map center and zoom for its "fly to" default, and the three paths
every event carries — its dossier record, its artifact manifest, and its
audit log. `VIEWS` is an array of seven layer entries, each naming its
event, its display label, the URL of the committed GeoJSON it draws, a
`stage` string that ties it to that event's audit rows (used by the validity
badge, next section), a `kind` that selects how `MapView.jsx` paints it
(`priority`, `rate`, `count`, or `volume`), and a [tier](12-glossary.md)
number. `RAMP` is the six-color scale every choropleth interpolates across.
The layer dropdown in the sidebar groups these seven entries by event, using
`EVENTS`'s titles as group labels.

A layer that fails to load is rendered as a declared failure, not an empty
map: `App.jsx`'s fetch effect catches the error and stores
`{ error: String(err) }` in place of the GeoJSON, and the sidebar shows
"layer failed to load" with the error text rather than silently drawing
nothing.

> **中文。** `app/src/lib/views.js` 就是完整的地图图层目录：每一份已提交的产物
> 对应一个地图图层，应用里不会凭空生出一个不在这里登记过的图层。它导出三样
> 东西。`EVENTS` 是三场灾害（`eaton-2025`、`milton-2024`、`ian-2022`）的记录，
> 每一条都带标题、"飞向"默认视角的地图中心与缩放级别，以及每个事件都携带的三个
> 路径——它的档案记录、制品清单、审计日志。`VIEWS` 是一个包含七条图层记录的
> 数组，每一条都写明所属事件、展示标签、它绘制的已提交 GeoJSON 的地址、一个把
> 它和该事件审计记录关联起来的 `stage` 字符串（下一节讲的有效性徽章要用到）、
> 一个决定 `MapView.jsx` 如何上色的 `kind`（`priority`、`rate`、`count` 或
> `volume` 之一），以及一个层级（1/2/3 级）编号。`RAMP` 是每一张分级设色图都会
> 在其间插值的六色色阶。侧栏里的图层下拉菜单把这七条记录按事件分组，用
> `EVENTS` 里的标题作为分组标签。一个加载失败的图层会被渲染成一个明确声明的
> 失败，而不是一张空地图：`App.jsx` 的抓取逻辑会捕获错误，把
> `{ error: String(err) }` 存到本该放 GeoJSON 的位置，侧栏会显示"图层加载
> 失败"并附上错误文字，而不是悄悄画出什么都没有的地图。

## Coverage has three states, not two

A resident's coverage lookup resolves to one of three states —
`covered`, `not_covered`, or `unknown` — returned by `lookupCoverage()`
against an index built by `buildCoverageIndex()` (both
`app/src/lib/coverage.js`). `buildCoverageIndex()` takes every layer the app
has attempted to load — loaded, failed, or not yet requested — and folds
every loaded layer's cells into one union map from H3 cell to the list of
layers that cover it, keyed across the whole catalogue rather than any one
event or any one layer. `eventsOf()` reads the distinct events out of a set
of hits, and `mergedProps()` merges every hit's properties into one object
for display, so an address covered by more than one layer shows facts from
all of them at once.

The third state exists because of a specific, already-fixed defect. Coverage
used to be indexed by event, with each event's layers loaded into the same
map in catalog order — so within one event, a narrower layer overwrote a
wider one rather than adding to it. Eaton's catalog order ends on its
109-cell cross-view evidence coverage grid, so 156 of the 265 tiles the
event had actually evaluated (both its damage grid and its exposure×SVI
context grid carry 265 cells) came back as "outside the evaluated deep-case
areas" purely because the narrower grid had overwritten the wider one in
the same event's map — a resident asking about their own,
already-evaluated address would have been told, confidently, that it fell
outside coverage. `app/src/lib/coverage.js` carries this history directly in
its own comments, and `app/src/lib/coverage.test.js` pins the fixed
behavior down with a test built from the exact shape of the bug: a wide
damage grid and a narrow evidence grid over the same event, and an
assertion that both contribute cells to the union.

`lookupCoverage()` returns `covered` the moment any loaded layer contains
the cell — a hit from one layer is never retracted by another layer that
failed to load. It returns `not_covered` only once every layer has loaded
and none of them contains the cell — the honest statement that the app's
competence is conditional on place. It returns `unknown` when the cell
matched nothing but some layer is still unread or failed to load
(`index.complete` is false) — an admission that the app has not yet looked
everywhere, not a claim about what it would find if it had. So a `not_covered`
result does not mean the address is safe; `ResidentPanel.jsx` states this
directly — "Ray Resilience makes no damage or vulnerability claims here" — and
neither this app nor `03`'s claim plane treats absence of deep-case coverage
as evidence of anything. An `unknown` result means the app genuinely does
not know yet, and says so rather than guessing at "outside," which is the
exact failure the fix above closed.

> **中文。** 一次居民覆盖查询会得到三种结果之一——`covered`（已覆盖）、
> `not_covered`（未覆盖）、`unknown`（未定）——由 `lookupCoverage()` 返回，
> 查询对象是 `buildCoverageIndex()` 构建的索引（均在
> `app/src/lib/coverage.js`）。`buildCoverageIndex()` 接收应用尝试加载过的
> 每一个图层——已加载的、加载失败的、尚未请求的——把每一个已加载图层的格子
> 折叠进同一张"H3 格 -> 覆盖它的图层列表"的并集地图里，这个索引横跨整个目录，
> 而不是按某一个事件或某一个图层分别建索引。`eventsOf()` 从一组命中记录里取出
> 不重复的事件，`mergedProps()` 把一组命中记录的属性合并成一个对象用于展示，
> 所以一个被多个图层覆盖的地址会一次性展示所有图层的事实。第三种状态的存在，
> 源于一处具体的、已经修复的缺陷。覆盖范围以前是按事件建索引的，同一事件的
> 各图层按目录顺序加载进同一张地图——于是同一事件内，一个覆盖面更窄的图层会
> 覆盖掉一个更宽的图层，而不是与它相加。Eaton 事件在目录顺序里排在最后的是它
> 109 格的跨视角证据覆盖网格，于是这个事件实际评估过的 265 个瓦片（它的损毁网格
> 与暴露度×SVI 关联网格都是 265 格）里，有 156 个仅仅因为同一事件的地图里窄
> 图层覆盖掉了宽图层，就被误判为"超出
> 评估范围"——如果一位居民查询自己那个其实已被评估过的地址，得到的会是一个
> 自信的错误答案。`app/src/lib/coverage.js` 的注释里直接记录了这段历史，
> `app/src/lib/coverage.test.js` 用一个按照缺陷原型构造的测试把修复后的行为
> 钉了下来：同一事件里一个宽的损毁网格和一个窄的证据网格，断言两者都要为并集
> 贡献格子。`lookupCoverage()` 只要有任何一个已加载图层包含该格，就立即返回
> `covered`——一个图层的命中不会被另一个加载失败的图层撤销。只有当所有图层都
> 已加载、且没有一个包含该格时，才会返回 `not_covered`——这是"本应用的能力
> 因地而异"这句诚实陈述。当该格什么都没匹配上、但仍有图层未读到或加载失败时
> （`index.complete` 为假），会返回 `unknown`——这是承认应用还没能看遍所有地方，
> 而不是对"看遍之后会发现什么"下结论。所以 `not_covered` 的结果并不意味着这个
> 地址是安全的；`ResidentPanel.jsx` 直接写明了这一点——"Ray Resilience 在这里不作
> 任何损毁或脆弱性方面的断言"——这个应用和 `03` 章讲的断言平面都不会把"没有
> 深度案例覆盖"当作能说明任何事情的证据。`unknown` 的结果意味着应用确实还不
> 知道，它会如实说出来，而不是去猜"超出范围"——而这正是上面那处修复所堵住的
> 那个失败。

## The watch badge reports what it dropped

`watchSummary()` (`app/src/lib/watch.js`) merges the live nationwide watch
layer with its own status product into one summary for
`app/src/components/Badges.jsx`'s `LiveWatchBadge`. It reports `mapped` (the
count of features actually drawn), `undisplayed` (parsed out of the status
product's `declared_unknowns` list, matched against the one prose shape the
pipeline emits: `"N feature(s) not displayed…"`), `total` (mapped plus
undisplayed, or `null` if either half is unavailable), the full list of
`unknowns` for display, and any per-source `failedSources`.

The reason the badge shows a fraction rather than one number: it used to
show only `mapped`, unconditionally, as if that were the complete hazard
count. `app/src/lib/watch.js`'s own comment and
`app/src/lib/watch.test.js` pin down the exact pre-fix behavior with real
figures — the badge read "882 active hazards" while the watch pipeline's own
`watch_status.json` had, in the same run, declared 198 more features it had
fetched and then dropped for want of usable geometry, for a true total of
1,080. The status product already stated this; nothing in the app read it.
Counting what a pipeline drops and then displaying only what it kept is a
quieter version of fabricating a layer, and the same kind of failure: the
number shown looks complete when it is not. `LiveWatchBadge` now renders
`{mapped} hazards mapped of {total}` whenever the two halves disagree, and a
second badge names the undisplayed count directly rather than folding it
into the first number. When the status product itself cannot be read,
`watchSummary()` returns `total: null` rather than assuming the mapped count
is the whole count, and the badge says "completeness unknown" instead of
presenting a partial number as final.

> **中文。** `watchSummary()`（`app/src/lib/watch.js`）把实时的全国监测图层和它
> 自己的状态产物合并成一份摘要，供 `app/src/components/Badges.jsx` 里的
> `LiveWatchBadge` 使用。它给出 `mapped`（实际画出的要素数）、`undisplayed`
> （从状态产物的 `declared_unknowns`（声明未知项）列表里解析出来，匹配流水线
> 唯一会输出的那种文字形状："N feature(s) not displayed…"）、`total`
> （mapped 加 undisplayed，若任一半缺失则为 `null`）、供展示用的完整
> `unknowns` 列表，以及按数据源列出的 `failedSources`。徽章之所以显示一个分数
> 而不是一个单独数字：它以前无条件只显示 `mapped`，仿佛那就是完整的灾害计数。
> `app/src/lib/watch.js` 自己的注释和 `app/src/lib/watch.test.js` 用真实数字
> 把修复前的确切行为钉了下来——徽章曾经显示"882 起活跃灾害"，而监测流水线自己
> 的 `watch_status.json` 在同一次运行里已经声明了另外 198 个它抓取到、却因为
> 缺乏可用几何信息而丢弃的要素，真实总数是 1,080。状态产物早就说明了这一点；
> 只是应用里没有任何代码去读它。数清流水线丢弃了什么、却只展示保留下来的那部分，
> 是一种更安静的"伪造图层"，性质相同：显示出来的数字看起来完整，其实不然。
> `LiveWatchBadge` 现在只要两个数字对不上，就会显示"{mapped} hazards mapped of
> {total}"（已映射 N 起，共 M 起），并用第二个徽章直接点名未展示的数量，而不是
> 把它并进第一个数字里。当状态产物本身读不到时，`watchSummary()` 会返回
> `total: null`，而不是假定已映射数就是全部，徽章会显示"完整性未知"，而不是把
> 一个不完整的数字当作最终结果呈现。

## Validity badges and the lineage panel

`stageValidity()` (`app/src/lib/data.js`) reads a pipeline stage's rows out
of an event's committed, append-only [audit log](12-glossary.md) and groups
them into runs — using an explicit `run_id` where the log carries one, and a
sequence-restart heuristic for older rows, both covered in the function's
own docstring and in `02`. It returns the `latest` run's check count and
pass/fail state separately from every `superseded` run, so a stage that
failed, was fixed, and re-ran is never reported as one inflated total.
`app/src/components/Badges.jsx`'s `ValidityBadge` renders exactly that: the
latest run's own pass/fail ("✓ latest run: 6/6 checks passed"), and a second
badge naming how many earlier runs exist — in a distinct, visually flagged
style if any of them failed, because a rejected run staying visible in the
log is evidence the harness worked, not something to hide.

The lineage panel (`app/src/components/LineagePanel.jsx`, toggled from the
"show lineage & provenance" button) answers a different question: not
whether the layer on screen passed its checks, but which committed file it
actually came from. `artifactLineage()` (`app/src/lib/data.js`) matches rows
from the event's [artifact manifest](12-glossary.md) to the active layer by
filename, oldest to newest — an artifact rebuilt more than once has more
than one row. For each row the panel shows the producing agent, its
timestamp, its sha256 (the first 12 characters, the same [artifact
ID](12-glossary.md) form a citation uses), and up to four of its inputs.
Below that it repeats the same `stageValidity()` result the badge shows, and
below that, any local slider adjustments recorded this session via
`getLocalAudit()` (`app/src/lib/data.js`) — again stated as session-only,
not sent anywhere. So the path from a map layer to the hash of the file
behind it runs: pick a layer, open the lineage panel, read the sha256 on the
row whose `path` matches that layer's URL.

> **中文。** `stageValidity()`（`app/src/lib/data.js`）从一个事件已提交、只增
> 不改的审计日志里读出某个处理阶段的记录行，并把它们分组成一次次运行——日志
> 里有 `run_id` 字段的用它分组，没有的老日志用一种"序列重启"启发式规则分组，
> 两种方法在函数自己的文档字符串和 `02` 章里都讲过。它把最近一次运行的检查数与
> 通过/失败状态，与每一次被取代的运行分开返回，所以一个失败过、被修复、又重跑过
> 的阶段，永远不会被报告成一个虚高的总数。`app/src/components/Badges.jsx` 里的
> `ValidityBadge` 正是这样渲染的：最近一次运行自己的通过/失败情况
> （"✓ latest run: 6/6 checks passed"），以及第二个徽章，点名存在多少次更早的
> 运行——如果其中有失败的，会用一种视觉上明显不同的样式标出来，因为一次被拒绝的
> 运行仍留在日志里可见，恰恰证明了 harness 起了作用，而不是什么需要隐藏的东西。
> 溯源面板（`app/src/components/LineagePanel.jsx`，由"show lineage &
> provenance"按钮切换出来）回答的是另一个问题：不是当前图层是否通过了检查，
> 而是它究竟来自哪一份已提交的文件。`artifactLineage()`
> （`app/src/lib/data.js`）按文件名把该事件制品清单里的记录行与当前图层匹配
> 起来，按时间从旧到新排列——一份被多次重建过的产物会有多条记录。面板为每一行
> 展示生成它的 agent、时间戳、sha256（前 12 个字符，与引证使用的制品 ID
> 形式相同），以及最多四项输入。下方再重复一遍徽章展示过的同一份
> `stageValidity()` 结果，再下方是本次会话里通过 `getLocalAudit()`
> （`app/src/lib/data.js`）记录下的任何本地滑杆调整——同样注明仅限本次会话，
> 不会发送到任何地方。所以从一个地图图层追到其背后文件哈希值的路径是：选中
> 一个图层，打开溯源面板，在 `path` 与该图层地址相匹配的那一行里读出 sha256。

## Citations, and how a live chip differs

`app/src/components/ChatPanel.jsx` is the browser side of `Steward.answer()`
— `07` covers the request lifecycle and the exact four response shapes the
gateway can return; this section covers how the panel renders each one
without collapsing any of them into another. A cited **answer** renders its
text through `parseCitations()` (`app/src/lib/citations.js`), which splits
the prose into text runs and citation tokens; each `[artifact:ID]` token
becomes a plain chip and each `[live:ID]` token becomes a chip marked with a
`↻` and a title reading "cites a live third-party lookup — re-derivable, not
retained" — the same distinction `05` covers for what a reader can actually
do with each kind of source. The answer's own `verifiability` value is
rendered through `verifiabilityLabel()` (`app/src/lib/citations.js`), which
names one of `retained`, `re-derivable`, or `cited-only` — the
[weakest-link](12-glossary.md) value the gateway itself computed, matching
`03` and `05` — or renders nothing at all when the gateway did not state one,
rather than defaulting to the strongest label. When a live citation is
present, the panel also renders the gateway's own `attribution` field
verbatim, because the field the credit lives in is the same field the
content came from — the app cannot show one without the other. A **rule-ID
refusal** and a declared **no-evidence** response each render their own
`reason` text under their own heading, and a declared **outage** — whether
`agent_unavailable` or `live_source_unavailable` — renders as an outage
message, distinguishing the two because they name different failing parts
of the system, not one generic "something went wrong."

The panel talks to a gateway endpoint the user configures, defaulting to
`http://localhost:8080`. The public site ships no chat backend of its own:
when that endpoint cannot be reached, the panel does not fail silently or
fall back to some hosted stand-in — it renders a declared
`agent_unavailable` outage naming the endpoint it tried and the command to
run the gateway locally, the same behavior `07` covers under "Not safe to
host yet."

> **中文。** `app/src/components/ChatPanel.jsx` 是 `Steward.answer()` 在浏览器
> 一侧的呈现——请求生命周期以及网关能返回的确切四种响应形状，`07` 章已经讲过；
> 这一节讲面板如何把每一种原样渲染出来，而不把其中任何一种混同成另一种。一条
> 带引用的**回答**，其正文通过 `parseCitations()`（`app/src/lib/citations.js`）
> 渲染，该函数把文本拆分成普通文字片段和引证标记；每一个 `[artifact:ID]`
> 标记变成一个普通的小标签，每一个 `[live:ID]` 标记变成一个带 `↻` 符号的
> 小标签，其提示文字写着"cites a live third-party lookup — re-derivable, not
> retained"（引用了一次实时第三方查询——可复现，非留存）——这正是 `05` 章讲过的、
> 读者对每一类来源实际能做什么的区别。这条回答自己的 `verifiability`
> （可验证性）值通过 `verifiabilityLabel()`（`app/src/lib/citations.js`）渲染，
> 给出 `retained`（留存）、`re-derivable`（可复现）、`cited-only`（仅可引证）
> 三者之一——即网关自己按短板原则（weakest-link）算出的值，与 `03`、`05`
> 两章一致——若网关没有说明这个值，则什么都不渲染，而不是默认取最强的那个标签。
> 当存在实时引证时，面板还会原样渲染网关自己的 `attribution`（署名）字段，
> 因为署名所在的字段和内容来源的字段是同一个——应用不可能只展示其中一个而不展示
> 另一个。一次**带规则编号的拒绝**和一次声明式的**无证据**响应，各自在自己的
> 标题下渲染各自的 `reason` 文字；一次声明式的**系统不可用**——无论是
> `agent_unavailable`（agent 本身不可用）还是 `live_source_unavailable`
> （实时数据源不可用）——都渲染成一条系统不可用消息，二者被区分开来，因为它们
> 点名的是系统里不同的失败部位，而不是笼统的一句"出了点问题"。这个面板对接的是
> 一个由用户自行配置的网关端点，默认指向 `http://localhost:8080`。公开网站本身
> 不附带任何对话后端：当这个端点无法访问时，面板不会悄悄失败，也不会转而连到
> 某个托管替身上——它会渲染一条声明式的 `agent_unavailable` 系统不可用消息，
> 点名它尝试连接的端点，以及在本地运行网关所需的命令，这与 `07` 章
> "Not safe to host yet" 一节讲的行为一致。

## Artifacts are vendored at build time

`app/scripts/sync-artifacts.mjs` runs at build time and vendors artifacts
from `events/` into the app's public directory, so the deployed PWA serves
exactly the committed, hashed products it was built from — nothing fetched
live, nothing wider than what was authorized. It does not decide which
artifacts to copy; that decision is the [distribution
plane](12-glossary.md)'s, computed into `publication_allowlist.json` by
`scripts/publication_boundary.py`, and this script refuses to run at all
without that file, and refuses to build "an eventless app" if the allowlist
is empty. For each allowed entry it either copies the file directly or, when
the entry's `redact_workstation_paths` flag is set, rewrites any workstation
path pattern to `<workstation>` before writing the file — the same
redaction `01` and `04` describe, applied here at the point the artifact
enters the published tree. `04` owns the full derivation of why this script
exists in its current, narrower form: it used to copy whole event
directories, which is how a parcel-level source artifact reached the public
site in the 2026-08-20 incident, and the list of which events publish at all
— once a plain array literal inside this script — moved out into
`policy_v1.yaml` as `published_events`, because which events are public is a
governance decision, not build-script trivia.

`app/vite.config.js` is what turns the built app into an installable,
offline-capable PWA, via `vite-plugin-pwa`'s `workbox` configuration. Two
caching rules do the work: a `StaleWhileRevalidate` cache for
`/events/**/*.{geojson,json,jsonl}`, safe because those files are exactly
the versioned, hashed artifacts `sync-artifacts.mjs` just vendored, and a
`CacheFirst`, 30-day cache for basemap tiles fetched from
`tiles.openfreemap.org` — the same keyless OpenFreeMap style `MapView.jsx`
loads. Choosing a keyless basemap provider is not an omission of a
higher-fidelity, keyed commercial option; it is what lets the cache-first
rule work without ever depending on a credential, which is the specific
trade that makes an app installable and fully offline-capable for maps and
analysis, with no account and no backend server required for anything
except the optional chat panel covered above.

> **中文。** `app/scripts/sync-artifacts.mjs` 在构建时运行，把 `events/` 下的
> 产物搬运到应用的公开目录里，让部署出去的 PWA 恰好提供它构建时所依据的、已提交
> 且已哈希的产物——不实时抓取任何东西，也不会比被授权的范围更宽。这个脚本自己不
> 决定要复制哪些产物；那个决定属于发布平面，由 `scripts/publication_boundary.py`
> 计算写入 `publication_allowlist.json`，这个脚本如果找不到那份文件就完全拒绝
> 运行，如果许可清单是空的就拒绝"构建一个没有任何事件的应用"。对每一条被许可的
> 条目，它要么直接复制文件，要么在条目的 `redact_workstation_paths` 标志被置位
> 时，先把任何工作站路径模式改写成 `<workstation>` 再写入——这正是 `01`、`04`
> 两章讲过的那种脱敏，只是应用在这里、产物进入已发布目录的这个节点上执行。`04`
> 章完整讲过这个脚本为何变成现在这个更窄的版本：它以前整个复制事件目录，这正是
> 2026-08-20 那次事故里一份 parcel 级源文件得以进入公开网站的原因；哪些事件
> 会被公开发布这份名单——曾经是这个脚本里一个普通的数组字面量——被搬到了
> `policy_v1.yaml` 里成为 `published_events`，因为"哪些事件可以公开"是一项
> 治理决定，不该是藏在构建脚本里的琐碎细节。`app/vite.config.js` 是让构建出的
> 应用变成一个可安装、可离线使用的 PWA 的地方，靠的是 `vite-plugin-pwa` 的
> `workbox` 配置。两条缓存规则做了具体的事：对
> `/events/**/*.{geojson,json,jsonl}` 采用"先给旧缓存、同时后台刷新"
> （`StaleWhileRevalidate`）策略，之所以安全，是因为这些文件正是
> `sync-artifacts.mjs` 刚刚搬运过来的、有版本、有哈希的产物；对从
> `tiles.openfreemap.org` 取得的底图瓦片采用"优先用缓存"
> （`CacheFirst`）、缓存 30 天的策略——这正是 `MapView.jsx` 加载的同一个免密钥
> OpenFreeMap 样式。选择一个免密钥的底图供应商，不是省略了一个精度更高、需要
> 密钥的商业选项；这正是让"优先用缓存"这条规则可以完全不依赖任何凭据运行的
> 前提，也是让这个应用在地图与分析功能上可安装、完全离线可用——除了上文提到的
> 可选对话面板外，无需账号、无需后端服务器——这一具体权衡的所在。
