# 07 · The agent, and the harness around it

`Steward.answer()` in `src/geosteward/gateway/steward.py` is where every piece
the two preceding chapters described in isolation runs against one located
question in one call: the [claim plane](12-glossary.md) `03` covers rule by
rule, and [verifiability](12-glossary.md) and the live lookup `05` covers end
to end. Neither is this chapter's to re-derive — `03` owns the eight rules
and what the [audit log](12-glossary.md) records of a decision; `05` owns the
two live-lookup regimes and what `events/live_evidence.jsonl` would hold if
it existed outside a test. What this chapter adds is the sequence: the order
these pieces actually run in in `Steward.answer()`, the two points in that
sequence where deterministic code — never the model — decides what happens
next, and the four shapes a finished response can take. The module's own
docstring states the point this chapter exists to demonstrate, not merely
assert: "Deterministic code classifies the request and verifies the output;
the LLM never decides its own authorization and never gets the last word."

> **中文。** `src/geosteward/gateway/steward.py` 里的 `Steward.answer()`，是前面
> 两章各自单独讲过的两件事，在一次带地理位置的提问里真正合到一起运行的地方：
> `03` 逐条讲过的断言平面，以及 `05` 从头到尾讲过的
> 可验证性（retained 留存 / re-derivable 可复现 / cited-only 仅可引证）与实时
> 查询。这两件事都不是本章要重新讲一遍的内容——`03` 讲清楚了那八条规则、以及
> 审计日志对一次决策记录了什么；
> `05` 讲清楚了两种实时查询机制，以及 `events/live_evidence.jsonl` 如果不是只在
> 测试里存在会装着什么。本章要补上的是顺序：这些环节在 `Steward.answer()` 里
> 实际按什么次序运行，这个顺序里哪两个环节是由确定性代码——而不是模型——决定接下来
> 发生什么，以及一份完成的响应能长成哪四种样子。这个模块自己的文档字符串把本章要
> 论证、而不只是断言的道理写在了最前面："由确定性代码对请求分类、对输出做校验；
> 大模型永远不能决定自己的授权范围，也永远没有最终决定权。"

## The request lifecycle

One request runs through six stages in this order: `classify` → policy
pre-check → evidence assembly from manifest-listed artifacts only → model
generation → `check_claims` post-check → audit, with up to three generation
attempts before a fail-closed refusal. Walking `Steward.answer` (lines
279–435) top to bottom: `classify(question)` (line 280) turns the free-text
question into a `(purpose, resolution)` pair — ordinary Python, not a model
call, and `03` covers exactly how the pattern order encodes policy.
`self.store.evidence_for(lat, lon)` (line 281) then loads whatever committed,
manifest-listed artifacts cover that location — the evidence tier and
[AOI](12-glossary.md) membership a `PolicyRequest` needs come from this call,
which is why it runs before the policy engine can evaluate anything; reading
a local, already-hashed, already-committed file costs nothing and discloses
nothing to anyone, which is a different property from the one the next
paragraph is about — the one that actually matters for a keyed, billable
third-party call: that call only happens later, inside `_lookup`, strictly
after the policy engine has authorized the request, so an unauthorized
question never reaches a third party and never spends money. Verifiability is
computed next (lines 283–294), in three branches keyed on whether the purpose
needs a live source at all and, if so, whether one is configured: `RETAINED`
for any purpose that never touches a live source; the
[weakest-link](12-glossary.md) of `RETAINED` and the configured source's own
declared verifiability when a live source *is* configured; and, when the
purpose needs one but none is configured, the fixed value `LIVE_PURPOSES`
declares for that purpose (`RE_DERIVABLE` for `facility_context`) — a
deliberate stand-in so the policy can still tell "in an AOI, but the
capability is absent" apart from "out of the AOI entirely," rather than
collapsing both into the same `default-deny`. A `PolicyRequest` is built from
`role`, `purpose`, `resolution`, the evidence's tier and AOI membership, and
that verifiability value (lines 296–303), the whole request is written to the
audit log as a `gateway_request` row — role, exact `lat`, `lon`, and the
question's own text, unredacted; this fact returns with consequences in [Not
safe to host yet](#not-safe-to-host-yet) — and only then does
`self.policy.evaluate(request)` run (line 312).

The request shape itself is either-or, and the check runs twice for the same
request rather than once. `AskRequest.exactly_one_location`
(`gateway/main.py`) rejects a request carrying both `lat`/`lon` and `area`,
or neither, before it ever reaches `Steward.answer`; `answer()` repeats the
identical
`has_area` / `has_point` / `has_any_coord` logic on its own keyword
arguments, so a caller that skips the HTTP layer entirely still cannot skip
the guard. The area branch sits exactly where the point lookup used to sit
alone, at the same point in this six-stage sequence: `self.store.
evidence_for_area(area) if area is not None else self.store.evidence_for(lat,
lon)` runs before `classify(question)`'s purpose ever reaches the policy
engine, so an area-shaped request is decided by the same pre-check ordering a
point-shaped one is — a rectangle touching none of the three deep-case AOIs
comes back `in_aoi: false` exactly as an out-of-bounds point would, and
`deny-outside-aoi` denies it the same way. One field only an area request
ever populates: `EventEvidence.cells`, the H3 r9 tile IDs `evidence_for_area`
actually matched, which rides through unchanged into the returned `answer`'s
own `cells` field — `08` covers the app rendering those as a highlight. A
point-shaped request's `cells` stays an empty list, because `evidence_for`
never assigns it; a point answer has one tile to speak of and already names
it in its own text.

A refusal here (lines 313–322) returns immediately: no live lookup has been
attempted, no evidence has been assembled into a prompt, and the model has
not been invoked at all. An authorized request with a located tile but zero
committed facts for it returns a declared no-evidence response just as
quickly (lines 324–332) — again before any model call. Only past both of
those gates does anything resembling "fetching" for a live answer happen:
when the classified purpose needs a live source, `self._lookup` (lines
238–277) computes an [H3 r9](12-glossary.md) cell from the raw coordinates,
issues the request, and calls `LiveEvidenceRecorder.record` (`05` covers what
that row holds and why) *before* using the result for anything — the ordering
inside `_lookup` is deliberate for the same reason the ordering inside
`answer` is: a lookup cannot end up cited without having been attested first.
What reaches the model is a category-count line, never the provider's raw
content (`05` again). The retained facts and any live line are joined into one
evidence block (lines 356–369), and only at that point does
`self.llm(messages)` run (line 374), inside a loop bounded by
`self.max_attempts` (default 3, line 217). Every attempt is checked by
`check_claims` (line 383) and recorded as a `gateway_post_check` audit row
(lines 384–387) before either an answer is returned (lines 397–415) or a
correction turn is appended to the conversation and the loop retries (lines
416–425). A third failing attempt does not relax the requirement; it produces
the fail-closed refusal at lines 427–435, `rule_id: "claim-post-check"`,
naming every violation the last draft still carried.

> **中文。** 一次请求依次经过六个阶段：`classify`（分类）→ 策略预检查 → 只从
> 已在制品清单里登记过的产物中组装证据 → 模型生成 → `check_claims`（断言后检查）
> → 写入审计，生成最多允许三次尝试，仍不过关就失败即拒绝。把 `Steward.answer`
> （279–435 行）从头看到尾：`classify(question)`（280 行）把自由文本问题转成一对
> `(purpose, resolution)`——这是普通 Python 代码，不涉及调用模型，具体模式顺序
> 如何编码策略，`03` 章已经讲清楚。接着 `self.store.evidence_for(lat, lon)`
> （281 行）加载覆盖这个位置的、已提交且在制品清单里登记过的产物——`PolicyRequest`
> 需要的证据层级和是否在关注区域（AOI）之内，正是从这次调用里来的，这也是为什么
> 它要在策略引擎能评估任何东西之前先跑：读取一份本地的、已经哈希、已经提交的文件
> 不花任何代价，也不向任何人披露任何东西，这和下一段要讲的那个属性是两回事——真正
> 关乎一次带密钥、要计费的第三方调用的是另一件事：那次调用只发生在更后面，在
> `_lookup` 内部，且严格晚于策略引擎授权这个请求之后，所以一个未获授权的问题
> 永远不会触达第三方，也永远不会花一分钱。接下来计算可验证性（283–294 行），
> 分三支：是否需要实时数据源、以及若需要，是否配置了数据源——任何从不接触实时
> 数据源的目的都取 `RETAINED`（留存）；`facility_context`（设施背景）在配置了
> 数据源时，取 `RETAINED` 与所配置数据源自身声明的可验证性二者中的
> 短板原则（weakest-link）结果；而当目的需要实时数据源、却没有配置任何数据源时，取
> `LIVE_PURPOSES` 为该目的声明的固定值（`facility_context` 对应
> `RE_DERIVABLE`）——这是一个有意为之的占位值，让策略还能分清"在关注区域内、
> 只是能力未配置"和"根本不在关注区域内"这两种情况，而不是把二者都归并进同一个
> `default-deny`。`PolicyRequest` 由 `role`（角色）、
> `purpose`（目的）、`resolution`（分辨率）、证据的层级与是否在 AOI 内、以及这个
> 可验证性值构造出来（296–303 行），整个请求被写入审计日志、记为一条
> `gateway_request`——角色、精确的 `lat`、`lon`、问题原文，都未经任何脱敏；这个事实
> 会在下文"尚不能安全对外托管"一节里带来后果——只有到这一步之后，
> `self.policy.evaluate(request)`（312 行）才会运行。
>
> 请求本身的形状就是"二选一"，而且这项检查对同一个请求跑了两遍，而不是一遍。
> `AskRequest.exactly_one_location`（`gateway/main.py`）在请求还没到达
> `Steward.answer` 之前，就会拒绝一个同时带着 `lat`/`lon` 和 `area`、或者二者都
> 没带的请求；`answer()` 内部又对自己收到的关键字参数重复了一遍完全相同的
> `has_area` / `has_point` / `has_any_coord` 判断逻辑，所以哪怕调用方绕开
> HTTP 这一层直接调用，也躲不开这道检查。区域分支所处的位置，正是原来只有点查询时
> 那一步所在的位置，落在这六个阶段里同样的次序上：`self.store.
> evidence_for_area(area) if area is not None else self.store.evidence_for(lat,
> lon)` 在 `classify(question)` 分类出的目的送进策略引擎之前就已经跑完，所以一个
> 区域形状的请求，走的是和一个点形状的请求完全相同的预检查顺序——一个完全没有
> 触及三个深度案例关注区域中任何一个的矩形，得到的 `in_aoi: false` 和一个界外的点
> 得到的结果一模一样，`deny-outside-aoi` 拒绝它们的方式也一样。只有区域请求才会
> 填充的一个字段是 `EventEvidence.cells`——`evidence_for_area` 实际匹配到的
> H3 r9 瓦片 ID，会原样一路带进最终返回的 `answer` 响应自己的 `cells` 字段里——
> `08` 章讲了应用如何把这些格子渲染成一个高亮图层。一个点形状请求的 `cells`
> 则始终是空列表，因为 `evidence_for` 从不给它赋值——一个点查询本来就只有一格可
> 谈论，而且已经在回答正文里点名了它。
>
> 如果在这里被拒绝（313–322 行）会立即返回：没有发起过任何实时查询、没有把任何
> 证据组装进提示词、模型压根没被调用过。一个已授权、但定位到的瓦片没有任何已提交
> 事实的请求，同样会很快返回一个声明式的"无证据"响应（324–332 行）——同样在任何
> 模型调用之前。只有越过这两道关卡之后，才会发生任何形似"获取"实时答案的事：当被
> 分类出的目的需要一个实时数据源时，`self._lookup`（238–277 行）从原始经纬度计算出
> 一个 H3 r9（分辨率 9 级网格）单元格，发出请求，并在把结果用于任何用途*之前*先
> 调用 `LiveEvidenceRecorder.record`（这条记录具体装了什么、为什么这样设计，
> `05` 章讲过）——`_lookup` 内部这个顺序是故意的，理由和 `answer` 内部那个顺序
> 一样：一次查询不应该在被引用之前还没被记录下来。真正交给模型的是一行按类别计数
> 的摘要，从不是数据源提供方的原始内容（还是 `05` 章）。留存事实和任何实时行会被
> 合并成一个证据块（356–369 行），只有到这时 `self.llm(messages)`（374 行）才会
> 运行，且运行在一个由 `self.max_attempts`（默认 3，217 行）限定次数的循环内。
> 每一次尝试都会被 `check_claims`（383 行）检查，并作为一条 `gateway_post_check`
> 审计记录写下来（384–387 行），然后要么返回一个回答（397–415 行），要么把一轮
> 纠正对话追加进对话历史、循环重试（416–425 行）。第三次尝试仍然失败时不会放宽
> 要求：而是在 427–435 行产生失败即拒绝的拒绝响应，`rule_id` 为
> `"claim-post-check"`，点名最后一份草稿仍然携带的每一项违规。

## The model never decides its own authorization

Two deterministic gates bracket the one call to the model this file ever
makes, and neither is optional. Before generation: `classify` and
`PolicyEngine.evaluate` — both ordinary code, both run to completion before
`self.llm(messages)` is ever reached, and `03` covers what the classifier's
pattern order encodes and how the eight ordered rules resolve a request. A
request the policy denies never reaches the model at all — `test_damage_
outside_aoi_refused_without_llm_call` and `test_resident_damage_assessment_
refused` in `tests/test_gateway_steward.py` assert `llm.calls == 0` directly,
not just the returned `rule_id`, so the property checked is that the model
was never invoked, not merely that its output was discarded. After
generation: `check_claims(text, allowed_ids, allowed_live_ids)` inspects the
model's own draft against the evidence it was actually given, matching two
citation forms — `[artifact:HASH12]` against `_CITATION` and `[live:HASH12]`
against `_LIVE_CITATION` — and enforcing, among the six violation classes `03`
covers rule by rule, the one this chapter's brief calls out by name: a
`[live:ID]` citation with no `[artifact:ID]` citation anywhere beside it is a
violation on its own (lines 162–166), because a non-retainable source is
never allowed to be the only thing holding an answer up. "Cited-only cannot
stand alone" is not a sentence in a prompt the model is asked to honor; it is
a regex-checked condition on the returned text that a draft either satisfies
or gets sent back for.

Sending a draft back is the visible half of what a failing check does; the
audited half matters just as much. Every attempt's violations are recorded as
a `gateway_post_check` row whether or not that attempt ultimately succeeds
(lines 384–387), so a reader of the audit log — `02` covers what this log is
for in general — can see every draft the model produced for a request, not
only the one that shipped. A third consecutive failure does not lower the
bar: `check_claims` runs identically on attempt three, and a still-failing
draft produces the same fail-closed refusal every other denial in this
harness produces, `rule_id: "claim-post-check"`, with the specific violations
named in the reason string — `test_fabricated_citation_refused_after_
retries` in `tests/test_gateway_steward.py` drives exactly this path and
asserts `llm.calls == 3`: the model was given three tries, not three
successes to choose the better of.

> **中文。** 这个文件唯一会调用模型的那一次调用，两侧各有一道确定性关卡，二者
> 都不是可选的。生成之前：`classify` 和 `PolicyEngine.evaluate`——都是普通代码，
> 都会在 `self.llm(messages)` 被真正触及之前跑完，分类器的模式顺序编码了什么、
> 八条有序规则如何裁决一个请求，`03` 章已经讲过。一个被策略拒绝的请求根本不会
> 到达模型——`tests/test_gateway_steward.py` 里的
> `test_damage_outside_aoi_refused_without_llm_call` 和
> `test_resident_damage_assessment_refused` 直接断言 `llm.calls == 0`，而不只是
> 断言返回的 `rule_id`，所以这里检查的性质是"模型从未被调用过"，而不仅仅是
> "模型的输出被丢弃了"。生成之后：`check_claims(text, allowed_ids,
> allowed_live_ids)` 把模型自己写出的草稿，拿去对照真正交给它的证据做检查，
> 匹配两种引证形式——`[artifact:HASH12]` 对应 `_CITATION`，`[live:HASH12]`
> 对应 `_LIVE_CITATION`——并在 `03` 章逐条讲过的六类违规里，强制执行本章任务
> 交代里点了名的这一条：一个 `[live:ID]` 引证如果旁边没有任何 `[artifact:ID]`
> 引证，本身就是一项独立的违规（162–166 行），因为一个不可留存的来源永远不能
> 单独撑起一条回答。"cited-only（仅可引证）不能单独立住"不是提示词里一句要求模型
> 自觉遵守的话，而是对返回文本做正则检查的一个条件——一份草稿要么满足它，要么被
> 打回去重写。
>
> 打回草稿只是检查失败时可见的那一半，被记入审计的另一半同样重要。无论一次尝试
> 最终是否通过，它的违规列表都会被记为一条 `gateway_post_check` 记录（384–387
> 行）——审计日志本身是干什么用的，`02` 章已经讲过——所以读审计日志的人能看到模型
> 为这次请求写过的每一份草稿，而不只是最终发出去的那一份。第三次连续失败并不会
> 放低标准：`check_claims` 在第三次尝试上和前两次跑的是同一套检查，仍然失败的
> 草稿会产生和这套 harness 里其他任何一次拒绝一样的失败即拒绝响应，`rule_id`
> 为 `"claim-post-check"`，理由字符串里点名具体是哪些违规。
> `tests/test_gateway_steward.py` 里的
> `test_fabricated_citation_refused_after_retries` 正是驱动了这条路径，并断言
> `llm.calls == 3`：模型得到的是三次尝试的机会，而不是从三次成功里挑一份更好的。

## The four response types

`Steward.answer` returns exactly one of four shapes on every path, and each
is a distinct dict `"type"` value produced at a distinct point in the file:

1. **A cited answer** — `{"type": "answer", ...}`, returned at lines 397–415
   once an attempt's draft passes `check_claims` with zero violations. Carries
   `citations`, `live_citations`, the answer's own `verifiability`, and an
   `attribution` field only when a live citation is present (lines 410–414).
2. **A rule-ID refusal** — `{"type": "refusal", "rule_id": ..., "reason":
   ...}`, produced two ways: a denied `PolicyDecision` (lines 313–322), naming
   whichever of the eight rules `03` covers actually fired, or `default-deny`
   when none did; and exhausting all three generation attempts (lines
   427–435), naming the fixed `rule_id: "claim-post-check"` instead of a
   policy rule.
3. **A declared no-evidence response** — `{"type": "no_evidence", "rule_id":
   ..., "reason": ...}`, at lines 324–332: the request is authorized —
   `rule_id` still names the allow rule that authorized it — but the located
   tile carries zero committed facts, most often a watch-only area outside
   any of the three deep cases.
4. **A declared outage**, in two code-level forms sharing one category: the
   model endpoint itself failing raises `LLMUnavailable`, caught at lines
   374–382 and reported as `{"type": "agent_unavailable", "reason": ...}`; a
   facility-context request needing a live source that either is not
   configured at all, or is configured without a `live_recorder` (lines
   338–343 — a source without a recorder is refused just as completely as no
   source at all, because a lookup nothing attests is the exact failure this
   design exists to prevent), or raises `LiveUnavailable` when the configured
   source is actually unreachable (lines 344–351), all return `{"type":
   "live_source_unavailable", "reason": ...}` via the shared `_live_
   unavailable` helper (lines 232–236).

`app/src/components/ChatPanel.jsx` is the app's own code and `08` covers how
it renders each of these four shapes as itself — the file's own comment
states the same commitment this chapter's sequence enforces: "Every response
type the gateway can emit ... renders as itself; nothing is papered over."

> **中文。** `Steward.answer` 在每一条路径上都恰好返回四种形状之一，每一种都是
> 在文件里某个确定位置产生的一个不同的 dict `"type"` 值：**带引用的回答**——
> `{"type": "answer", ...}`，在 397–415 行返回，前提是某次尝试的草稿以零违规
> 通过了 `check_claims`；携带 `citations`（引证）、`live_citations`（实时引证）、
> 这条回答自身的 `verifiability`（可验证性），以及仅在存在实时引证时才有的
> `attribution`（署名）字段（410–414 行）。**带规则编号的拒绝**——
> `{"type": "refusal", "rule_id": ..., "reason": ...}`，有两种产生方式：一次
> 被拒绝的 `PolicyDecision`（313–322 行），点名 `03` 章讲过的八条规则里究竟是
> 哪一条生效了，若都没命中则是 `default-deny`；以及耗尽全部三次生成尝试
> （427–435 行），这次点名的不是一条策略规则，而是固定的 `rule_id`
> `"claim-post-check"`。**声明式的"无证据"响应**——`{"type": "no_evidence",
> "rule_id": ..., "reason": ...}`，在 324–332 行：请求已被授权——`rule_id`
> 仍然点名授权它的那条允许规则——但定位到的瓦片没有任何已提交事实，最常见于
> 三个深度案例之外的、只有监测覆盖的区域。**声明式的系统不可用**，在代码层面有
> 两种形式，共享同一个类别：模型端点本身失败会抛出 `LLMUnavailable`，在
> 374–382 行被捕获，报告为 `{"type": "agent_unavailable", "reason": ...}`；
> 一个需要实时数据源的设施背景请求，若该数据源根本没有配置、或者配置了却没有
> `live_recorder`（338–343 行——一个没有记录器的数据源，和压根没有数据源一样，
> 会被彻底拒绝，因为一次没有任何东西为它作证的查询，正是这套设计存在的目的所要
> 防止的失败），或者所配置的数据源真正不可达时抛出 `LiveUnavailable`
> （344–351 行），三种情况都通过共享的 `_live_unavailable` 辅助函数（232–236 行）
> 返回 `{"type": "live_source_unavailable", "reason": ...}`。
> `app/src/components/ChatPanel.jsx` 是应用自己的代码，`08` 章讲它如何把这四种形状原样
> 渲染出来——这个文件自己的注释写的正是本章这套顺序所强制执行的同一种承诺：
> "网关能发出的每一种响应类型……都会原样渲染；没有任何一种被掩盖过去。"

## Provider-agnostic by construction

`src/geosteward/gateway/llm.py` is the only place `Steward` ever calls out to
a model, and the whole module is `json`, `os`, `urllib.error`, and `urllib.
request` — no SDK, no vendor client library. `chat_completion` posts an
OpenAI-compatible `/chat/completions` request and reads three environment
variables to build it: `STEWARD_LLM_BASE_URL` (default `http://localhost:
11434/v1`, a local Ollama instance), `STEWARD_LLM_MODEL` (default
`gpt-oss:20b`), and `STEWARD_LLM_API_KEY` (optional — attached as a bearer
token only when set). Any endpoint speaking the same shape, hosted or local,
is a change to those three variables and nothing else; no code path in this
module distinguishes one provider from another. `LLMUnavailable` is raised
uniformly across `URLError`, `KeyError`, `IndexError`, `JSONDecodeError`, and
`TimeoutError` (lines 42–43) — a malformed response and an unreachable host
report the same way, which is why `Steward.answer` has exactly one branch
for "the model is unavailable" rather than one per failure mode. The default
configuration has been verified on the owner's RTX 3090 at roughly 154
tokens/second — a fact about that one machine's throughput, not a claim about
what any given deployment will see.

This is a separate code path from the live-lookup regime `05` covers:
`GroundedMapsSource` in `src/geosteward/live/grounded.py` wraps a call to
Gemini's `generateContent`, a different provider entirely, for the
`cited-only` facility-answer regime that `03` and `05` both note has no
default source configured and has never run against a live API. Neither this
chapter's adversarial suite nor `05`'s live-record tests need a Gemini key or
a Google Maps Platform key to run: `tests/test_gateway_steward.py` replaces
`self.llm` with `MockLLM`, a plain Python callable, and never instantiates
`chat_completion` at all; the live-lookup tests in
`tests/test_gateway_live.py` do the same for the live source with
`FakeLiveSource`. No hosted
credential of any kind is required for development or for the adversarial
evaluation the next section counts.

> **中文。** `src/geosteward/gateway/llm.py` 是 `Steward` 唯一会对外调用模型的
> 地方，整个模块只用到 `json`、`os`、`urllib.error`、`urllib.request`——没有任何
> SDK，没有任何厂商客户端库。`chat_completion` 发出一个兼容 OpenAI 接口的
> `/chat/completions` 请求，用三个环境变量来构造它：`STEWARD_LLM_BASE_URL`
> （默认 `http://localhost:11434/v1`，本地 Ollama 实例）、`STEWARD_LLM_MODEL`
> （默认 `gpt-oss:20b`）、`STEWARD_LLM_API_KEY`（可选——只有设置了才会作为
> bearer token 附上）。任何说着同一套接口形状的端点，无论托管在哪里，都只是
> 改这三个变量，别无其他——这个模块里没有任何一条代码路径会区分不同的模型提供方。
> `LLMUnavailable` 在 `URLError`、`KeyError`、`IndexError`、`JSONDecodeError`、
> `TimeoutError`（42–43 行）上被统一抛出——一个格式错误的响应和一个无法连接的
> 主机，报告方式完全一样，这也是为什么 `Steward.answer` 只有一个"模型不可用"的
> 分支，而不是每种失败模式各设一个分支。默认配置已经在负责人的 RTX 3090
> 显卡上验证过，速度约为每秒 154 个 token——这是这一台机器吞吐量的事实，不是对
> 任何具体部署环境会看到什么速度的断言。
>
> 这和 `05` 章讲的实时查询机制是完全独立的两条代码路径：
> `src/geosteward/live/grounded.py` 里的 `GroundedMapsSource` 包了一层对 Gemini `generateContent`
> 的调用——完全是另一个提供方——服务于 `03` 和 `05` 都提到过的那种"cited-only
> （仅可引证）"设施回答机制，而这套机制在这个构建里默认没有配置数据源，也从未
> 真正对接过任何实时 API。本章的对抗性测试套件、以及 `05` 章的实时记录测试，
> 运行时都不需要 Gemini 密钥或 Google Maps Platform 密钥：
> `tests/test_gateway_steward.py` 用 `MockLLM`——一个普通的 Python 可调用对象——
> 替换掉 `self.llm`，从头到尾都没有实例化过 `chat_completion`；
> `tests/test_gateway_live.py` 里的实时查询测试也是用 `FakeLiveSource` 做同样的
> 替换。开发工作本身、以及下一节要清点的对抗性评估，都不需要任何托管服务的密钥。

## The adversarial test suite

`tests/test_gateway_steward.py`'s own docstring names what it is: "Adversarial
evaluation of the gateway: every path must end in a structured, audited
response — approval, refusal with a rule ID, declared outage, or declared
no-evidence." Running it —

```
python -m unittest tests.test_gateway_steward -v
```

— produces `Ran 28 tests in 0.047s`, `OK`: 28 tests, all passing, across five
`TestCase` classes. The seven categories this chapter's brief names are all
present, verified by reading the test bodies rather than assumed from their
names: **out-of-AOI** (`TestPolicyGate.test_damage_outside_aoi_refused_
without_llm_call`, which also asserts zero model calls); **fabricated
citations** (`TestCheckClaims.test_fabricated_citation_fails` and
`TestClaimGate.test_fabricated_citation_refused_after_retries`, the latter
driving the full three-attempt exhaustion path); **uncited numerics**
(`TestCheckClaims.test_uncited_number_fails`, plus the eight cases in
`TestUncitedAssertions` covering digitless assertions the pre-inversion rule
`03` describes would have missed entirely); **parcel elicitation**
(`TestCheckClaims.test_parcel_statement_fails` and `TestPolicyGate.test_
parcel_question_refused_any_role`, one checking the model's own output, the
other checking the request never reaches the model at all); **LLM outage**
(`TestClaimGate.test_llm_outage_is_declared_not_faked`); **retry repair**
(`TestClaimGate.test_retry_can_repair_uncited_draft`, an uncited first draft
followed by a compliant second one, asserting `llm.calls == 2`); and **audit
completeness** (`TestClaimGate.test_every_path_is_audited`, checking that
`gateway_request`, `gateway_post_check`, and `gateway_response` all appear as
actions in the audit rows for one successful request).

This count is `tests/test_gateway_steward.py` alone.
`tests/test_gateway_live.py` — `05`'s territory, the non-retainable regime — adds its own
separate suite over the live-lookup code paths (attestation ordering,
containment of poisoned test content, the weakest-link computation) and is
not folded into the 28 above.

> **中文。** `tests/test_gateway_steward.py` 自己的文档字符串点明了它是什么："对
> 网关的对抗性评估：每一条路径都必须以一个结构化的、经过审计的响应结束——批准、
> 带规则编号的拒绝、声明式系统不可用，或声明式无证据。"运行
> `python -m unittest tests.test_gateway_steward -v`，输出是
> `Ran 28 tests in 0.047s`、`OK`：28 个测试，分布在五个 `TestCase` 类里，全部
> 通过。本章任务交代里点名的七个类别都能找到，而且是通过读测试代码本身、而不是
> 单凭名字猜出来验证的：**AOI 之外**
> （`TestPolicyGate.test_damage_outside_aoi_refused_without_llm_call`，同时
> 断言模型调用次数为零）；**伪造引证**
> （`TestCheckClaims.test_fabricated_citation_fails` 与
> `TestClaimGate.test_fabricated_citation_refused_after_retries`，后者驱动了
> 完整的三次尝试耗尽路径）；**无引证的数字断言**
> （`TestCheckClaims.test_uncited_number_fails`，外加
> `TestUncitedAssertions` 里八个覆盖不含数字断言的用例——`03` 章讲过，反转前的
> 旧规则本会完全漏掉这一类）；**parcel（地块）级套话**
> （`TestCheckClaims.test_parcel_statement_fails` 与
> `TestPolicyGate.test_parcel_question_refused_any_role`，一个检查模型自身的
> 输出，另一个检查请求根本没能到达模型）；**大模型服务中断**
> （`TestClaimGate.test_llm_outage_is_declared_not_faked`）；**重试修复**
> （`TestClaimGate.test_retry_can_repair_uncited_draft`——第一份草稿无引证，
> 第二份合规，断言 `llm.calls == 2`）；以及**审计完整性**
> （`TestClaimGate.test_every_path_is_audited`，检查一次成功请求的审计记录里
> `gateway_request`、`gateway_post_check`、`gateway_response` 三个动作是否都
> 出现过）。
>
> 这个数字只统计 `tests/test_gateway_steward.py` 一个文件。
> `tests/test_gateway_live.py`——属于 `05` 章讲的不可留存机制——针对实时查询相关代码路径（记录先于
> 使用的顺序、对被污染测试内容的隔离性、短板原则的计算）另有一套独立测试，不计入
> 上面的 28 这个数字。

## Not safe to host yet

Three concrete defects, each verified directly in the code rather than
inferred, together mean this gateway is not safe to expose publicly as it
stands: **CORS defaults to allow any origin.** `gateway/main.py`'s
`CORSMiddleware` reads `allow_origins=os.environ.get("STEWARD_CORS_ORIGINS",
"*").split(",")` (line 31) — absent an operator setting that variable, every
origin is permitted, on a `/ask` endpoint that can trigger a keyed,
third-party lookup once a live source is ever configured. **The audit log
records the exact question and the exact coordinates, unredacted.** The
`gateway_request` row `Steward.answer` writes (lines 304–310) carries `lat`,
`lon`, and `question` verbatim; `AuditLog.record` in
`src/geosteward/harness/audit.py` serializes whatever payload it is given straight to JSONL
with no redaction step of any kind — this is a different mechanism from the
workstation-path redaction `01` and `04` describe for artifact manifests
(`REDACTED_PREFIX`, `redact_workstation_paths`), which scrubs local
filesystem paths, not a resident's location or the words they typed. **There
is no rate limiting anywhere in `gateway/main.py`.** No per-origin, per-IP, or
per-key throttling exists on `/ask`, so nothing bounds how many requests —
and, once a live source is configured, how many billable third-party calls —
a single caller can trigger.

Origin allowlisting, rate limiting, and log redaction all have to land before
any public deployment, and the order matters for a second reason beyond the
gateway's own safety: this same list is on the critical path for wiring up
*any* keyed third-party API, whether that is a hosted LLM behind `STEWARD_
LLM_BASE_URL` or the live facility source `03` and `05` describe as
authorized-but-unconfigured. A keyed endpoint sitting behind an open-CORS,
unthrottled, unredacted gateway is not a smaller version of the hosting
problem; it is the same three defects with a bill attached. Consistent with
this, the public site ships no chat backend at all:
`app/src/components/ChatPanel.jsx` defaults to `http://localhost:8080` (line 6) and, when that
endpoint cannot be reached, renders a declared-outage message telling the
reader to run the gateway themselves (`pip install -e .[deepcase,gateway] &&
uvicorn gateway.main:app --port 8080`) rather than silently failing or
routing to some hosted stand-in that does not exist. Everything this chapter
has described — the lifecycle, the two authorization gates, the four
response types, the 28 passing adversarial tests — describes what this code
does when run, locally, against a locally running model; none of it describes,
or should be read as describing, a service currently reachable over the
internet.

> **中文。** 三处具体的缺陷，每一处都直接在代码里核实过、而不是推测出来的，
> 合在一起意味着这个网关目前原样对外暴露是不安全的：**CORS 默认允许任意来源。**
> `gateway/main.py` 的 `CORSMiddleware` 读取
> `allow_origins=os.environ.get("STEWARD_CORS_ORIGINS", "*").split(",")`
> （31 行）——如果运维人员没有专门设置这个环境变量，任何来源都会被放行，而
> `/ask` 这个端点一旦配置了实时数据源，就能触发一次带密钥的第三方查询。
> **审计日志记录的是精确的问题原文和精确的经纬度，未经任何脱敏。** `Steward.answer`
> 写下的 `gateway_request` 记录（304–310 行）原样携带 `lat`、`lon`、
> `question`；`src/geosteward/harness/audit.py` 里的 `AuditLog.record` 把拿到的
> payload 直接序列化写进 JSONL，不做任何形式的脱敏——这和 `01`、`04` 两章讲过的、
> 针对制品清单的工作站路径脱敏（`REDACTED_PREFIX`、`redact_workstation_paths`）
> 是完全不同的机制：那套机制清洗的是本地文件系统路径，不是居民的位置或他们打出来
> 的原话。**`gateway/main.py` 里没有任何形式的限流。** `/ask` 上不存在按来源、按
> IP，或按密钥的节流机制，所以没有任何东西限制一个调用方能触发多少次请求——一旦
> 配置了实时数据源，也就没有任何东西限制它能触发多少次要计费的第三方调用。
>
> 来源白名单、限流、日志脱敏，这三样都必须在任何公开部署之前落地，而顺序之所以
> 重要，除了网关自身的安全之外还有第二个理由：接入*任何*带密钥的第三方 API——不管
> 是 `STEWARD_LLM_BASE_URL` 背后的某个托管大模型，还是 `03`、`05` 两章都提到过的
> "已授权但未配置"的实时设施数据源——都要先过这同一份清单。一个带密钥的端点，如果
> 架在一个 CORS 开放、无限流、日志不脱敏的网关背后，并不是"托管问题"的一个简化
> 版本，而是同样这三处缺陷外加一张账单。与此一致的是，公开网站目前完全没有配套的
> 对话后端：`app/src/components/ChatPanel.jsx` 默认指向
> `http://localhost:8080`（6 行），当这个端点无法访问时，会渲染一条声明式的
> 系统不可用消息，告诉读者自己在本地运行网关
> （`pip install -e .[deepcase,gateway] && uvicorn gateway.main:app --port
> 8080`），而不是悄悄失败，也不会转而连到某个并不存在的托管替身上。本章讲过的
> 一切——请求生命周期、两道授权关卡、四种响应类型、28 个通过的对抗性测试——描述的
> 都是这段代码在本地运行、对接一个本地运行的模型时会做的事；其中没有任何一处
> 描述的是、也不应该被读成是描述了一个当前可以通过公网访问的服务。
