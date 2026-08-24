# 03 · The claim plane — what the agent may assert

[Institutional validity](12-glossary.md) — the third of the three conditions
the [Steward Harness](12-glossary.md) enforces, after outcome and process in
`02` — has two halves, and this chapter is the first: the
[claim plane](12-glossary.md), governing what the agent may assert about a
place, given who is asking, why, at what resolution, and against what
evidence tier. Chapter `04` covers the second half, the
[distribution plane](12-glossary.md) — what a build may publish — and
chapter `05` covers verifiability, the axis both planes read from. The claim
plane and the distribution plane are two separate rule sets rather than one,
and the reason is a real incident rather than a taste for symmetry: on
2026-08-20 a parcel-level [CAL FIRE DINS](12-glossary.md) source reached the
public site while satisfying every rule this chapter describes, because
nothing in this chapter's rules was ever asked to approve it — the build
copied the file directly, a step no claim rule has jurisdiction over. This
chapter answers "may the agent say this"; it does not answer "may a build
ship this file," and nothing below should be read as if it did.

> **中文。** [有效性（结果 / 过程 / 制度）](12-glossary.md)——这是
> Steward Harness（问责框架）强制执行的第三项条件，紧接着 `02` 讲过的结果与
> 过程——分成两半，本章是前一半：断言平面，管的是给定提问角色、提问目的、分辨率和
> 证据层级之后，agent
> 可以对一个地方断言什么。后一半——发布平面，管的是构建可以发布什么——留给 `04`；
> 两个平面共同读取的可验证性这根轴留给 `05`。断言平面与发布平面之所以是两套独立
> 规则而不是一套，理由是一次真实事故，而不是出于对称的美学偏好：2026 年 8 月 20
> 日，一份 parcel 级的 CAL FIRE DINS（损毁勘查）数据在满足本章讲到的每一条规则的
> 情况下，仍然进了公开站点——因为本章的规则从来没有被要求去批准它：构建脚本直接
> 复制了这个文件，而这一步不在任何断言规则的管辖范围内。本章回答的是"agent 能不能
> 这么说"，不回答"构建能不能发布这个文件"，下文任何一处都不应被当作在回答后者。

## Ordered rules, first match wins, default deny

`PolicyEngine.from_yaml(path)` loads the `rules:` section of
`src/geosteward/harness/policy_v1.yaml` — the claim plane; the same file's
`distribution:` section belongs to chapter `04`. `PolicyEngine.evaluate(request:
PolicyRequest) -> PolicyDecision` walks the loaded rules in the order they
appear in the YAML and returns the first one whose `match` conditions all
hold. The request being checked is a `PolicyRequest(role, purpose, resolution,
evidence_tier, in_aoi, verifiability)`; the decision returned is a
`PolicyDecision(allowed, rule_id, reason)`, naming exactly which rule fired
and why. A request that matches none of the ordered rules — not "hits some
implicit permissive rule," but matches nothing in the list at all — falls
through to `default_deny()`, which returns `allowed=False`, `rule_id=
"default-deny"`, and the reason "No policy rule authorizes this request; the
harness fails closed." Authorization is therefore never a default computed
from what's absent; it is always one specific named rule, or the one
specific, equally named, default-deny rule.

> **中文。** `PolicyEngine.from_yaml(path)` 加载
> `src/geosteward/harness/policy_v1.yaml` 里的 `rules:` 部分——也就是断言平面；
> 同一个文件里的 `distribution:` 部分属于 `04` 章。`PolicyEngine.evaluate(request:
> PolicyRequest) -> PolicyDecision` 按 YAML 里出现的顺序遍历这些规则，返回第一条
> `match` 条件全部满足的规则。被检查的请求是一个 `PolicyRequest(role, purpose,
> resolution, evidence_tier, in_aoi, verifiability)`；返回的决策是一个
> `PolicyDecision(allowed, rule_id, reason)`，点名究竟是哪一条规则生效、理由是
> 什么。一个不命中任何一条已排序规则的请求——不是"命中了某条隐含的放行规则"，而是
> 在整份列表里什么都没命中——会落到 `default_deny()`，返回 `allowed=False`、
> `rule_id="default-deny"`，理由是"没有任何策略规则授权这个请求；harness 失败即
> 拒绝"。因此授权从来不是靠"缺席"推算出来的默认值，它永远是某一条被点名的具体规则，
> 或者同样被点名的那一条 default-deny 规则。

## Validation happens at load, not at evaluation

Two checks run inside `PolicyEngine.__init__` — at construction, which for
`from_yaml` means at load time, before any request is ever evaluated:
`validate_rules` and `_validate_verifiability_values`. `validate_rules`
raises a `ValueError` on any rule missing a string `id` or `reason`, any
`effect` other than `allow`/`deny`, and — the case worth stating plainly —
any `match` key outside the eight this plane recognizes (`role`, `purpose`,
`resolution`, `in_aoi`, `evidence_tier_at_least`, `evidence_tier_below`,
`verifiability`, `verifiability_below`). A hand-edited YAML rule is the
realistic place a typo lands, and a misspelled match key on a *deny* rule is
not a loud failure at runtime — it is a rule that quietly matches nothing,
ever, so every request that should have hit that deny rule instead falls
through to whichever rule comes after it. A silent load is therefore a
silent widening of authorization, and running this check at load rather
than at evaluation turns that widening into a load-time exception instead of
a request-time surprise.

`_validate_verifiability_values` exists one level down, for the same reason,
on the one match value this plane restricts to a closed set rather than a
free-form string: `verifiability` and `verifiability_below` must each name a
point on `VERIFIABILITY_ORDER` (`cited-only`, `re-derivable`, `retained`).
Most match values — a `role` name, a `purpose` name — are not checked against
any vocabulary by `validate_rules`, because there is no closed vocabulary to
check them against. Verifiability is different: it is exactly three named
points, and the function's own reasoning states the failure mode as
concretely as the deny-rule case above does — a rule matching `verifiability:
retianed` (a typo of `retained`) would match nothing and therefore never deny
anything, the same silent-widening failure `validate_rules` guards against
for match keys, now guarded for this one closed-set value.

> **中文。** `PolicyEngine.__init__` 内部会跑两项检查——在构造阶段，对
> `from_yaml` 而言就是加载时刻，早于任何请求被真正评估之前：`validate_rules` 和
> `_validate_verifiability_values`。`validate_rules` 会对以下情况抛出
> `ValueError`：规则缺少字符串类型的 `id` 或 `reason`；`effect` 不是
> `allow`/`deny` 之一；以及——这一点值得说得直白一些——`match` 里出现了这个平面
> 认得的八个键（`role`、`purpose`、`resolution`、`in_aoi`、
> `evidence_tier_at_least`、`evidence_tier_below`、`verifiability`、
> `verifiability_below`）之外的键。手写 YAML 规则最容易出现打字错误，而一条
> **deny（拒绝）**规则里键名拼错，在运行期并不会大声报错——它只会悄悄地永远匹配不到
> 任何请求，于是本该命中这条拒绝规则的每一个请求，都会落到它后面的下一条规则上去。
> 所以一次悄无声息的加载，就是一次悄无声息的授权范围扩大；把这项检查放在加载而不是
> 评估阶段执行，就是要把这种扩大变成一次加载期就抛出的异常，而不是留到请求期才让人
> 意外发现。
>
> `_validate_verifiability_values` 出于同样的理由，多管了一层：这个平面里唯一被
> 限定为封闭取值集合、而非自由字符串的匹配值——`verifiability` 与
> `verifiability_below` 必须是 `VERIFIABILITY_ORDER`（`cited-only`、
> `re-derivable`、`retained`）上的某一个点。大多数匹配值——比如某个 `role` 名字、
> 某个 `purpose` 名字——`validate_rules` 并不会拿它们去对照任何词表，因为根本没有
> 封闭词表可对照。可验证性不一样：它恰好只有三个命名的点，这个函数自己的注释把失败
> 模式说得和上面拒绝规则的例子一样具体——一条写成 `verifiability: retianed`
> （`retained` 的笔误）的规则会匹配不到任何请求、因而永远拒绝不了任何东西，这正是
> `validate_rules` 针对匹配键防范的同一种"悄悄扩大授权"的失败，只是这次防范的对象
> 换成了这一个封闭取值的匹配值。

## Classification is deterministic; the model does not choose its own authorization

Before a request ever reaches the policy engine, `classify(question) ->
tuple[str, str]` in `src/geosteward/gateway/steward.py` turns the free-text
question into the `(purpose, resolution)` pair a `PolicyRequest` is built
from — and `classify` is ordinary Python: a fixed sequence of compiled
regular expressions checked in order, not a call to the language model. The
module's own docstring states the point this section exists to make:
"Deterministic code classifies the request and verifies the output; the LLM
never decides its own authorization and never gets the last word." The order
the patterns are checked in is itself a policy choice, not an accident:
`damage_assessment` is checked first because it is the heaviest claim and the
most constrained; `exposure` is checked before `facility_context` so that a
question mentioning both vulnerability and hospitals resolves toward the
stronger evidence rather than the weaker one; `watch` is the fallback when
none of the keyword patterns match anything at all. `resolution` is set to
`parcel` the moment a street-address-shaped or "my house"-shaped pattern
matches the question text, and stays `tile` otherwise. Because classification
happens before the model is ever invoked, an LLM cannot argue its way into a
broader authorization than the question's own text supports — it receives
the classification as a fact already decided, not a request it gets to
negotiate.

> **中文。** 请求到达策略引擎之前，`src/geosteward/gateway/steward.py` 里的
> `classify(question) -> tuple[str, str]` 先把自由文本问题转换成
> `PolicyRequest` 据以构造自身的 `(purpose, resolution)` 这对值——而
> `classify` 就是普通的 Python 代码：按固定顺序检查一串预编译的正则表达式，
> 不涉及对语言模型的任何调用。这个模块自己的文档字符串把本节要说明的道理讲得很
> 直接："由确定性代码对请求分类、对输出做校验；大模型永远不能决定自己的授权范围，
> 也永远没有最终决定权。"这些模式的检查顺序本身就是一项策略选择，不是随意安排：
> `damage_assessment`（损毁评估）排第一个检查，因为它是最重的断言、约束也最严；
> `exposure`（暴露度）排在 `facility_context`（设施背景）之前检查，这样一个同时
> 提到脆弱性和医院的问题会被归到证据更强的那一类，而不是更弱的那一类；当所有关键词
> 模式都不命中时，兜底归为 `watch`（监测）。一旦问题文本命中形似门牌地址或"我家
> 房子"这类模式，`resolution` 就被设为 `parcel`，否则保持 `tile`。因为分类发生在
> 模型被调用之前，大模型没有办法靠论证把自己说进一个比问题文本本身所支持的更宽的
> 授权范围里——它拿到的分类结果是一个已经决定好的既成事实，而不是一个它可以去
> 商榷的请求。

## The rules, one at a time

`policy_v1.yaml`'s `rules:` section holds eight rules, evaluated in this
order, each one an answer to a specific question a request can ask:

1. **`deny-outside-aoi`** (`match: {purpose: damage_assessment, in_aoi:
   false}`) — Is a damage-assessment request outside the event's
   [AOI](12-glossary.md) authorized? No, unconditionally: damage assessment
   is scoped to inside the boundary regardless of any other field on the
   request.
2. **`deny-parcel-any-role`** (`match: {resolution: parcel}`) — Is a
   parcel-resolution claim authorized, for any role, any purpose? No: v1's
   evidence supports a statement no finer than tile resolution, and this
   rule matches on resolution alone, before role or purpose are even
   considered.
3. **`deny-resident-damage-assessment`** (`match: {role: resident, purpose:
   damage_assessment}`) — May a resident receive a damage assessment? No:
   residents get exposure context and guidance instead; a damage conclusion,
   when one is authorized at all, goes to a planner (rule 7).
4. **`deny-damage-assessment-without-retained-evidence`** (`match: {purpose:
   damage_assessment, verifiability_below: retained}`) — May a damage
   assessment rest on anything weaker than [retained](12-glossary.md),
   hashed evidence committed to this repository? No: a live third-party
   lookup, however current, cannot support the project's heaviest claim.
5. **`allow-watch-anywhere`** (`match: {purpose: watch}`) — Where, and for
   whom, is monitoring information authorized? Anywhere, any role, any
   evidence tier, inside or outside every AOI — the broadest rule in the
   plane, matching on purpose alone.
6. **`allow-exposure-in-aoi`** (`match: {purpose: exposure, resolution:
   tile, in_aoi: true, evidence_tier_at_least: 2}`) — Is tile-level exposure
   analysis authorized inside a deep-case AOI? Yes, once evidence has
   reached [Tier 2](12-glossary.md) (Analysis) or better.
7. **`allow-planner-damage-tier3`** (`match: {role: planner, purpose:
   damage_assessment, resolution: tile, in_aoi: true, evidence_tier_at_least:
   3}`) — May a planner receive a tile-level damage assessment? Yes, where
   [Tier 3](12-glossary.md) (Evidence) cross-view evidence exists for that
   place — every other field on this rule (role, resolution, AOI
   membership) has to hold too.
8. **`allow-facility-context-re-derivable`** (`match: {purpose:
   facility_context, resolution: tile, in_aoi: true, verifiability:
   re-derivable}`) — May tile-level facility context (nearby hospitals,
   shelters, fire stations) rest on a [re-derivable](12-glossary.md) live
   source paired with retained exposure evidence? Yes, as a rule — that is
   what this rule authorizes, not a claim about what currently runs: the
   live lookup this rule exists for has no configured source in this build
   (`Steward.live_source` defaults to `None`) and has never executed
   against a live API, so the authorization is real and enforced while the
   capability it authorizes sits unexercised. Chapter `05` covers what a
   live source and its record are.

What the four allow rules above deliberately leave uncovered matters as much
as what they cover: a request whose verifiability is `cited-only` — prose
the model could produce but that is neither retained nor re-derivable by
anyone — matches none of them, and falls through to `default-deny`. No rule
in this plane was ever written to authorize a `cited-only` claim; the
fail-closed default carries that entire regime without a line of policy
dedicated to it.

`tests/test_policy_v1_matrix.py` is the committed check on this ordering:
its own docstring calls it "verified cell by cell (role x purpose x tier x
resolution)," and its `MATRIX` table drives eleven `(role, purpose,
resolution, tier, in_aoi)` combinations through `PolicyEngine.evaluate`,
asserting both the allow/deny outcome and the exact `rule_id` that produced
it. It exercises six of the eight rules above by name —
`allow-watch-anywhere`, `allow-exposure-in-aoi`, `allow-planner-damage-tier3`,
`deny-outside-aoi`, `deny-resident-damage-assessment`, `deny-parcel-any-role`
— plus `default-deny` itself, twice, for combinations none of those six
cover. `deny-damage-assessment-without-retained-evidence` and
`allow-facility-context-re-derivable` sit outside this matrix: both turn on
`verifiability`, a field none of `MATRIX`'s entries ever set to anything but
the `PolicyRequest` default of `retained`, so the matrix as committed today
says nothing about either.

> **中文。** `policy_v1.yaml` 的 `rules:` 部分共有八条规则，按以下顺序依次评估，
> 每一条都在回答一个具体问题：`deny-outside-aoi` 问的是"AOI 之外的损毁评估请求
> 授权吗"，答案是不授权，且不看请求的任何其他字段；`deny-parcel-any-role` 问的是
> "parcel 分辨率的断言，不论角色、不论目的，授权吗"，答案是不授权——这条规则只看
> 分辨率，甚至不看角色或目的；`deny-resident-damage-assessment` 问的是"居民能
> 拿到损毁评估吗"，答案是不能——居民得到的是暴露度背景与行动建议，损毁结论（如果
> 真的授权）给的是规划者（见第 7 条）；`deny-damage-assessment-without-retained-evidence`
> 问的是"损毁评估能不能建立在比 retained（留存）更弱的证据之上"，答案是不能——
> 一次实时的第三方查询无论多新，都撑不起这个项目最重的断言；`allow-watch-anywhere`
> 问的是"监测信息在哪里、对谁授权"，答案是任何地点、任何角色、任何证据层级、
> 无论在不在任何 AOI 之内都授权——是本平面里覆盖面最广的一条规则，只看请求目的；
> `allow-exposure-in-aoi` 问的是"深度案例 AOI 内的 tile 级暴露度分析授权吗"，
> 答案是授权，前提是证据已达到 2 级（Analysis）及以上；`allow-planner-damage-tier3`
> 问的是"规划者能拿到 tile 级损毁评估吗"，答案是能，前提是该地存在 3 级
> （Evidence）交叉视角证据——规则里其余每个字段（角色、分辨率、是否在 AOI 内）
> 也都必须同时成立；`allow-facility-context-re-derivable` 问的是"tile 级设施
> 背景（附近的医院、避难所、消防站）能不能建立在一个可复现的实时数据源、并搭配
> retained 暴露度证据之上"，答案是——作为一条规则——能：这只是说这条规则授权
> 了什么，不代表现在真的在这么跑：这条规则对应的实时查询在这个构建里没有配置数据
> 源（`Steward.live_source` 默认是 `None`），也从未真正对接过任何实时 API，
> 所以授权本身是真实且被强制执行的，只是它所授权的能力目前还没有被实际用上——
> 实时数据源本身及其记录留给 `05` 章。这四条允许规则没有覆盖到的部分，和它们
> 覆盖到的部分同样重要：一个可验证性为 `cited-only`（仅可引证）的请求——模型能
> 写出这样的文字，但既不能留存也没有任何人能复现它——不会命中上面任何一条允许
> 规则，只会落到 `default-deny`。本平面里从来没有一条规则是为了授权 `cited-only`
> 断言而写的；失败即拒绝的默认规则，不靠专门为它写的一行策略，就扛住了整个这一类
> 请求。
>
> `tests/test_policy_v1_matrix.py` 正是给这套排序做的已提交检查：它自己的文档
> 字符串说这是"逐格验证（角色 × 目的 × 层级 × 分辨率）"，它的 `MATRIX` 表驱动
> 十一组 `(role, purpose, resolution, tier, in_aoi)` 组合走一遍
> `PolicyEngine.evaluate`，同时断言放行/拒绝的结果和产生这个结果的确切
> `rule_id`。它按名字覆盖了上面八条规则里的六条——`allow-watch-anywhere`、
> `allow-exposure-in-aoi`、`allow-planner-damage-tier3`、`deny-outside-aoi`、
> `deny-resident-damage-assessment`、`deny-parcel-any-role`——外加
> `default-deny` 本身（两次，对应那六条都覆盖不到的组合）。
> `deny-damage-assessment-without-retained-evidence` 和
> `allow-facility-context-re-derivable` 不在这份矩阵里：这两条都要看
> `verifiability` 这个字段，而 `MATRIX` 里没有一项把它设成过 `PolicyRequest`
> 默认值 `retained` 以外的任何值，所以就已提交的这份矩阵而言，它对这两条规则
> 什么都没说。

## The claim post-check

Even a request the policy authorizes still produces a draft the model
wrote, and `check_claims(text: str, allowed_ids: set[str], allowed_live_ids:
set[str] | None = None) -> list[str]` in `src/geosteward/gateway/steward.py`
is what checks that draft before it is ever returned — an empty list means
the draft passed; anything else names what failed. Reading the function top
to bottom, it finds six distinct kinds of violation: no citation anywhere in
the text at all; a cited `[artifact:ID]` naming an id absent from the
evidence actually given to the model (a fabricated citation); a cited
`[live:ID]` naming an id this request's live lookup never produced (a
fabricated live citation); a `[live:ID]` citation with no `[artifact:ID]`
citation anywhere alongside it, because a non-retainable source is never
allowed to be the only thing holding an answer up; a sentence that asserts
something and carries no citation at all; and a sentence, anywhere in the
answer, matching the same parcel-shaped patterns `classify` uses to detect a
parcel-level question, this time as a parcel-level statement the model was
never authorized to make.

The uncited-sentence check turns on `is_non_assertive(sentence)`, and that
function implements a *closed* exemption list of exactly three sentence
shapes that need no citation: a question (ending in `?`), imperative advice
addressed to the reader (matched at the sentence's head — verbs like
"contact," "check," and "avoid," optionally behind a leading conditional or
"please"), and a declared limit — the system stating what it cannot or will
not say. Every other sentence shape is required to carry a citation. That
direction is not the one this check started in: it previously required a
citation only on a sentence containing a digit — a blocklist naming the one
shape considered dangerous and letting every other shape through — and under
that rule a sentence like *"Your neighborhood was not significantly
affected."* carried no digit, so it passed with nothing behind it. Inverting
the rule to citation-by-default with a closed exemption list means a
sentence shape nobody anticipated is now refused rather than published: the
failure mode of getting the exemption list wrong became an over-strict
refusal instead of an uncited claim — the direction this harness fails in
everywhere else. Measured over thirteen representative drafts, the
inversion moved acceptance from 9 of 13 to 7 of 13 — closing three drafts
that had carried an uncited assertion, and fixing one draft the old rule had
wrongly rejected. The lower number is the improvement: a citation checker
that accepts more drafts than it used to has gotten looser, not better.

> **中文。** 即便策略已经授权了一个请求，模型写出来的仍然只是一份草稿，
> `src/geosteward/gateway/steward.py` 里的 `check_claims(text: str,
> allowed_ids: set[str], allowed_live_ids: set[str] | None = None) ->
> list[str]` 就是在这份草稿被返回之前对它做检查的地方——返回空列表说明通过，
> 否则列表里点名的是具体哪里出了问题。把这个函数从头看到尾，能数出六类不同的违规：
> 全文没有任何引证；引用了一个 `[artifact:ID]`，但这个 id 根本不在真正交给模型的
> 证据里（伪造引证）；引用了一个 `[live:ID]`，但这个 id 不是这次请求的实时查询
> 真正产生的（伪造实时引证）；出现了 `[live:ID]` 引证却没有任何 `[artifact:ID]`
> 引证与之并存——因为一个不可留存的数据源永远不能单独撑起一个回答；某个断言性的
> 句子完全没有引证；以及回答里任何位置出现的、与 `classify` 用来识别 parcel 级
> 问题的同一批模式相匹配的句子——这次是模型本不被授权做出的 parcel 级陈述。
>
> "无引证句子"这一类检查依赖 `is_non_assertive(sentence)`，这个函数实现的是一份
> **封闭**的豁免清单，恰好三种句型不需要引证：疑问句（以 `?` 结尾）、面向读者的
> 祈使式建议（在句首匹配——"contact"（联系）、"check"（核实）、"avoid"（避免）
> 一类动词，前面可以跟一个条件从句或"please"）、以及声明自身局限的句子——系统说明
> 自己不能说或不会说什么。除此之外的任何句型都必须携带引证。这个方向和这项检查
> 最初的方向正好相反：它以前只要求含有数字的句子携带引证——这是一份"黑名单"，
> 点名了被认为危险的那一种句型、放行了其余所有句型——在那条旧规则下，像"你所在的
> 社区并未受到显著影响"这样一句话不含数字，于是不带任何依据就通过了。把规则反转成
> "默认要求引证、再列一份封闭的豁免清单"之后，任何没人预料到的句型现在会被拒绝而
> 不是被放行发布：把豁免清单列错的后果，从"一条无据断言"变成了"一次过于严格的拒绝"
> ——这正是本 harness 在别处一直坚持的失败方向。在十三份有代表性的草稿上测量，
> 这次反转让通过率从 13 份里的 9 份变成了 13 份里的 7 份——堵住了三份带有无引证
> 断言的草稿，同时纠正了一份被旧规则错误拒绝的草稿。数字变小才是改进：一个比以前
> 通过更多草稿的引证检查器，只是变松了，不是变好了。
