# 02 · Outcome validity and the provenance record

The [Steward Harness](12-glossary.md) enforces three conditions during
operation — [validity (outcome / process / institutional)](12-glossary.md) —
and this chapter covers the first two: outcome, the executable spatial
checks an artifact must pass before it is accepted, and process, the
append-only record of what ran, on what inputs, and with what result. The
institutional condition's two planes (what an agent may assert, what a build
may publish) are `03` and `04`; what a reader can independently verify about
any of it is `05`. Read in that order, this chapter is where the harness
starts: before a stage's output can be claimed to be anything, it has to
survive the checks below, and every attempt — successful or not — becomes a
permanent row in the record this chapter describes.

> **中文。** Steward Harness（问责框架）在运行期间强制执行三项条件——
> 有效性（结果 / 过程 / 制度）——本章讲其中前两项：结果，即一个产物在被接受前必须
> 通过的可执行空间检查；过程，即"跑了什么、用了什么输入、结果如何"的只增不改的
> 记录。制度条件的两个平面（agent 可以断言什么、构建可以发布什么）留给 `03`、
> `04` 两章；读者能独立核实到什么程度，留给 `05`。按这个顺序读下去，
> 本章正是 harness 真正开始的地方：在一个处理阶段的产出能被拿去断言任何事情之前，
> 它得先扛过下面这些检查；而无论这次尝试成功与否，它都会在本章要讲的记录里留下
> 一行永久痕迹。

## The four outcome checks

Every outcome check is an ordinary, pure Python function in
`src/geosteward/harness/checks/outcome.py`, and every one of them returns the
same frozen `CheckResult(check, passed, detail)` dataclass rather than
raising or logging on its own — the module's docstring states the split of
responsibility directly: "Every check is a pure function returning a
CheckResult; callers decide whether a failed check aborts the stage (fail
closed) or is recorded." The four, by their real names and signatures:

1. `check_crs(declared, expected="EPSG:4326")` — the coordinate reference
   system a caller declares must equal the expected one (WGS84 by default);
   an undeclared CRS and a mismatched one both fail, with a detail string
   naming which.
2. `check_join_integrity(left_ids, joined_ids, min_coverage=1.0)` — after a
   spatial or tabular join, every ID on the joined side must appear in the
   left side (no orphans), and the fraction of the left side actually
   matched must reach `min_coverage`, 100% unless a caller overrides it.
3. `check_bounds(name, value, minimum, maximum)` — a named scalar (a
   latitude, a percentile rank, anything with a known valid range) must fall
   inside `[minimum, maximum]`.
4. `check_uncertainty_present(payload, field="uncertainty")` — the payload
   dict must contain the named field at all.

That last check has a real limitation worth stating plainly rather than
discovering later: `check_uncertainty_present` tests `field in payload`, so
`{"uncertainty": None}` passes exactly as readily as a populated uncertainty
object — the check verifies that a feature *declares* an uncertainty slot,
not that the slot says anything. See 11-limits-and-gaps.md for this and the
project's other open items.

`CheckResult.as_row()` produces exactly the `{"check", "passed", "detail"}`
mapping that shows up, one row per check, under the `"check"` action in
every committed `audit_log.jsonl` — the log below is not a separate
description of what a check did; it is that same `CheckResult` value,
serialized.

> **中文。** 四项结果检查都是 `src/geosteward/harness/checks/outcome.py` 里的
> 普通纯函数，每个都返回同一种不可变的 `CheckResult(check, passed, detail)`，
> 自己不抛异常也不写日志——模块自己的文档字符串把职责分工说得很直接："每项检查都是
> 返回 CheckResult 的纯函数；由调用方决定检查失败时是让处理阶段中止（失败即拒绝）
> 还是仅作记录。"四项检查依次是：`check_crs`（校验声明的坐标参照系是否等于期望值，
> 默认 EPSG:4326）、`check_join_integrity`（联接后要求联接侧的每个 ID 都能在左侧
> 找到、且左侧被实际匹配到的比例达到 `min_coverage`，默认要求 100%）、
> `check_bounds`（要求一个命名的标量落在给定的 `[minimum, maximum]` 区间内，
> 比如纬度或某个百分位排名）、`check_uncertainty_present`（要求 payload 里存在
> 指定字段，默认字段名 `uncertainty`）。最后这一项有一个必须直说的真实局限：
> `check_uncertainty_present` 判断的是"字段是否存在"，所以 `{"uncertainty":
> None}` 和一个内容完整的不确定性对象一样能通过检查——它验证的是"这个要素声明了
> 一个不确定性槽位"，而不是"这个槽位里说了什么"。参见 11-limits-and-gaps.md
> 了解这一点和其他尚待解决的问题。`CheckResult.as_row()` 生成的正是下一节所说的
> 审计日志里、每条 `"check"` 记录的 `{"check", "passed", "detail"}`
> 结构本身——日志不是对检查结果的另一份转述，它就是这同一个 `CheckResult` 值被
> 序列化后的样子。

## The artifact contract

Every agent's output goes through the same contract, defined once in
`src/geosteward/agents/base.py` and used by every pipeline stage and every
deep-case build script:

- An artifact is an `Artifact(path, kind, agent, created_utc, inputs,
  notes, sha256)` — a file on disk plus its provenance. Its path lives
  under `events/<event-id>/`, in a subdirectory named for the stage that
  produced it (`exposure/`, `dossier/`, `decision/`, `snapshots/`, and so
  on across the committed events).
- `EventContext.register()` appends one row per artifact to the event's
  [artifact manifest](12-glossary.md), `events/<event-id>/artifact_manifest.jsonl`,
  opening the file in append mode and never rewriting a previous line. The
  row is `Artifact.manifest_row()`: `path`, `kind`, `agent`, `created_utc`,
  `inputs` (the names of the artifacts it was built from), `notes`, and
  `sha256` — computed by `sha256_file()` from
  `src/geosteward/harness/audit.py` if the caller did not already supply
  one.
- Whether a rerun ever touches the bytes already on disk depends on the
  stage, and the two committed patterns are both real. `TyphoonWatcher` in
  `src/geosteward/agents/watcher.py` writes each capture to
  `snapshots/<event-id>_<stamp>.json`, a path built from the run's own UTC
  stamp — the class docstring says so directly: "Snapshot files are
  append-only and timestamped; earlier captures are the frozen
  forecast-conditioned record used for post-event validation." No later run
  can overwrite an earlier one because no two runs share a filename. Other
  stages — every deep-case build script included — write to a fixed
  relative path instead, so a rerun *does* replace the file's bytes on
  disk; what survives is the manifest row, not the byte content. This is
  not a gap in the contract, it is verifiable in the committed data:
  `events/eaton-2025/artifact_manifest.jsonl` has two rows for
  `events/eaton-2025/snapshots/svi/eaton_aoi_tracts_2020.geojson` — one at
  `20260820T022422Z`, one at `20260820T022619Z`, matching the two attempts
  described in the last section of this chapter — each with its own
  `created_utc` and its own recomputed `sha256`, neither row edited or
  removed by the other. A reader who wants the frozen bytes of a
  fixed-path artifact's earlier version has to have retained the file
  separately; a reader who wants a permanent record that a build with a
  given hash existed at a given time always has it, because the manifest
  never forgets a row.
- An agent that is missing a required input fails closed with a stated
  reason rather than producing a hollow result. `CrossViewEvidence.run()`
  in `src/geosteward/agents/evidence.py` raises `FileNotFoundError` naming
  the missing `evidence/imagery_manifest.csv` if post-event imagery has not
  arrived yet, rather than interpolating a damage number. Where an
  orchestrator runs a sequence of such agents, it records the failure
  instead of continuing as if nothing happened:
  `run_pre_event()` in `src/geosteward/pipeline.py` wraps each agent's
  `run()` in a `try`/`except`, and on failure writes
  `{"agent": ..., "status": f"failed: {error}"}` as that stage's audit row
  before stopping the sequence — the exception's own reason ends up in the
  permanent record, not just on a console. The deep-case build scripts
  enforce the same contract locally rather than through this orchestrator:
  see the next section for how, and the final section for what it caught.

> **中文。** 每个 agent 的产出都遵循同一套契约，定义在
> `src/geosteward/agents/base.py` 里，被每一个流水线阶段和每一个深度案例构建脚本
> 复用：一个 artifact 就是一个 `Artifact(path, kind, agent, created_utc,
> inputs, notes, sha256)`——一份文件加上它的来源信息；其路径位于
> `events/<event-id>/` 下，按产出它的处理阶段命名子目录（如 `exposure/`、
> `dossier/`、`decision/`、`snapshots/` 等，视具体事件而定）。
> `EventContext.register()` 会以追加模式打开该事件的制品清单
> （`events/<event-id>/artifact_manifest.jsonl`），为每个 artifact 追加一行、
> 从不改写已有的行；这一行就是 `Artifact.manifest_row()`：路径、种类、
> 生成它的 agent、UTC 时间戳、输入（即它是由哪些产物构建出来的）、备注，以及
> sha256——若调用方没有预先提供，就由 `src/geosteward/harness/audit.py` 里的
> `sha256_file()` 计算。一次重跑是否会真的覆盖磁盘上已有的字节，取决于具体阶段，
> 已提交的代码里两种模式都存在：`src/geosteward/agents/watcher.py` 里的
> `TyphoonWatcher` 把每次抓取写到 `snapshots/<event-id>_<stamp>.json`——路径本身
> 就包含这次运行的 UTC 时间戳，这个类自己的文档字符串写得很直接："快照文件只增不改
> 且带时间戳；更早的抓取就是用于灾后验证的、被冻结的灾前预测记录"——因此不会有两次
> 运行共用同一个文件名，后来的运行也就不可能覆盖更早的运行。但其他阶段——包括每一个
> 深度案例构建脚本——写入的是固定路径，一次重跑确实会替换磁盘上的字节；能留存下来的
> 是清单里的那一行记录，而不是字节内容本身。这不是契约的漏洞，而是已提交数据里可以
> 直接核实的事实：`events/eaton-2025/artifact_manifest.jsonl` 里，
> `events/eaton-2025/snapshots/svi/eaton_aoi_tracts_2020.geojson` 这同一个路径
> 有两行记录——一行是 `20260820T022422Z`，一行是 `20260820T022619Z`，正对应本章
> 最后一节讲到的两次尝试——各自带着自己的 `created_utc` 和重新算出的
> `sha256`，谁都没有改写或删掉对方。想要拿到某个固定路径产物更早版本的原始字节，
> 读者得另行自己保留那份文件；但想要一份"某个哈希值在某个时间点确实存在过"的永久
> 记录，读者始终能拿到，因为清单从不遗忘任何一行。缺少所需输入的 agent 会带着明确
> 理由主动拒绝，而不是生成一个空洞的结果：`src/geosteward/agents/evidence.py` 里
> 的 `CrossViewEvidence.run()`，在灾后影像尚未到位时会抛出 `FileNotFoundError`，
> 点名缺失的 `evidence/imagery_manifest.csv`，而不是插值出一个损毁数字。当有编排者
> 依次运行这样一串 agent 时，它会把失败记录下来而不是当作无事发生继续往下走：
> `src/geosteward/pipeline.py` 里的 `run_pre_event()` 用 `try`/`except` 包住每个
> agent 的 `run()`，失败时把 `{"agent": ..., "status": f"failed: {error}"}`
> 写作该阶段的审计行，然后终止这一串运行——异常本身的理由进了永久记录，而不只是
> 打印在控制台上。深度案例构建脚本不是通过这个编排器、而是各自在本地落实同一套契约
> ——具体怎么做见下一节，它拦下过什么见本章最后一节。

## The audit log is append-only

Process validity's other half lives in `src/geosteward/harness/audit.py`,
alongside two small primitives the rest of the harness builds on:
`sha256_file(path)`, used to hash every artifact registered above, and
`new_run_id()`, a fresh 12-character hex identifier generated on demand.
`AuditLog` itself is a dataclass holding a `path` and a `run_id` (defaulted
to `new_run_id()` at construction), and its one method, `record(action,
actor, payload=None, rule_id=None)`, opens that path in append mode and
writes one JSON line — `action`, `actor`, a UTC timestamp, the current
`run_id`, the payload, and an optional `rule_id` — every time it is called.
Nothing about `AuditLog` ever seeks backward in the file; a row, once
written, is permanent. The class docstring is explicit about why an
append-only log has to exist at all: "A stage can be rejected, fixed, and
re-run, and both attempts belong in the log — erasing the rejected one
would erase the evidence that the harness worked."

Because `AuditLog.record` stamps every row it writes with the `run_id` set
when that `AuditLog` instance was created, every row written by one run of
one script shares one `run_id`, and a later rerun (a new `AuditLog`
instance) gets a different one — in principle, enough on its own to group a
stage's attempts without looking at timestamps or check names at all. In
practice, every committed `audit_log.jsonl` under `events/` today — Eaton's
and Ian's included — was written before this field existed: none of their
rows carry a `run_id` key at all. `AuditLog`'s docstring says as much:
"Logs written before this existed are not rewritten; the frontend recovers
their runs from the check sequence instead." That recovery is the subject
of the next section.

> **中文。** 过程有效性的另一半在 `src/geosteward/harness/audit.py` 里，旁边还有
> 两个供 harness 其余部分复用的小工具：`sha256_file(path)`（就是上一节给每个
> 已登记 artifact 计算哈希用的那个函数），以及 `new_run_id()`（按需生成一个全新的
> 12 位十六进制标识符）。`AuditLog` 本身是一个数据类，持有一个 `path` 和一个
> `run_id`（构造时默认调用 `new_run_id()` 生成），它唯一的方法
> `record(action, actor, payload=None, rule_id=None)` 每次被调用时都会以追加模式
> 打开该路径、写入一行 JSON——包含 `action`、`actor`、一个 UTC 时间戳、当前的
> `run_id`、payload，以及可选的 `rule_id`。`AuditLog` 从不回头改写文件里已有的
> 内容；一行一旦写下就是永久的。这个类自己的文档字符串直接说明了为什么必须要有这样
> 一份只增不改的日志："一个处理阶段可能被拒绝、被修正、再重跑一次，这两次尝试都该
> 留在日志里——把被拒绝的那次抹掉，就等于抹掉了 harness 确实起作用过的证据。"
> 由于 `AuditLog.record` 会把该 `AuditLog` 实例创建时确定的 `run_id` 盖在它写下
> 的每一行上，同一次脚本运行写下的所有行就会共享同一个 `run_id`，而后续一次重跑
> （对应一个新的 `AuditLog` 实例）会拿到不同的 `run_id`——原则上，光凭这一点就足以
> 把同一处理阶段的多次尝试分组开来，完全不需要再看时间戳或检查名称。但实际情况是，
> 目前 `events/` 下所有已提交的 `audit_log.jsonl`——包括 Eaton 和 Ian 的——都是在
> 这个字段出现之前写下的：它们的每一行都没有 `run_id` 这个键。`AuditLog` 的文档
> 字符串对此说得很清楚："在这个字段出现之前写下的日志不会被重写；前端改从检查序列
> 里恢复它们各自的运行归属。"这种恢复方法正是下一节要讲的内容。

## Recovering runs from structure, not timestamps

Because no committed `audit_log.jsonl` carries a `run_id`, grouping their
rows into runs — a prerequisite for saying anything true about "the latest
run" of a stage, which capability 5 in `01-capabilities.md` depends on —
has to come from two structural markers instead, both implemented in
`stageValidity()` in `app/src/lib/data.js`:

- a `"stage"` row closes the run it belongs to;
- a `"check"` row whose check name repeats the current run's *first* check
  name means the fixed check sequence started over — the only way that
  happens is that the previous attempt died before writing a closing
  `"stage"` row.

Timestamps cannot do this job, and the two committed deep-case logs prove
it from opposite directions rather than the same one:

- **A time-window heuristic would merge two attempts that are not one
  run.** Eaton's `exposure.svi_context` stage aborts at `20260820T022423Z`
  (three check rows in `events/eaton-2025/audit_log.jsonl`, the third a
  failed `join_integrity`) and its corrected re-run starts at
  `20260820T022620Z` — one minute fifty-seven seconds later. Any window
  wide enough to tolerate ordinary rebuild latency would fold these into a
  single "run" and reproduce exactly the double-counting bug capability 5
  describes: nine check rows summed as though one run produced them, when
  no six-check run ever passed and no nine-check run ever existed.
- **A same-timestamp heuristic would split one attempt that is not two.**
  Ian's `evidence.svi_sample_density` stage, in
  `events/ian-2022/audit_log.jsonl`, writes six check rows at
  `20260820T033819Z` and then its seventh check plus its closing `"stage"`
  row at `20260820T033820Z` — one uninterrupted run whose rows straddle a
  wall-clock second boundary. Grouping strictly by identical timestamp
  string would report this as two runs where there was only ever one.

Both failures are real, and they fail for complementary reasons: a
heuristic loose enough to survive Eaton's two-minute gap is tight enough to
be fooled by Ian's one-second one, and vice versa. No single timestamp
window sits between them. `run_id` supersedes both markers once it is
present on a log — `stageValidity()` checks for it first — and the
structural heuristic exists specifically for the logs written before it,
which, per `AuditLog`'s own docstring quoted above, are never rewritten to
add it retroactively.

> **中文。** 由于目前没有一份已提交的 `audit_log.jsonl` 带有 `run_id`，
> 要把日志行归并成一次次"运行"——这是能对某个处理阶段说出"最近一次运行"这类话的
> 前提，`01-capabilities.md` 里能力 5 的有效性徽章正依赖这一点——就只能依靠两个
> 结构性标记，二者都实现在 `app/src/lib/data.js` 的 `stageValidity()` 里：一行
> `"stage"` 记录关闭它所属的这次运行；而一行 `"check"` 记录如果其检查名称与当前
> 这次运行的**第一项**检查名称重复，就说明这套固定的检查序列重新从头开始了——唯一
> 能导致这种情况的原因，就是上一次尝试在写下收尾的 `"stage"` 行之前就已经中断。
> 时间戳做不到这件事，而两份已提交的深度案例日志恰好从相反的两个方向证明了这一点：
> 一个足够宽松的"时间窗口"式启发式会把本不属于同一次运行的两次尝试合并——Eaton 的
> `exposure.svi_context` 阶段在 `20260820T022423Z` 中止
> （`events/eaton-2025/audit_log.jsonl` 里三行检查记录，第三行
> `join_integrity` 失败），其修正后的重跑在一分五十七秒后的
> `20260820T022620Z` 开始；任何宽到能容忍正常重建延迟的窗口都会
> 把这两次尝试并成"一次运行"，正好复现能力 5 里讲到的那个重复计数缺陷——把九行检查
> 当作一次运行产生的结果去求和，而实际上既不存在通过了九项检查的运行，也没有哪次
> 六项检查的运行是从这九行里剥离出来的。反过来，一个按"时间戳完全相同"分组的启发式
> 又会把本属于同一次运行的记录拆开——Ian 的 `evidence.svi_sample_density` 阶段
> （见 `events/ian-2022/audit_log.jsonl`）先在 `20260820T033819Z` 写下六行检查
> 记录，随后第七项检查和收尾的 `"stage"` 行落在 `20260820T033820Z`——这是一次
> 完整不间断的运行，只是记录跨过了一个墙钟秒的边界；按时间戳字符串严格分组会把它
> 报告成两次运行，而它从头到尾只有一次。这两种失败都是真实存在的，而且互为反面：
> 一个宽松到能扛住 Eaton 那两分钟间隔的启发式，恰好窄不到能被 Ian 那一秒钟的边界
> 迷惑，反之亦然——不存在一个居中的时间窗口同时躲开两者。一旦日志上出现
> `run_id`，它就会取代这两个结构性标记——`stageValidity()` 会优先检查这个字段；
> 这套结构性启发式专门用来处理该字段出现之前写下的日志，而根据前面引用的
> `AuditLog` 文档字符串，这些日志不会被回头重写来补上这个字段。

## A real fail-closed catch, preserved

The Eaton example above is not a hypothetical: it is a real assertion the
harness rejected, corrected in the very next attempt, and left in the
record rather than erasing. `scripts/build_eaton_svi.py` joins CDC SVI 2022
tract ranks onto the 265-cell DINS damage grid, and runs two
`check_join_integrity` calls back to back — one confirming every grid cell
was assigned to a tract, the other confirming every assigned tract GEOID
actually came from the fetched Census tract set. That second check
originally required full coverage (`min_coverage=1.0` implicitly, the
function's default) of the fetched tract set by the assigned tracts. The
aborted attempt in `events/eaton-2025/audit_log.jsonl`, at
`20260820T022423Z`, shows exactly that assertion failing: `crs` passes,
the first `join_integrity` passes ("coverage 100.00%, no orphans"), and
the second fails — `"coverage 14.71% below required 100.00%"` — and the
script's own `fail_closed()` helper (which logs every `CheckResult` as a
`"check"` row, then raises `RuntimeError` on the first failure) stops
there; no closing `"stage"` row for this attempt exists, because the
script never reached it.

The assertion was too strict, and the fix is visible in the committed
source, not just inferred from the log: the AOI envelope used to fetch
Census tracts legitimately covers more tracts than the Eaton burn
perimeter actually touches, so requiring the fetched set to be fully
covered by the assigned set was never the right check — a code comment in
`scripts/build_eaton_svi.py` says so directly: "the envelope legitimately
covers more tracts than the burn area touches, so full coverage is NOT
required here." The corrected re-run passes `min_coverage=0.0` to that
second call instead. Its six check rows, starting at `20260820T022620Z` in
the same log, all pass — including the same check re-run with the
corrected threshold, `"coverage 14.71%, no orphans"`, the identical
coverage number that failed a minute and fifty-seven seconds earlier, now
correctly accepted — and the attempt closes with a `"stage"` row carrying
`{"status": "ok", "n_cells": 265, "n_tracts": 20, "n_svi_missing": 0}`.
Both attempts remain in `events/eaton-2025/audit_log.jsonl` today, in that
order, because nothing in this harness erases a rejected attempt once it
has been superseded.

> **中文。** 上一节用到的 Eaton 例子不是假设，而是一次真实被 harness 拒绝、
> 在紧接着的下一次尝试里被修正、并且被完整保留在记录里而非抹去的断言。
> `scripts/build_eaton_svi.py` 把 CDC SVI 2022 的区块排名联接到 265 格的 DINS
> 损毁网格上，背靠背运行两次 `check_join_integrity`：一次确认每个网格都被分配到了
> 某个区块，另一次确认每个被分配到的区块 GEOID 确实来自抓取到的人口普查区块集合。
> 第二个检查最初要求（函数默认的 `min_coverage=1.0`）被分配到的区块要**完全覆盖**
> 抓取到的区块集合。`events/eaton-2025/audit_log.jsonl` 里
> `20260820T022423Z` 那次中止的尝试，记录的正是这条断言的失败：`crs` 通过，
> 第一个 `join_integrity` 通过（"coverage 100.00%, no orphans"），第二个失败——
> "coverage 14.71% below required 100.00%"——脚本自己的 `fail_closed()`
> 辅助函数（把每个 `CheckResult` 记作一行 `"check"`，遇到第一个失败就抛出
> `RuntimeError`）就此止步；这次尝试没有收尾的 `"stage"` 行，因为脚本根本没有
> 走到那一步。这条断言本身定得过于严格，修复方式在已提交的源码里能直接看到，
> 不需要靠日志去推断：用来抓取人口普查区块的 AOI 外包框本来就会合理地覆盖比
> Eaton 火场实际烧到的范围更多的区块，所以要求"抓到的区块集合必须被分配到的区块
> 完全覆盖"从一开始就不是正确的检查——`scripts/build_eaton_svi.py` 里的一行
> 代码注释直接写明了这一点："外包框本来就会合理地覆盖比火场实际烧到的范围更多的
> 区块，所以这里不要求完全覆盖。"修正后的重跑把这第二次调用的 `min_coverage`
> 改成了 `0.0`。同一份日志里从 `20260820T022620Z` 开始的六行检查记录全部通过——
> 包括用修正后的阈值重新跑的同一个检查，"coverage 14.71%, no orphans"，
> 与一分五十七秒前导致失败的那个覆盖率数字完全相同，这次却被正确接受——这次尝试
> 以一行 `"stage"` 记录收尾，内容是 `{"status": "ok", "n_cells": 265,
> "n_tracts": 20, "n_svi_missing": 0}`。两次尝试至今仍然按原本的顺序留在
> `events/eaton-2025/audit_log.jsonl` 里，因为这套 harness 里没有任何机制会在
> 一次被拒绝的尝试被后续尝试取代之后，把它抹去。
