# Design — a bilingual manual for GeoSteward

**Date:** 2026-08-23 · **Status:** approved (structure and sourcing rules approved by the owner in
brainstorming, 2026-08-23) · **Scope:** documentation only; no behaviour change to shipped code,
with one new maintenance script.

## 1. The problem this solves

A reader arriving at this repository cannot currently form a correct picture of what it does.

The README is dense and accurate but is written as an entry point, not an explanation: 138 lines
covering positioning, a works/does-not table, the harness rationale, tiers, a quick start, and a
repository map. It answers "should I look further" well and "how does this actually work" barely.

Worse, two documents actively misdescribe the system:

- **`docs/architecture.md`** is titled *DisasterPilot architecture*, and it is wrong in two
  different ways that need separating. Some claims are simply **false**: it points at
  `src/disasterpilot/sources/` (the package was renamed `geosteward` on 2026-08-19), and its source
  table lists a Zhejiang Water Resources typhoon API as the only live connector with USGS as
  *planned* — the live connectors are USGS, NWS, NHC and NIFC, and the typhoon module is legacy code
  pending retirement. Other claims are **superseded rather than false**: the five agent roles
  (WATCHER / DOSSIER / EXPOSURE / EVIDENCE / DECISION) still exist as modules under
  `src/geosteward/agents/`, but they are no longer how the system is organised — the current
  architecture is three loosely coupled planes, and the deep cases are built by
  `scripts/build_*_case.py`, not by that agent chain. Its closing section describes LLM integration
  as *planned*, which the shipped gateway has overtaken. The artifact-contract section is still
  substantially correct.

  The distinction matters for the retirement decision in §7: a file that is merely out of date can
  be updated, but a file whose organising frame has been replaced needs a replacement, not an edit.
- **`docs/methodology.md`** describes the pre-rework three-phase method built around Super Typhoon
  Bavi: WorldPop/GHS-POP exposure, Sentinel-1 change detection, and a budget-constrained inspection
  route. `STATUS.md` records the routing as **not implemented**. The file reads as a description of
  what exists and is in fact a plan that was partly superseded.

`STATUS.md` already tracks the architecture drift as a known limitation. It has not been fixed
because there was no document to fix it *into*.

So the deliverable is not only new prose. It is a single authoritative description of the
architecture, plus the retirement of the two documents that contradict it. A manual added beside
them would leave a reader with three incompatible accounts and no way to tell which is current.

> **中文。** 现在的问题不是文档少，而是文档互相矛盾。README 写得准但它是入口而不是解释。
>
> `docs/architecture.md` 的错分两种，必须区分开。**确实为假的**：它指向
> `src/disasterpilot/sources/`（包已于 2026-08-19 改名 `geosteward`），数据源表格把浙江水利
> 台风 API 列为唯一 live 连接器、把 USGS 列为"计划中"（实际 USGS / NWS / NHC / NIFC 都已上线，
> 台风模块是待退役的遗留代码）。**被取代而非为假的**：五个 agent 角色
> （WATCHER / DOSSIER / EXPOSURE / EVIDENCE / DECISION）作为模块**仍然存在**于
> `src/geosteward/agents/`，但已不再是系统的组织方式——当前架构是三个松耦合平面，
> 深度案例由 `scripts/build_*_case.py` 构建，不走那条 agent 链。文末把 LLM 集成写成"计划中"，
> 已被上线的 gateway 超越。artifact contract 那一节基本仍然正确。
>
> 这个区分决定了 §7 的退役方式：仅仅过时的文件可以更新，而**组织框架已被替换**的文件
> 需要的是替代品而不是修改。
>
> `docs/methodology.md` 描述的是重构前围绕台风 Bavi 的方法，其中的巡检路径规划至今未实现。
> `STATUS.md` 早就把架构漂移记为已知问题，但一直没修——因为没有一份文档可以修进去。
> 所以交付物不只是新文章，还包括**让那两份矛盾的文档退役**。只加不删，读者会拿到三份
> 互不兼容的说明，且无法判断哪份是当前的。

### Why the documents rotted, which determines how to prevent it

`architecture.md` asserted that `src/disasterpilot/sources/` exists. That assertion became false the
moment the package was renamed, and nothing anywhere failed. The coupling between the document and
the code was purely narrative, so there was no mechanism by which the code could contradict the
document.

This is the same shape as the 2026-08-20 publication-boundary incident, one level up: a correct
declaration with no consumer. There, the manifest declared a `kind` and the build ignored it. Here,
the document declares a path and nothing checks it. The fix has the same shape too — give the
declaration a consumer (§6).

> **中文。** 文档腐坏的根因是**文档与代码之间没有可检测的耦合**。`architecture.md` 声称
> `src/disasterpilot/sources/` 存在，包改名那一刻这条断言就假了，但没有任何东西会因此报错。
> 这与 2026-08-20 的发布边界事故是同一种形状，只是高了一层：声明正确、消费者缺失。
> 修法也是同一种形状——给声明配一个消费者（见 §6）。

## 2. Readers, and what each needs

The owner named three audiences in brainstorming. A fourth candidate — OASIS reviewers — was
explicitly **not** selected: the README plus `docs/track_a_alignment.md` remain the reviewer-facing
path, and this manual is not written for a fifteen-minute judging pass.

| Reader | What they need | Where the manual serves them |
| --- | --- | --- |
| The future maintainer (including the owner in three months) | Module boundaries, data flow, why each design choice was made, where the traps are | `09`, `02`–`05`, `10` |
| Chinese-speaking colleagues and students | A low-friction way in: what the thing does, what the concepts mean, how to run it | `README`, `01`, `06`, `10`, `12` |
| Source material for a patent-disclosure memo | A precise, complete mechanism description | `02`–`05`, `07` |

The third reader creates a distribution conflict, resolved in §3.

> **中文。** 三类读者：接手的维护者、中文同行与学生、以及专利披露备忘的素材来源。
> OASIS 评委被**明确排除**——README 加 `docs/track_a_alignment.md` 仍是面向评委的路径，
> 这份说明书不是为十五分钟的评审通读写的。第三类读者带来一个分发冲突，见 §3。

## 3. Ruling: two documents, not one

A manual detailed enough to explain the mechanism to a newcomer is, functionally, closer to an
enabling disclosure than the design specs currently in `docs/design/specs/` are. The repository
is private today, but blocker #6 in `STATUS.md` is the visibility flip needed for reviewer access,
so anything committed here should be assumed to become public.

Two facts keep this proportionate:

1. The mechanism is **already** described in the repository in enabling detail — the README's
   validity table, `policy_v1.yaml`'s comments, and both design specs. What determines the
   disclosure position is the timing of the visibility flip, not whether one more file is added.
2. A single file cannot satisfy both distribution requirements. Disclosure material wants
   confidentiality until filing; the Chinese-language explanation exists in order to be shared.

**Ruled by the owner, 2026-08-23: split.** The repository manual is written as though it will be
public, and contains no patent intent and no claim-style language. A separate mechanism-disclosure
memo lives **outside the repository** and gets its own spec; it is organised by claim elements
rather than by feature, and it reuses the same facts without reusing the file.

This spec covers the repository manual only.

Two consequences carried forward, not decided here: the standing advice to file a provisional
application before the visibility flip (routed via Texas A&M Innovation Partners), and the standing
rule that the public repository never states that a patent is planned.

> **中文。** 一份足以让新人看懂机制的说明书，在功能上比现在 `docs/design/specs/` 里的
> 设计文档更接近**使能性披露**。仓库现在是 private，但 `STATUS.md` 的 blocker #6（为评委访问
> 而翻转可见性）意味着这里提交的任何东西都应假定会公开。
>
> 两个事实让这件事保持在合理比例内：其一，机制**已经**在仓库里被详细描述了（README 的有效性
> 表格、`policy_v1.yaml` 的注释、两份设计文档），真正决定披露状态的是可见性翻转的时机，而不是
> 多加一个文件；其二，一份文件无法同时满足两种分发要求——披露材料要求提交前保密，中文说明的
> 存在目的就是被分享。
>
> **所有者裁定（2026-08-23）：拆分。** 仓库说明书按"必将公开"来写，不含专利意图、不含权利
> 要求式措辞。机制披露备忘放在**仓库之外**，另起一份 spec，按权利要求要素而非按功能组织，
> 复用同一批事实但不复用文件。本 spec 只覆盖仓库说明书。

## 4. Shape: `docs/manual/`, thirteen numbered files

One 2,000-line bilingual file would be unnavigable and would rot as a single block. The content is
split so each file has one subject and can be read, reviewed, and corrected on its own.

```
docs/manual/
├── README.md                          index · one-minute version · three reading paths
├── 01-capabilities.md                 capability catalogue
├── 02-harness-outcome-audit.md        validity layers 1–2: checks, audit, manifest
├── 03-policy-claim-plane.md           layer 3a: what the agent may assert
├── 04-policy-distribution-plane.md    layer 3b: what a build may publish
├── 05-verifiability-and-live.md       layer 4: retention, licence, content-free records
├── 06-data-and-evidence.md            Tier-1 watch + three deep cases, field by field
├── 07-gateway-and-agent.md            the agent request lifecycle
├── 08-app-pwa.md                      the two-mode front end
├── 09-module-reference.md             file-by-file responsibilities
├── 10-getting-started.md              install, test, run, rebuild
├── 11-limits-and-gaps.md              what this cannot do
└── 12-glossary.md                     bilingual terminology, binding on the other files
```

Three organising views are all present rather than one chosen, at the owner's direction: capability
(`01`), mechanism (`02`–`08`), and module reference (`09`). They are layered rather than merged —
`01` orients, `02`–`08` explain, `09` indexes — and `README.md` routes each reader to the right
entry point instead of expecting a linear read.

### Reading paths in `README.md`

- **Maintainer / handover:** `10` → `09` → `02`–`05`
- **Chinese-speaking colleague or student:** `README` → `01` → `06` → `10`, with `12` alongside
- **Mechanism study:** `02` → `03` → `04` → `05` → `07`

> **中文。** 一个两千行的双语单文件既无法导航，也会作为一整块腐坏。因此按主题拆成 13 个文件，
> 每个文件一个主题，可以独立阅读、评审、修正。
>
> 三种组织视角**全部保留**（按所有者要求）：能力目录（`01`）、机制（`02`–`08`）、模块参考
> （`09`）。它们是分层而非混合的——`01` 定位、`02`–`08` 解释、`09` 索引——`README.md` 把每类
> 读者导向正确的入口，而不是期待线性通读。

### Why the two policy planes get separate files

`03` and `04` both describe rules in `policy_v1.yaml`, and the temptation is to write one chapter
about "the policy engine". That would reproduce the error the 2026-08-20 incident was caused by. The
planes answer different questions — what the agent may *assert*, versus what a build may *publish* —
and the parcel-level DINS file reached the public site precisely because those were treated as one
concern. Keeping them in separate files makes the distinction structural in the documentation, the
same way the two `policy_v1.yaml` sections make it structural in the code.

> **中文。** `03` 和 `04` 描述的都是 `policy_v1.yaml` 里的规则，很容易合成"policy 引擎"一章。
> 那样做会复现 2026-08-20 事故的成因。两个平面回答的是不同问题——agent 可以**断言**什么，
> 与构建可以**发布**什么——而 parcel 级 DINS 文件之所以到了公开站点，正是因为这两件事被
> 当成了一件事。分成两个文件，让这个区分在文档里也是结构性的。

### Why the glossary is load-bearing

`verifiability`, `fail-closed`, `resolution_cap`, `declared unknowns`, and `weakest-link` have no
settled Chinese renderings. Without a binding glossary, twelve files will each invent their own, and
a reader will not be able to tell whether two passages are discussing the same concept. `12` fixes
one rendering per term and the other files conform to it.

> **中文。** `verifiability`、`fail-closed`、`resolution_cap`、`declared unknowns`、
> `weakest-link` 在中文里没有稳定译法。没有一份有约束力的术语表，12 个文件会各译各的，
> 读者无法判断两处是否在讨论同一个概念。`12` 为每个术语钉死一个译法，其余文件服从。

## 5. Bilingual conventions

- **English first, Chinese immediately after, per subsection.** The Chinese passage is a Markdown
  blockquote (`>`) directly beneath the English it restates. Interleaving was chosen over parallel
  files (`MANUAL.md` + `MANUAL.zh.md`) because parallel files drift, and drift is the exact failure
  this manual exists to correct. A reader editing one language sees the other in the same screen.
- **Language-neutral content appears once.** Code blocks, tables of file paths, command lines,
  field names, and diagrams are not duplicated. Tables whose cells are prose get a Chinese
  counterpart table; tables of identifiers do not.
- **The Chinese is a restatement, not a translation.** A Chinese-speaking reader's gap is usually
  not English but US-specific context: what CAL FIRE DINS is, which agency publishes CDC SVI, what
  NIFC/WFIGS covers, why H3 r9 is the resolution that matters here. A literal translation carries
  none of that. Where the Chinese needs a clause the English does not, it gets one.
- **Terminology is bound by `12-glossary.md`.** First use of a glossary term in each file links to
  it.

> **中文。** 英文在前，中文紧随其后作为引用块，以小节为单位。选择交错而非双文件
> （`MANUAL.md` + `MANUAL.zh.md`），因为双文件会漂移，而漂移正是这份说明书要纠正的问题本身。
>
> 语言中立的内容只出现一次：代码块、路径表、命令行、字段名、示意图都不重复。
> 单元格是散文的表格配中文对照表；标识符表格不配。
>
> 中文是**重述而非翻译**。中文读者缺的通常不是英语，而是美国本地语境：CAL FIRE DINS 是什么、
> CDC SVI 由哪个机构发布、NIFC/WFIGS 覆盖什么、为什么这里关键的分辨率是 H3 r9。逐字翻译
> 承载不了这些。中文需要英文没有的分句时，就加上。

## 6. Content sourcing, and the anti-rot mechanism

### Sourcing rules

Every factual assertion traces to one of three things: a committed artifact, a source file, or a
test. Concretely:

- **Numbers come from the artifacts, not from prose.** `STATUS.md` and the README carry figures
  (18,428 DINS points, a 265-cell damage grid, 2,244 matched samples, 212 tests) that were true when
  written. The manual derives them by reading `events/**` and running the suite, because a second
  document copying a first document's numbers doubles the drift surface instead of checking it. The
  suite was confirmed at **212 tests, green**, on 2026-08-23 before this spec was written.
- **Historical narrative cites the incident and spec documents.** The account of the 2026-08-20
  publication boundary belongs to `docs/incidents/2026-08-20-publication-boundary.md`; the manual
  summarises and links rather than re-narrating.
- **Rationale cites the specs.** Where a design decision has a recorded ruling — the three §11
  rulings in the non-retainable-evidence spec, for instance — the manual states the decision and
  links to where it was made, including the alternative that was rejected.
- **Nothing unimplemented is described in the present tense.** `11-limits-and-gaps.md` is the
  designated home for absences, and the capability entries in `01` carry them inline.

### `scripts/manual_anchors.py`

Every capability entry and every module-reference row carries at least one repository-relative path.
The script extracts those anchors from `docs/manual/*.md` and asserts each exists.

```
python scripts/manual_anchors.py list     # every anchor found, with its file and line
python scripts/manual_anchors.py check    # non-zero exit on any anchor that does not resolve
```

`check` runs in CI beside the existing gates. The pattern is deliberately borrowed from
`scripts/publication_boundary.py plan --check`: a convention nobody can verify is a convention that
decays, so the convention is made executable.

**What it catches:** renamed packages, moved modules, deleted files, typo'd paths — the entire class
of failure that made `architecture.md` false.

**What it does not catch:** a path that still resolves while the behaviour behind it has changed.
`gateway/steward.py` will exist long after any particular claim about it stops being true. That
residue is human work, and stating the limit is more useful than implying the gate is complete.

> **中文。** 来源规则：每个事实断言都追溯到提交的 artifact、源文件、或测试三者之一。
>
> **数字从 artifact 读，不从散文抄。** `STATUS.md` 和 README 里的数字（18,428 个 DINS 点、
> 265 格损毁网格、2,244 个匹配样本、212 个测试）在写下时是真的。说明书通过读 `events/**`
> 和跑测试来得到它们——第二份文档抄第一份文档的数字，是把漂移面积翻倍而不是校验它。
> 测试套件已于 2026-08-23 本 spec 撰写前确认为 **212 个测试全绿**。
>
> **历史叙事引 incident 与 spec 文档**，说明书做摘要并链接，不重讲一遍。
> **设计理由引 spec**，包括当时被否决的方案。
> **未实现的东西不用现在时描述**——`11-limits-and-gaps.md` 是缺失项的指定归处。
>
> `scripts/manual_anchors.py` 提取说明书里所有仓库相对路径并断言其存在，`check` 模式进 CI。
> 这个思路是刻意照搬 `scripts/publication_boundary.py plan --check` 的：无法被验证的约定
> 一定会衰变，所以把约定做成可执行的。
>
> **能抓：** 包改名、模块移动、文件删除、路径拼错——正是让 `architecture.md` 变假的那整类问题。
> **抓不到：** 路径仍然解析成功、但其背后行为已经改变。`gateway/steward.py` 会在关于它的
> 任何具体断言失效之后继续存在很久。这部分残余是人的工作，而把这个限制说出来，
> 比暗示这个 gate 是完备的更有用。

## 7. Retiring the two stale documents

- **`docs/architecture.md` is deleted.** Its false claims could be corrected, but its organising
  frame — five agent roles as the shape of the system — has been replaced by the three-plane
  architecture, and correcting a document whose frame is wrong produces a worse document than
  writing a new one (§1). Git history preserves it for anyone who wants the pre-rework picture. A
  deprecation header was considered and rejected: a file that says "this is outdated" at the top and
  then presents a detailed, confident, superseded architecture still misleads a skimming reader.
  The agent modules it describes are real and still present, so they are documented in
  `09-module-reference.md` with their current status — a reader who finds `agents/watcher.py` needs
  to be told what it is and why the deep-case builders do not go through it.
- **`docs/methodology.md` moves to `docs/archive/methodology-bavi.md`.** It describes the Bavi-era
  method, so it belongs beside `events/archive/bavi-2026/`, and it acquires a header stating what it
  is and what superseded it. It is moved rather than deleted because its methodological lineage —
  cross-view reliability gating, spatially blocked evaluation, forecast-conditioned versus observed
  products never mixed in one table — is still the intellectual basis of the evidence tier, and
  because the append-only instinct in this project is right even where it is not strictly required.
- **What survives is absorbed, not lost.** The CrossViewGate methodological lineage and the honesty
  rules go into `06-data-and-evidence.md`; the artifact contract (`EventContext.write_json` /
  `register`, per-artifact agent name, UTC timestamp, input artifact names, append-only reruns,
  fail-closed stages) goes into `02-harness-outcome-audit.md`.
- **`README.md` gains a pointer** to `docs/manual/` in its repository map, and its architecture
  block stays as-is — a short orientation diagram is the right thing for an entry point.

> **中文。** `docs/architecture.md` **删除**：它那些为假的断言本来是可以改的，但它的**组织框架**
> ——以五个 agent 角色作为系统形状——已被三平面架构替换，而修改一个框架错了的文档，
> 得到的结果比重写一份更糟（见 §1）。git 历史保留原文。曾考虑加废弃标头后保留，否决了——
> 一个开头写着"本文已过时"、接下来给出详细、自信、已被取代的架构的文件，仍然会误导略读者。
> 它描述的 agent 模块是真实存在的，因此在 `09-module-reference.md` 里记录其现状——
> 读者翻到 `agents/watcher.py` 时需要被告知它是什么、以及为什么深度案例的构建脚本不走它。
>
> `docs/methodology.md` **移到** `docs/archive/methodology-bavi.md`：它描述的是 Bavi 时期方法，
> 应与 `events/archive/bavi-2026/` 并列，并加上说明它是什么、被什么取代的标头。移动而非删除，
> 因为它的方法谱系——跨视角可靠性门控、空间分块评估、预报条件产品与观测产品绝不混入同一张表
> ——仍是证据层的思想基础；也因为这个项目的 append-only 本能即使在并非严格必要处也是对的。
>
> 仍然成立的内容被**吸收而非丢弃**：方法谱系与诚实规则进 `06`，artifact contract 进 `02`。
> `README.md` 在仓库地图里加一行指向 `docs/manual/`，其架构框图保持原样——入口文档需要的
> 就是一张简短的定位图。

## 8. Division of labour among the four document families

Stated explicitly, because the failure mode for a new manual is becoming a fourth redundant account
of the same thing.

| Document | Its one job |
| --- | --- |
| `README.md` | Reviewer entry point: what this is, what works and what does not, how to run it |
| `docs/STATUS.md` | Dated ledger: done / next / blocked |
| `docs/manual/` | **The single authority on architecture and mechanism** |
| `docs/design/specs/` | Decision record: why a choice was made at the time, including rejected alternatives |
| `docs/track_a_alignment.md` | Mapping to the OASIS Track A brief, with absences listed |

The manual does not carry status, and `STATUS.md` does not explain mechanism. When they disagree
about a fact, the artifacts decide.

> **中文。** 明确写出职责划分，因为新说明书最可能的失败模式就是变成同一件事的第四份冗余描述。
> 说明书不承载状态，`STATUS.md` 不解释机制。两者对某个事实有分歧时，以 artifact 为准。

## 9. Per-file content specification

`01-capabilities.md` — one entry per user-visible capability. Every entry carries five fields, in
this order: **what it does / where it is valid (geographic competence) / what evidence backs it /
which files implement it / what it refuses to do.** The fifth field is not decoration. This
repository's distinguishing property is not the number of features but that each has an articulated
refusal boundary — tile-level evidence yields no parcel-level claim, an address outside an AOI is
told so rather than extrapolated to, an uncitable sentence is refused rather than softened. A
catalogue listing only capabilities would omit the most distinctive part of the system and would
read as a stronger claim than the system makes. Capabilities to cover: nationwide Tier-1 watch,
three deep cases, resident mode, planner mode with the trade-off slider, validity badges, lineage
viewer, the agent chat loop, the publication boundary, and offline/installable operation.

`02-harness-outcome-audit.md` — outcome checks (CRS assertions, join integrity, sanity bounds,
mandatory uncertainty) from `src/geosteward/harness/checks/outcome.py`; the append-only audit log and
`run_id` grouping from `audit.py`, including why run recovery reads structural markers rather than
timestamps; SHA-256 artifact hashing and the manifest contract; the fail-closed stage discipline; and
the preserved real catch where an over-strict join assertion was rejected and corrected.

`03-policy-claim-plane.md` — the policy engine (ordered rules, first match wins, default deny),
construction-time validation and why an unknown match key must fail loudly at load, deterministic
request classification, each claim rule in `policy_v1.yaml` with the question it answers, and the
claim post-check with its closed exemption set and the citation-by-default inversion.

`04-policy-distribution-plane.md` — `artifact_classes` and the three attributes
(`resolution_cap` / `audience` / `license`), the distribution rules, `publication_boundary.py`
(`plan` / `plan --check` / `verify`), the two independent defences (denying a classified artifact
versus denying an unrecognised file), the CI gates, and a summary of the 2026-08-20 incident with a
link to the full account.

`05-verifiability-and-live.md` — the `verifiability` axis (`retained` > `re-derivable` >
`cited-only`, totally ordered, weakest-link) and why it is orthogonal to tier; the `license`
attribute; the two regimes (structured APIs re-derivable by request plus response digest, grounded
generation falling through to default-deny); the content-free record in `src/geosteward/live/`; the
containment property test; and the standing limitation that neither adapter has ever run against a
live API, so `events/live_evidence.jsonl` does not exist outside tests.

`06-data-and-evidence.md` — the four Tier-1 connectors with their failure modes; the three deep
cases with, for each, the AOI, inputs, output grids field by field, declared unknowns, and excluded
sources; the absorbed CrossViewGate methodological lineage and honesty rules; the dataset registry
and its 33 GB workstation dependency; and the GenDisasterSVI ruling (street imagery excluded as
model-generated, `post_sat` confirmed real).

`07-gateway-and-agent.md` — the request lifecycle end to end (classify → policy pre-check → evidence
retrieval from manifest-listed artifacts only → generation → claim post-check → audit), the
provider-agnostic LLM client, the four response types, why the model never decides its own
authorization, the adversarial test suite, and the hardening that must precede any hosted
deployment.

`08-app-pwa.md` — the two modes, the layer catalogue, `lib/coverage.js` and its three states
(`covered` / `not_covered` / `unknown`) with why the third exists, `lib/watch.js` and the
mapped-of-total badge, `lib/citations.js` and live-chip rendering, the lineage panel, the chat panel,
and the build-time artifact sync.

`09-module-reference.md` — every file under `src/geosteward/`, `gateway/`, `scripts/`, and `app/src/`
with its responsibility, its dependencies, and its tests. Includes the two legacy modules
(`sources/zj_typhoon.py`, `hazards/typhoon.py`) marked as pending retirement, since a reader will
otherwise wonder why a typhoon API sits in a US-only system.

`10-getting-started.md` — install, run the suite, run the app, run the gateway with Ollama, and what
can and cannot be rebuilt from a fresh clone. The workstation constraint is stated plainly: the deep
case builders read a private 33 GB corpus, so `events/` cannot be regenerated by a third party, and
what a reviewer can verify is the committed artifacts, their hashes, and their audit logs.

`11-limits-and-gaps.md` — geographic competence limits, the never-executed live adapters, the
unhosted and unhardened gateway, citation click-through absent, planner adjustments not persisted,
inspection routing not implemented, NWS zone alerts counted but not displayed, and the missing
release metadata.

`12-glossary.md` — one binding Chinese rendering per term, with a one-line definition and a link to
where the concept is specified. Minimum set: AOI, artifact ID, audit log, CAL FIRE DINS, CDC SVI,
claim plane, declared unknowns, distribution plane, fail-closed, H3 r9, manifest, NIFC/WFIGS,
resolution cap, Steward Harness, tier, validity (outcome/process/institutional), verifiability,
weakest-link.

> **中文。** 逐文件内容规格如上。其中 `01` 每个条目的第五个字段"**拒绝做什么**"不是装饰：
> 这个仓库的特点不是功能多，而是每个功能都有明确的拒绝边界——tile 级证据不产出 parcel 级断言、
> AOI 外的地址被告知在评估范围外而不是被外推、无法引用的句子被拒绝而不是被软化。一份只列
> "能做什么"的目录会漏掉这个系统最独特的部分，读起来还会比系统实际的主张更强。

## 10. Verification

The manual is prose, so "tests pass" is not the standard. Four checks:

1. **`python scripts/manual_anchors.py check` exits zero.** Every path anchor resolves. This is the
   one mechanical gate, and it runs in CI.
2. **Every number was read from an artifact or a test run during writing**, not copied from
   `STATUS.md` or the README. Where a figure appears in both, they must agree; a disagreement is a
   finding to report, not to smooth over.
3. **Fresh-reader test.** Someone with no prior context reads `docs/manual/` and answers four
   questions: what does this repository do, where does its competence end, what does it refuse to do,
   and what is not implemented. Wrong or unsupported answers are gaps in the manual, not reader
   error. The reader can be a colleague, or — at the owner's request — a subagent given the manual
   and nothing else.
4. **Terminology consistency.** Every glossary term is rendered in Chinese exactly as `12` specifies,
   checked by grep over the manual.

Unit tests are added for `scripts/manual_anchors.py` itself — anchor extraction, a resolving anchor,
a non-resolving anchor, and the exit code — following the repository's existing convention that a
gate is not trusted until it has been shown to fail on the thing it exists to catch.

> **中文。** 说明书是散文，所以"测试通过"不是标准。四项检查：
> 锚点脚本 `check` 退出码为零；每个数字都是撰写期间从 artifact 或测试运行中读出的
> （在两处都出现的数字必须一致，不一致是需要报告的发现而不是需要抹平的问题）；
> 无上下文的 subagent 读完说明书后能正确回答"这个仓库做什么、能力边界在哪、拒绝做什么、
> 什么没实现"；以及术语中文译法与 `12` 完全一致（用 grep 检查）。
>
> `scripts/manual_anchors.py` 自身要有单元测试——锚点提取、能解析的锚点、不能解析的锚点、
> 退出码——遵循这个仓库既有的约定：一个 gate 在被证明能对它存在所要抓的东西报错之前，
> 不值得信任。

## 11. Out of scope

- **The disclosure memo.** Separate document, outside the repository, its own spec (§3).
- **Rewriting `README.md`.** It gains one pointer. It is well-shaped for its job.
- **Rewriting `docs/track_a_alignment.md`.** It is current and reviewer-facing.
- **Fixing the code the manual documents.** Where writing the manual surfaces a defect, it is
  reported and tracked, not fixed in the same change — documentation work that quietly edits
  behaviour is unreviewable.
- **Translating the design specs or the incident document.** They are decision records; the manual
  links to them.
- **A documentation site generator.** Markdown in the repository renders on GitHub and is what a
  maintainer will actually read.

> **中文。** 范围之外：披露备忘（另起 spec）；重写 README（只加一行指针）；重写
> `track_a_alignment.md`；修复说明书记录过程中发现的代码缺陷（报告并跟踪，不在同一次改动里修
> ——悄悄改行为的文档工作是无法评审的）；翻译设计文档与事故文档（它们是决策记录，说明书链接
> 过去即可）；文档站点生成器（仓库里的 Markdown 在 GitHub 上直接渲染，也是维护者真正会读的
> 东西）。

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| The manual becomes the fourth stale document | §6 anchor gate catches path rot; §8 division of labour prevents overlap; §7 removes the competing accounts |
| Thirteen files, and nobody reads any of them | `README.md` routes by reader instead of assuming a linear read; `01` alone answers the owner's original question |
| The Chinese half drifts from the English | Interleaving makes them adjacent in one file; §5 forbids parallel files for this reason |
| Writing surfaces defects and the work sprawls | §11 forbids fixing in place; findings are reported and tracked |
| Detail crosses into an enabling disclosure | §3 keeps patent material out of the repository entirely; the visibility-flip timing remains the owner's decision |

> **中文。** 风险与对策如上表。最主要的风险是说明书自己变成第四份过时文档——对策是
> §6 的锚点 gate 抓路径腐坏、§8 的职责划分防止重叠、§7 移除竞争性描述。

## 13. Definition of done

- `docs/manual/` exists with all thirteen files, bilingual throughout per §5.
- `docs/architecture.md` deleted; `docs/methodology.md` moved to `docs/archive/methodology-bavi.md`
  with a superseded-by header; surviving content absorbed per §7.
- `README.md` repository map points to `docs/manual/`.
- `scripts/manual_anchors.py` implemented with unit tests, wired into CI, `check` green.
- The full Python suite still green (212 at the time of writing, plus the new anchor tests).
- The fresh-reader test in §10.3 passes.
- Defects surfaced while writing are filed in `STATUS.md`, not silently fixed.

> **中文。** 完成标准如上。
