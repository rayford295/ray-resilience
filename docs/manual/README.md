# GeoSteward Manual · 使用与机制说明书

## The one-minute version

GeoSteward is an accountable GeoAI risk-analyst agent: a WebGIS and
installable smartphone app (PWA) that answers what hazards threaten a place,
how exposed and vulnerable it is, and what the evidence actually supports —
an entry for OASIS @ ACM SIGSPATIAL 2026, Track A.

Hazard monitoring ([Tier 1](12-glossary.md) — Watch) is nationwide: any US
location gets the current hazard feed. Exposure and damage analysis (Tiers 2
and 3) exist only inside three deep-case [AOIs](12-glossary.md) — the Eaton
Fire (2025), Hurricane Milton (2024), and Hurricane Ian (2022) — and nowhere
else; a place outside them is told so, not extrapolated to.

The distinguishing property is not how much ground the system covers. It is
that every claim boundary is enforced rather than advisory. The
[Steward Harness](12-glossary.md) makes the geographic limit and the citation
requirement both [fail-closed](12-glossary.md): a request outside a
deep-case AOI is refused as out of scope, tile-level evidence never yields a
parcel-level claim, and a factual sentence the agent cannot cite is refused
rather than softened. What this system will not say is as load-bearing as
what it will.

> **中文。** GeoSteward 是一个具备问责能力的 GeoAI 风险分析智能体——一套可安装到
> 手机的网页地图应用（PWA），回答"受哪些灾害威胁""暴露度与脆弱性如何""证据能支持
> 什么结论"三个问题，是 ACM SIGSPATIAL 大会 OASIS 竞赛 Track A（灾害韧性与脆弱性
> 分析赛道）的参赛项目。
>
> 灾害监测（第 1 层）覆盖全美国；暴露度与损毁分析（第 2、3 层）只在三个深度案例
> 关注区域（AOI）内存在——2025 年 Eaton 火灾、2024 年 Milton 飓风、2022 年 Ian
> 飓风——之外的地方一律被明确告知"超出评估范围"，而不是被外推出结论。
>
> 系统最独特之处不是覆盖面大，而是每条断言边界都被**强制执行**而非仅是文档建议：
> Steward Harness 让地理边界与引证要求都做到失败即拒绝——AOI 外的请求被拒绝，
> tile 级证据推不出 parcel 级断言，无法引证的语句被拒绝而非软化。它不说什么，和
> 说什么同样重要。

## Which parts to read

Three paths through the manual, each starting at that reader's actual first
question rather than at chapter `01`:

- **Maintainer / handover:** `10` → `09` → `02`–`05` — starts with running
  and rebuilding the system, because a handover's first question is "can I
  reproduce this," then what each module does, then why the harness enforces
  what it enforces.
- **Chinese-speaking colleague or student:** `README` → `01` → `06` → `10`,
  with `12` alongside — starts with what the system does and does not cover,
  because that question comes before mechanism, with the glossary open
  throughout for terms without a settled Chinese rendering.
- **Mechanism study:** `02` → `03` → `04` → `05` → `07` — starts inside the
  harness itself, in the order its four validity layers are enforced at
  request time, before reaching the agent that sits on top of them.

A reader who is none of the three: start at `01`. It states what the system
does and, for every capability, what it refuses to do — the fastest way to
learn whether any of the three paths above is worth following further.

> **中文。** 三条路径各自从该读者真正的第一个问题开始，而不是从第 `01` 章开始：
> **接手/维护者**从"能不能重建这个系统"问起，所以先读安装与运行（`10`），再读
> 模块索引（`09`），最后读 harness 为什么这样设计（`02`–`05`）；**中文同行或学生**
> 先弄清系统做什么、不做什么，再进入机制，所以从 `README` 起，经 `01`、`06`，到
> `10`，术语表（`12`）全程放在手边，供查阅还没有固定译法的术语；**机制研究**者
> 直接进入 harness 内部，按四层有效性在一次请求中被执行的顺序阅读（`02` → `03` →
> `04` → `05`），最后看坐在这些层之上的 agent（`07`）。
>
> 如果读者不属于以上三类：从 `01` 开始——它说明系统能做什么，以及**每一项能力拒绝
> 做什么**，是判断上面三条路径哪一条值得继续读下去的最快方式。

## The thirteen files

`01`–`11` do not exist yet; they are listed here as plain names because the
[anchor gate](../../scripts/manual_anchors.py) treats a linked or
inline-code path as a claim that the file resolves. Each becomes a working
link as its chapter is written.

| File | Subject |
|---|---|
| [README.md](README.md) | Index · one-minute version · three reading paths |
| 01-capabilities.md | Capability catalogue |
| 02-harness-outcome-audit.md | Validity layers 1–2: checks, audit, manifest |
| 03-policy-claim-plane.md | Layer 3a: what the agent may assert |
| 04-policy-distribution-plane.md | Layer 3b: what a build may publish |
| 05-verifiability-and-live.md | Layer 4: retention, licence, content-free records |
| 06-data-and-evidence.md | Tier-1 watch + three deep cases, field by field |
| 07-gateway-and-agent.md | The agent request lifecycle |
| 08-app-pwa.md | The two-mode front end |
| 09-module-reference.md | File-by-file responsibilities |
| 10-getting-started.md | Install, test, run, rebuild |
| 11-limits-and-gaps.md | What this cannot do |
| [12-glossary.md](12-glossary.md) | Bilingual terminology, binding on the other files |

> **中文。** `01`–`11` 尚未写出，这里以纯文本列出文件名，因为
> [锚点检查脚本](../../scripts/manual_anchors.py) 会把链接或行内代码形式的路径当作
> "这个文件已存在"的断言；每一章写完后才把对应行改成可用链接。
>
> | 文件 | 主题（中文） |
> |---|---|
> | README.md | 索引·一分钟版·三条阅读路径 |
> | 01-capabilities.md | 能力目录（含每项能力的拒绝边界） |
> | 02-harness-outcome-audit.md | 有效性第 1–2 层：结果检查与审计留痕 |
> | 03-policy-claim-plane.md | 第 3a 层：agent 可以断言什么 |
> | 04-policy-distribution-plane.md | 第 3b 层：构建可以发布什么 |
> | 05-verifiability-and-live.md | 第 4 层：留存、许可，以及"内容为空"的实时记录 |
> | 06-data-and-evidence.md | 全美灾害监测与三个深度案例，逐字段说明 |
> | 07-gateway-and-agent.md | agent 请求的完整生命周期 |
> | 08-app-pwa.md | 双模式前端（居民模式 / 规划者模式） |
> | 09-module-reference.md | 逐文件职责索引 |
> | 10-getting-started.md | 安装、测试、运行、重建 |
> | 11-limits-and-gaps.md | 本系统做不到什么 |
> | 12-glossary.md | 双语术语表，对其余各章具有约束力 |

## What this manual is not

This manual has one job: be the single authority on architecture and
mechanism. Four other places in this repository carry different jobs, and a
reader looking for any of them here will get a stale or incomplete answer
instead of the real one:

- [`README.md`](../../README.md) — the entry point: what this is, what
  works and what does not, how to run it. It is also the reviewer-facing
  document, together with [`docs/track_a_alignment.md`](../track_a_alignment.md)
  below; this manual is not written for a reviewer's fifteen-minute pass.
- [`docs/STATUS.md`](../STATUS.md) — the dated ledger: done, next, blocked.
- [`docs/design/specs/`](../design/specs/) — decision records: why a choice
  was made at the time, including the alternatives that were rejected.
- [`docs/track_a_alignment.md`](../track_a_alignment.md) — the mapping to
  the OASIS Track A brief.

The manual does not carry status, and `STATUS.md` does not explain
mechanism. When the two disagree about a fact, the artifacts — the
committed data, code, and test runs — decide, never whichever document was
written more recently.

> **中文。** 这份说明书只有一个职责：作为架构与机制的唯一权威来源。仓库里另外四处
> 承担着不同的职责，在这里找它们只会得到过时或不完整的答案：
>
> - `README.md`——入口文档：这是什么、能做什么不能做什么、怎么运行；它同时是
>   面向评委的文档，与 `docs/track_a_alignment.md`（见下）一起承担这个角色——
>   这份说明书不是为评委的十五分钟通读写的。
> - `docs/STATUS.md`——带日期的台账：已完成 / 下一步 / 被阻塞。
> - `docs/design/specs/`——决策记录：当时为什么这样选，包括被否决的方案。
> - `docs/track_a_alignment.md`——与 OASIS Track A 参赛说明的对应关系。
>
> 说明书不承载状态，`STATUS.md` 不解释机制。两者对同一个事实有分歧时，以
> artifact——已提交的数据、代码与测试结果——为准，而不是看哪份文档写得更晚。
