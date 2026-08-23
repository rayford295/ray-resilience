# 12. Glossary

This file fixes one English term, one Chinese rendering, one one-line definition, and one
repository anchor for each entry below. Chapters `01`–`11` link here on the first use of a term
and reuse the rendering in this table verbatim rather than inventing their own — that is what
makes this file binding rather than a convenience index.

> **中文。** 本文件为下表中的每个术语钉死一个英文词、一个中文译法、一行定义和一个仓库锚点。
> `01`–`11` 各章在术语首次出现处链接到本文件，并原样复用这里的译法，而不是各自另译——
> 这正是本文件具有约束力、而非仅是一份索引的原因。

The `中文` column is a restatement chosen for reuse, not a gloss coined on the spot: where a
Chinese-speaking reader needs context the English term does not spell out — what an agency is,
what a feed covers, why a number is the one that matters — that context lives in the `What it is`
column, and the `中文` column stays short enough to drop into a sentence.

> **中文。** `中文` 列是为了被反复引用而选定的译法，不是临时想出来的注释：中文读者需要的、
> 英文术语本身没写明的语境——某机构是什么、某数据源覆盖什么、为什么某个数字才是关键——
> 都放在 `What it is` 列里，`中文` 列则保持简短，方便直接嵌入句子。

| Term | 中文 | What it is (one line) | Specified in |
|---|---|---|---|
| AOI | 关注区域（AOI） | The event's geographic boundary. Exposure and damage-assessment claims are authorized only inside it; watch/monitoring claims are authorized at any location and any evidence tier, inside or outside every AOI. | `src/geosteward/harness/policy_v1.yaml` |
| artifact ID | 制品 ID | The first 12 hex characters of an artifact's manifest SHA-256, used as a citation tag (`[artifact:XXXXXXXXXXXX]`) so a sentence can be traced back to the committed, hashed product it came from. | `src/geosteward/gateway/context.py` |
| artifact manifest | 制品清单 | The append-only `artifact_manifest.jsonl` for one event: one row per artifact, recording its kind, producing agent, inputs, and sha256. | `src/geosteward/agents/base.py` |
| audit log | 审计日志 | The append-only JSONL log of every consequential action — pipeline stage, policy refusal, human trade-off adjustment — with every row stamped with a run ID so re-run attempts stay distinguishable. | `src/geosteward/harness/audit.py` |
| CAL FIRE DINS | CAL FIRE DINS（损毁勘查） | Damage Inspection (DINS): a per-structure post-fire structure survey conducted by CAL FIRE, the California state fire and forestry agency; this project treats the points as parcel-level ground truth, caps public products at tile resolution, and registers the point layer itself as a restricted-resolution artifact never shipped to the resident-facing app. | `src/geosteward/deepcase/dins.py` |
| CDC SVI | CDC SVI（社会脆弱性指数） | The Social Vulnerability Index published by the US Centers for Disease Control and Prevention / ATSDR: tract-level percentile ranks (`RPL_*`); attaching a tract-level rank to an H3 cell is a downscaling approximation the project declares on every output row. The 2022 vintage is the one joined onto this project's damage grids. | `src/geosteward/deepcase/svi.py`, `scripts/build_eaton_svi.py` |
| claim plane | 断言平面 | The half of `policy_v1.yaml` scoping what the agent may assert per request — by role, purpose, resolution, evidence tier, AOI membership, and verifiability. First-match-wins over ordered rules; unmatched requests are denied. | `src/geosteward/harness/policy_v1.yaml` |
| declared unknowns | 声明未知项 | Gaps in the evidence stated explicitly, with the same prominence as what is known, rather than silently missing — Tier-1 watch output, for instance, declares up front that it supports monitoring only, no damage or exposure conclusions. | `src/geosteward/watch.py` |
| distribution plane | 发布平面 | The half of `policy_v1.yaml` scoping what a build may publish, over each artifact's `resolution_cap`, `audience`, and `license`; `verify_site()` checks an assembled site tree against the resulting allowlist by set difference, and CI fails the deploy on a violation. Added after the 2026-08-20 incident, alongside the claim plane rather than folded into it. | `src/geosteward/harness/policy_v1.yaml`, `src/geosteward/harness/publication.py` |
| fail-closed | 失败即拒绝（fail-closed） | The `default_deny()` decision every policy plane falls back to when no rule matches: deny the request and record why, rather than allowing by default. | `src/geosteward/harness/policy.py` |
| H3 r9 | H3 r9（分辨率 9 级网格） | The H3 hexagonal grid at resolution 9, roughly 0.1 km² per cell — the finest geography the project's evidence supports a statement about. | `src/geosteward/gateway/steward.py` |
| NIFC/WFIGS | NIFC/WFIGS（国家跨部门消防中心野火地理服务） | The US National Interagency Fire Center's Wildland Fire Interagency Geospatial Services feed: a keyless, current-incident wildfire source feeding the nationwide Tier-1 watch layer. | `src/geosteward/sources/nifc.py` |
| resolution cap | 分辨率上限（resolution cap） | The finest geography an artifact kind can support a statement about (`parcel`, `tile`, `event`, `dataset`, `source`, …), declared per artifact class; a kind absent from the declaration is denied publication rather than assumed safe. | `src/geosteward/harness/policy_v1.yaml` |
| Steward Harness | Steward Harness（问责框架） | The accountable layer around the agents: executable spatial checks (outcome), append-only audit with artifact hashing (process), and a declarative policy engine scoping what may be claimed (institutional). | `src/geosteward/harness/__init__.py` |
| tier (1/2/3) | 层级（1/2/3 级） | The evidence ladder a place sits on: Tier 1 (Watch) is nationwide near-real-time hazard monitoring; Tier 2 (Analysis) is tile-level exposure × vulnerability inside one of the three deep-case AOIs; Tier 3 (Evidence) is reliability-gated cross-view damage assessment, available only where that evidence exists. | `README.md` |
| validity (outcome / process / institutional) | 有效性（结果 / 过程 / 制度） | The three conditions the Steward Harness enforces during operation: outcome (executable spatial checks — CRS, join integrity, bounds, mandatory uncertainty), process (append-only provenance and fail-closed stages), and institutional (the two declarative policy planes). | `README.md` |
| verifiability (`retained` / `re-derivable` / `cited-only`) | 可验证性（retained 留存 / re-derivable 可复现 / cited-only 仅可引证） | A totally ordered axis, weakest first, stating what a *reader* can do to check a piece of support: open a hashed copy committed in this repository (`retained`), re-issue the same request with their own key and compare response digests (`re-derivable`), or check only that the cited references exist (`cited-only`). It is **orthogonal to tier**: tier encodes how fresh and deep the evidence is, verifiability encodes what a reader — not the project — can independently confirm, and a live third-party lookup can be perfectly current and accurate while still being uncheckable by anyone without a key. Where a claim draws on several supporting sources, it takes the weakest-link value among them, never the strongest. | `src/geosteward/harness/policy.py` |
| weakest-link | 短板原则（weakest-link） | The rule combining verifiability across several supporting sources: a claim is no more verifiable than its weakest support, so an answer drawing on both a hashed grid and a live lookup is `re-derivable`, not `retained` — taking the maximum or averaging would let strong evidence launder weak evidence into the same standing. | `src/geosteward/harness/policy.py` |
