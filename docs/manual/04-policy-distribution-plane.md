# 04 · The distribution plane — what a build may publish

[Institutional validity](12-glossary.md) is enforced by two separate rule
sets rather than one. Chapter `03` covers the first, the
[claim plane](12-glossary.md) — what the agent may assert about a place,
given who is asking, why, and against what evidence. This chapter covers
the second, the [distribution plane](12-glossary.md) — what a build is
authorized to publish, given an artifact that already exists on disk and
is recorded under a kind. Chapter `05` covers verifiability, the axis both
planes read from. The engine lives in
`src/geosteward/harness/distribution.py` (`DistributionPolicy`,
`ArtifactRef`, `DistributionPolicy.evaluate`); `src/geosteward/harness/publication.py`
and `scripts/publication_boundary.py` are the two places that engine
actually runs against real files, covered under the CI gates below.

> **中文。** 有效性（结果 / 过程 / 制度）由两套独立的规则集共同强制执行，而不是一套。
> `03` 章讲的是第一套：断言平面——给定提问角色、提问目的和证据依据，agent 可以
> 对一个地方断言什么。本章讲第二套：发布平面——给定一份已经落盘、并已按种类
> 登记的制品，构建是否被授权发布它。两个平面共同读取的可验证性这根轴留给
> `05` 章。这套引擎实现在 `src/geosteward/harness/distribution.py`
> （`DistributionPolicy`、`ArtifactRef`、`DistributionPolicy.evaluate`）；
> `src/geosteward/harness/publication.py` 与 `scripts/publication_boundary.py`
> 是这套引擎真正对真实文件运行的两个地方，见下文"CI 关卡"一节。

## Why a second plane exists

On 2026-08-20 a parcel-level [CAL FIRE DINS](12-glossary.md) source —
`damage_points_restricted` — reached the public Pages site while
satisfying every rule chapter `03` describes, because nothing in this
project ever *claimed* it. The build's `app/scripts/sync-artifacts.mjs`
copied whole event directories with `cpSync`, and a file nobody asserted
is a file the claim plane has no jurisdiction over: `deny-parcel-any-role`
forbids parcel-level claims at every role and tier, and it forbade
nothing here, because no agent ever produced a claim for this file to
match against. The full account, including the exposure window and the
verification steps taken to close it, is in
`docs/incidents/2026-08-20-publication-boundary.md`; this chapter does
not repeat it, only the shape of the fix.

That shape is a second, independent rule set reusing the claim plane's own
grammar: `DistributionPolicy` imports `PolicyDecision`, `default_deny`, and
`validate_rules` directly from `src/geosteward/harness/policy.py`, so both
planes share one decision shape and one fail-closed default rather than
inventing a second one that could quietly drift from the first. Running
`python scripts/publication_boundary.py plan` over the repository as it
stands today confirms the fix's shape directly, rather than asking a
reader to trust a number in prose: of the 30 files the three published
events place under `events/`, 16 are allowed and 14 are denied — one of
them `damage_points_restricted`'s
`events/eaton-2025/exposure/dins_points_restricted.csv.gz`, denied by
`deny-publish-parcel-resolution`, and thirteen more are internal snapshot
files (registry profiles, SVI tract snapshots, a debris baseline) across
all three events, denied by `deny-publish-internal-audience`. Thirty is
exactly what an undifferentiated `cpSync` of every committed file would
have shipped before this plane existed; sixteen is what the policy now
authorizes.

> **中文。** 2026 年 8 月 20 日，一份 parcel 级的 CAL FIRE DINS（损毁勘查）数据源
> ——`damage_points_restricted`——在满足 `03` 章讲到的每一条规则的情况下，
> 仍然进了公开的 Pages 站点，原因是本项目从来没有断言过它。构建脚本
> `app/scripts/sync-artifacts.mjs` 用 `cpSync` 整个复制了事件目录，而一个
> 没有人断言过的文件，断言平面根本管不到：`deny-parcel-any-role` 禁止在任何
> 角色、任何层级下做出 parcel 级断言，但它在这里什么也没禁止，因为从来没有
> agent 为这个文件生成过一条断言去命中这条规则。完整经过——包括暴露窗口和
> 事后的核验步骤——记录在 `docs/incidents/2026-08-20-publication-boundary.md`
> 里；本章不重述那份记录，只讲修复之后的形态。
>
> 那个形态是一套独立的第二规则集，复用断言平面自己的语法：`DistributionPolicy`
> 直接从 `src/geosteward/harness/policy.py` 导入 `PolicyDecision`、
> `default_deny`、`validate_rules`，让两个平面共享同一种决策结构和同一个
> 失败即拒绝（fail-closed）的默认值，而不是另起一套、日后悄悄和前者走样。
> 现在对仓库运行 `python scripts/publication_boundary.py plan`，能直接
> 核实这次修复的形态，而不必让读者去相信一段文字里的数字：三个已发布事件在
> `events/` 下共放着 30 个文件，其中 16 个被允许、14 个被拒绝——其中一个正是
> `damage_points_restricted` 的
> `events/eaton-2025/exposure/dins_points_restricted.csv.gz`，被
> `deny-publish-parcel-resolution` 拒绝；另外十三个是三个事件里的内部快照文件
> （注册档案、SVI 普查区快照、一份废墟基线），被 `deny-publish-internal-audience`
> 拒绝。三十，正是这套平面出现之前，一次不加区分的 `cpSync` 会发布出去的数字；
> 十六，是现在策略实际授权的数字。

## Three attributes per artifact class

`policy_v1.yaml`'s `artifact_classes` section maps every artifact `kind`
this project produces to exactly three attributes, and `_validate_classes`
in `distribution.py` enforces "exactly": a class missing one of them, or
carrying a key outside `KNOWN_CLASS_ATTRIBUTES`, raises a `ValueError` at
construction, before any file is ever evaluated. `resolution_cap` is the
finest geography the artifact can support a statement about — `parcel`,
`tile`, `event`, `dataset`, or `source`. `audience` is who the artifact is
for: `public` ships to the site, `lineage` stays reachable by hash through
the manifest rather than by URL, and `internal` supports reproduction on
the maintainer's workstation only. `license` is whether the content is
this project's to redistribute at all.

`license` is kept separate from the other two on purpose.
`resolution_cap` and `audience` both record what *this project* judges
safe to serve; a third party's terms are not this project's to judge, so
licensing gets its own attribute and, as the next section shows, its own
denial checked ahead of every other rule. `damage_points_restricted` is
the case that proves the two judgments are independent rather than
redundant: it is `license: public-domain-source`, because CAL FIRE DINS is
public-domain data — nobody's redistribution terms are being violated —
and at the same time `resolution_cap: parcel`, so it is denied publication
on disclosure grounds, not licensing grounds. A clean license does not
excuse a parcel-level resolution, and a capped resolution does not excuse
a restricted license; neither attribute stands in for the other.

`license` is also the one attribute checked against a closed vocabulary,
`KNOWN_LICENSES` (`project`, `public-domain-source`,
`third-party-restricted`), for the same reason `_validate_verifiability_values`
checks verifiability in chapter `03`: `resolution_cap` and `audience`
values are only ever compared against rules in this same file, so a typo
in either one just fails to match, denies by default, and narrows the
public surface rather than widening it. A license value is different — it
names an external constraint the rules key off — and a rule matching
`license: third-party-restricted` guards against exactly the misspelling
`third-party-restrcited`: a value that satisfies no deny rule, so the
class it labels would publish. Validating the value at load turns that
typo into a load-time `ValueError` instead of a silent widening of the
public surface.

> **中文。** `policy_v1.yaml` 的 `artifact_classes` 部分把本项目产出的每一种
> 制品 `kind` 都映射到恰好三个属性，`distribution.py` 里的 `_validate_classes`
> 强制执行这个"恰好"：一个类缺了其中任何一个属性，或者带了
> `KNOWN_CLASS_ATTRIBUTES` 之外的键，都会在构造阶段——早于任何文件被真正
> 评估之前——抛出 `ValueError`。`resolution_cap`（分辨率上限（resolution cap）
> ）是该制品能够支撑一个陈述的最细地理层级——`parcel`、`tile`、`event`、
> `dataset` 或 `source`。`audience` 是这个制品是为谁准备的：`public` 发布到
> 站点，`lineage` 只通过清单以哈希可达、而不通过 URL，`internal` 仅支持在
> 维护者本机上复现。`license` 则是这份内容本项目是否有权再分发。
>
> `license` 被特意和另外两个分开。`resolution_cap` 与 `audience` 记录的都是
> ——本项目——判断什么是可以安全发布的；而第三方的条款不是本项目能去判断
> 的事，所以许可获得了自己的属性，也（如下一节所示）获得了排在所有其他
> 规则之前的、专属于它的拒绝。`damage_points_restricted` 正是证明这两项
> 判断相互独立、而非彼此重叠的例子：它是 `license: public-domain-source`
> ——因为 CAL FIRE DINS 是公有领域数据，谈不上违反任何人的再分发条款——
> 同时又是 `resolution_cap: parcel`，所以它是因为披露层面的判断、而不是
> 许可层面的判断被拒绝发布的。干净的许可不能替代分辨率的上限，被封顶的
> 分辨率也不能替代受限的许可；这两个属性谁都不能替谁开脱。
>
> `license` 也是唯一一个被限定为封闭词表——`KNOWN_LICENSES`（`project`、
> `public-domain-source`、`third-party-restricted`）——校验的属性，理由和
> `03` 章里 `_validate_verifiability_values` 校验可验证性的理由一样：
> `resolution_cap` 与 `audience` 的取值只会拿来和同一份文件里的规则比对，
> 所以哪怕写错了，也只是匹配不上、按默认值拒绝，结果是缩小公开面而不是
> 扩大它。许可不一样——它指向的是一项外部约束，规则正是拿它来判断的——而
> 一条匹配 `license: third-party-restricted` 的规则，防的正是写成
> `third-party-restrcited` 这种笔误：这样的取值满足不了任何一条拒绝规则，
> 于是它标记的这个类就会被发布出去。在加载时校验这个取值，就是把这个笔误
> 变成一次加载期的 `ValueError`，而不是一次悄无声息的公开面扩大。

## The rules, one at a time

`artifact_classes` groups thirteen kinds the way `policy_v1.yaml` itself
groups them. **Tile products, the public evidence surface** —
`damage_grid`, `svi_context_grid`, `debris_exposure_grid`,
`evidence_grid`, `evidence_coverage_grid`, `sample_density_grid` — are all
`{resolution_cap: tile, audience: public, license: project}`. **Accountability
records**, where publishing the record *is* the accountability claim —
[artifact manifest](12-glossary.md) and [audit log](12-glossary.md), plus
`event_record` — are `{resolution_cap: event, audience: public, license:
project}`. **The record of a non-retainable lookup**, `live_lookup_record`,
is `{resolution_cap: tile, audience: public, license: project}`: it holds
no third-party content at all, only request parameters, a response
digest, and a count, so it is publishable *because* it is empty of the
content it attests to. **The restricted parcel source**,
`damage_points_restricted`, is `{resolution_cap: parcel, audience:
lineage, license: public-domain-source}` — lineage-only, never served, for
the reason the previous section makes concrete. **Internal snapshots**,
frozen upstream state kept for reproduction rather than for the app —
`dataset_registry_snapshot` and `source_snapshot` — are `audience:
internal`. One more case matters as much as these five groups: every kind
absent from this table at all. A new artifact added to `events/` under a
kind nobody has classified here is
denied by `DistributionPolicy.evaluate` before any rule is even
consulted, naming the unclassified kind in the reason. That is the point
of the table, not a gap in it — a new product cannot widen the public
surface until somebody classifies it.

`distribution`'s six rules are evaluated in this order, first match wins,
exactly as chapter `03` describes for the claim plane:

1. **`deny-publish-third-party-restricted`** (`match: {license:
   third-party-restricted}`) — may a third-party-restricted artifact
   publish, whatever its resolution or audience? No, checked first and
   unconditionally.
2. **`deny-publish-parcel-resolution`** (`match: {resolution_cap:
   parcel}`) — may a parcel-resolution artifact publish? No; this is the
   rule that denies `damage_points_restricted`, matching on resolution
   alone before its `audience: lineage` is ever considered.
3. **`deny-publish-internal-audience`** (`match: {audience: internal}`) —
   may an internal snapshot publish? No; `dataset_registry_snapshot` and
   `source_snapshot` stop here.
4. **`deny-publish-lineage-audience`** (`match: {audience: lineage}`) —
   may a lineage artifact publish? No, reachable by hash through the
   manifest rather than by URL. In the shipped policy this rule never
   actually fires, because `damage_points_restricted` — the one kind
   currently classified `audience: lineage` — is already caught one rule
   earlier by its `resolution_cap`; it stands ready for a future kind
   that is lineage-scoped without also being parcel-resolution, so that
   kind is denied by name rather than falling through to a generic
   default.
5. **`allow-publish-tile-products`** (`match: {resolution_cap: tile,
   audience: public}`) — may a public tile product publish? Yes; this is
   what authorizes the six tile products and `live_lookup_record`.
6. **`allow-publish-event-accountability-records`** (`match:
   {resolution_cap: event, audience: public}`) — may a public
   event-level accountability record publish? Yes; this is what
   authorizes `event_record`, the artifact manifest, and the audit log.

> **中文。** `artifact_classes` 把十三种制品按 `policy_v1.yaml` 自己的分组方式
> 分了组。**tile 产品，也就是公开的证据面**——`damage_grid`、
> `svi_context_grid`、`debris_exposure_grid`、`evidence_grid`、
> `evidence_coverage_grid`、`sample_density_grid`——全部是
> `{resolution_cap: tile, audience: public, license: project}`。
> **问责记录**——发布这份记录本身就是问责断言——制品清单与审计日志，
> 加上 `event_record`——是 `{resolution_cap: event, audience: public,
> license: project}`。**一次不可留存查询的记录** `live_lookup_record` 是
> `{resolution_cap: tile, audience: public, license: project}`：它完全不
> 承载任何第三方内容，只有请求参数、一个响应摘要和一个计数，正因为它对
> 它所证明的内容而言是空的，所以才可以发布。**受限的 parcel 数据源**
> `damage_points_restricted` 是 `{resolution_cap: parcel, audience:
> lineage, license: public-domain-source}`——仅供溯源、从不发布，理由在
> 上一节已经讲清楚。**内部快照**——为了复现而保留、不是为了 app 而存在的
> 冻结上游状态——`dataset_registry_snapshot` 与 `source_snapshot`——都是
> `audience: internal`。还有一种情况和上面这五组同样要紧：任何不在这张表里
> 的 kind。`events/` 下新增的、任何没有在这里被分类的制品，会在任何规则被查询之前
> 就被 `DistributionPolicy.evaluate` 拒绝，理由里点名这个未分类的 kind。
> 这正是这张表存在的意义，而不是它的一个漏洞——一个新产品在被人分类之前，
> 没法扩大公开面。
>
> `distribution` 的六条规则按以下顺序评估，先匹配先生效，和 `03` 章讲的
> 断言平面完全一样：`deny-publish-third-party-restricted` 问的是"一个
> third-party-restricted 的制品，不论分辨率、不论受众，能发布吗"，答案是
> 不能，且排在最前面、无条件生效；`deny-publish-parcel-resolution` 问的是
> "parcel 分辨率的制品能发布吗"，答案是不能——正是这条规则拒绝了
> `damage_points_restricted`，只看分辨率，甚至不看它的 `audience: lineage`；
> `deny-publish-internal-audience` 问的是"内部快照能发布吗"，答案是
> 不能——`dataset_registry_snapshot` 和 `source_snapshot` 就止步于此；
> `deny-publish-lineage-audience` 问的是"lineage 制品能发布吗"，答案是
> 不能，它只通过清单以哈希可达、不通过 URL——在已上线的策略里这条规则实际上
> 从未真正生效过，因为当前唯一被标为 `audience: lineage` 的 kind——
> `damage_points_restricted`——已经在前一条规则那里被它的 `resolution_cap`
> 拦下了；这条规则是为将来某个"lineage 范围但不是 parcel 分辨率"的 kind
> 准备的，让那样的 kind 被点名拒绝，而不是落到一个笼统的默认拒绝里；
> `allow-publish-tile-products` 问的是"公开的 tile 产品能发布吗"，答案是
> 能——正是它授权了那六个 tile 产品和 `live_lookup_record`；
> `allow-publish-event-accountability-records` 问的是"公开的
> 事件级问责记录能发布吗"，答案是能——正是它授权了 `event_record`、
> 制品清单和审计日志。

## Two independent defences

`deny-publish-third-party-restricted` and its five neighbors run inside
`plan_publication` (`src/geosteward/harness/publication.py`), which walks
`events/`, asks `DistributionPolicy.evaluate` about every file's recorded
kind, and denies a *classified* artifact whose attributes match a deny
rule. `verify_site`, in the same module, is a structurally different
check: given an assembled site tree and the generated allowlist, it takes
their set difference — any file present in the tree that is not named on
the allowlist is a violation, reported as `unauthorized_artifact`,
regardless of *why* it is missing. It would catch a newly classified but
denied kind just as it would catch a kind nobody ever classified, and —
the case that matters most, because it is the one that actually happened
— it would catch a file that reached the tree by a path that bypassed
`plan_publication` altogether, such as a build script regressing to a
whole-directory copy. The module's own docstring states the design choice
plainly: nothing in `verify_site` recognises a "dangerous" file by
pattern; a pattern match would be a blocklist, permanently one artifact
behind the next thing nobody thought to name. `verify_site` separately
reports `leaked_workstation_path` violations, using `_leaked_paths` to
check each allowed file's contents against `WORKSTATION_PATH` — a second
property, independent of the allowlist membership check, over the same
assembled tree.

`plan_publication` flags which allowed files need that redaction, setting
`redact_workstation_paths` from `REDACTED_KINDS` (currently just
`artifact_manifest`) rather than leaving the build script to decide which
kinds carry workstation paths. The redaction itself, though, runs inside
`app/scripts/sync-artifacts.mjs`: it reads the allowlist entry's flag and,
where set, applies its own copy of the `WORKSTATION_PATH` pattern before
writing the file into the built app. `publication.py` also defines a
function performing the identical substitution,
`redact(text)` at `src/geosteward/harness/publication.py:191` — but
nothing in this repository calls it. The decision of which artifact kinds
need redaction correctly lives in the policy layer; the execution of that
decision is duplicated, once exercised in the build script and once not.
This chapter does not correct that duplication; it is reported as a
defect elsewhere.

> **中文。** `deny-publish-third-party-restricted` 和它另外五个同级规则，
> 运行在 `src/geosteward/harness/publication.py` 的 `plan_publication`
> 里面：它遍历 `events/`，就每个文件登记的 kind 去问
> `DistributionPolicy.evaluate`，拒绝一个已分类、但属性匹配某条拒绝规则
> 的制品。同一个模块里的 `verify_site` 是结构上完全不同的一种检查：
> 给定一棵已装配好的站点目录树和生成好的白名单，它取两者的集合差
> ——树里出现、但白名单里没点名的任何文件，都算一次违规，标记为
> `unauthorized_artifact`——不管它缺席的原因是什么。一个新分类但被拒绝的
> kind 会被它抓到，一个从来没被分类过的 kind 也会被它抓到——而最关键的
> 那种情形、也是真正发生过的那种——一个绕开 `plan_publication` 整个流程、
> 靠别的路径混进树里的文件（比如构建脚本退化回整目录复制），同样会被它
> 抓到。这个模块自己的文档字符串把这个设计选择讲得很直白：`verify_site`
> 里没有任何东西靠模式去识别"危险"文件；模式匹配只会是一份黑名单，
> 永远比下一个没人想到要点名的东西慢一步。`verify_site` 还会另外报告
> `leaked_workstation_path` 违规，用 `_leaked_paths` 拿每一个被允许的
> 文件内容去比对 `WORKSTATION_PATH`——这是同一棵已装配树上、独立于
> 白名单成员检查的另一项属性。
>
> `plan_publication` 会标出哪些被允许的文件需要做这项脱敏，靠
> `REDACTED_KINDS`（目前只有 `artifact_manifest`）来设置
> `redact_workstation_paths`，而不是把"哪些 kind 携带工作站路径"这个
> 判断留给构建脚本去做。但真正执行脱敏的地方是
> `app/scripts/sync-artifacts.mjs`：它读取白名单条目上的这个标志，
> 一旦为真，就在把文件写进构建好的 app 之前，套用它自己那份
> `WORKSTATION_PATH` 模式的副本。`publication.py` 里也定义了一个执行
> 完全相同替换的函数——`src/geosteward/harness/publication.py:191` 的
> `redact(text)`——但这个仓库里没有任何地方调用它。哪些制品种类需要
> 脱敏，这项判断正确地留在了策略层；而执行这项判断的代码被重复实现了
> 一次，一份在构建脚本里被真正用上，另一份没有。本章不去修正这处重复，
> 只是把它作为一个缺陷另行报告。

## The CI gates

`scripts/publication_boundary.py` has three modes. `plan` asks the
distribution policy about every file under `events/` and writes
`app/public/publication_allowlist.json`, the file
`app/scripts/sync-artifacts.mjs` copies from when it builds the app.
`plan --check` writes nothing; it exits non-zero if the committed
allowlist has drifted from what the policy would generate today — the
gate that stops a hand-edited allowlist from widening the public surface
behind the policy's back. `verify <site_dir>` checks an already-assembled
site tree against the committed allowlist and is, in the module's own
words, the gate that actually matters, because it inspects the artifact
about to be deployed rather than the intent that produced it.

`.github/workflows/test.yml` runs the first two: `plan --check` in the
`unit-tests` job, alongside the rest of the test suite, and `verify`
against `app/dist` in the `app-build` job, after `npm run build` has run
`sync-artifacts.mjs` for real — so a regression in that script back to
copying whole directories, the exact failure mode of the 2026-08-20
incident, is what this step exists to catch. `.github/workflows/pages.yml`
runs the third: it assembles `_site` from `docs/`, `app/dist/`, and the
optional live-data products, then runs `verify _site` immediately before
`actions/upload-pages-artifact`, so a violation fails the build and the
deploy step never runs at all. Three checks, three different artifacts —
the generated allowlist, the app's own build output, and the fully
assembled site — on every push, every pull request, and every scheduled
Pages deploy.

> **中文。** `scripts/publication_boundary.py` 有三种模式。`plan` 就
> `events/` 下的每一个文件去问发布平面，写出
> `app/public/publication_allowlist.json`——`app/scripts/sync-artifacts.mjs`
> 构建 app 时正是从这份文件里拷贝的。`plan --check` 什么也不写，只在
> 已提交的白名单和策略今天会生成的结果不一致时非零退出——这是防止一份
> 手改的白名单绕开策略、悄悄扩大公开面的关卡。`verify <site_dir>` 拿一棵
> 已经装配好的站点目录树去对照已提交的白名单，用这个模块自己的话说，是
> 真正起作用的关卡，因为它检查的是即将部署的制品本身，而不是产生这个
> 制品的意图。
>
> `.github/workflows/test.yml` 跑前两种：`plan --check` 在 `unit-tests`
> 这个 job 里、和其余测试放在一起跑；对 `app/dist` 跑 `verify` 则在
> `app-build` 这个 job 里、在 `npm run build` 真正跑过一次 `sync-artifacts.mjs` 之后
> 跑——所以这个脚本如果退化回整目录复制（正是 2026 年 8 月 20 日那次事故
> 的失败方式），这一步就是用来抓住它的。`.github/workflows/pages.yml`
> 跑第三种：它把 `docs/`、`app/dist/` 和可选的实时数据产品装配成 `_site`，
> 然后紧接着在 `actions/upload-pages-artifact` 之前跑 `verify _site`，
> 一旦违规，构建就失败，部署这一步根本不会跑。三种检查、三种不同的制品
> ——生成出来的白名单、app 自己的构建产物、完整装配好的站点——覆盖每一次
> push、每一次 pull request、每一次定时的 Pages 部署。

## Ordering must be a function of the policy

On 2026-08-21 `plan_publication` sorted `Path` objects directly, and
`PurePath` ordering case-folds on Windows but not on POSIX: two registry
profile files differing only in case — `Eaton_Fire_profile.json` and
`EATON_wildfire_mapillary_matched_profile.json` — swapped places between
the maintainer's Windows workstation and Linux CI. That mattered because
the allowlist is a generated, committed file and `plan --check`
regenerates it and diffs the bytes against the commit: for that diff to
mean anything, the file's bytes have to be a function of the policy
alone, never of which operating system happened to produce them. A gate
that fails on a cosmetic reordering, rather than a real drift in what is
authorized, is a gate people learn to override — and the next time it
fires for a real reason, the habit already formed is to override it
again. The fix is `_sort_key(path, root) -> str`, ordering by the
POSIX-relative-path string rather than by the `Path` object itself,
applied everywhere ordering reaches a committed file: collecting
manifests in `_kinds_by_path`, walking files in `plan_publication`, and
reporting violations in `verify_site`.

> **中文。** 2026 年 8 月 21 日，`plan_publication` 曾经直接对 `Path` 对象
> 排序，而 `PurePath` 的排序在 Windows 上会做大小写折叠、在 POSIX 上不会：
> 两份仅大小写不同的注册档案文件——`Eaton_Fire_profile.json` 和
> `EATON_wildfire_mapillary_matched_profile.json`——在维护者的 Windows
> 工作站和 Linux CI 之间会互换顺序。这件事之所以要紧，是因为白名单是一份
> 生成出来、已提交的文件，`plan --check` 会重新生成它、再把字节内容和
> 提交的版本做对比：要让这个对比有意义，这份文件的字节内容就必须只是
> 策略的函数，绝不能取决于恰好是哪个操作系统生成的它。一个因为无关紧要的
> 顺序变化、而不是因为真正的授权范围漂移就失败的关卡，是一种人们会学会
> 绕过去的关卡——等它下一次真的因为该失败的理由而失败时，绕过去已经成了
> 习惯。修复方式是 `_sort_key(path, root) -> str`，按 POSIX 相对路径字符串
> 排序，而不是按 `Path` 对象本身排序，并且用在了每一处排序结果会影响到
> 已提交文件的地方：`_kinds_by_path` 里收集清单、`plan_publication` 里
> 遍历文件、`verify_site` 里报告违规。
