# 10 · Getting started

This chapter is a procedure, not an explanation: commands to run, in the
order a fresh clone actually needs them, with what each one produced when
run against the exact state this manual describes. Every command below was
executed before it was written down — none is copied from `README.md` or
`docs/STATUS.md` without being re-run — so a number that looks wrong is more
likely this chapter going stale than a typo. Mechanism lives in `02`–`09`;
this chapter only tells a reader what to type.

> **中文。** 本章是操作步骤，不是原理讲解：按一次全新 clone 真正需要的顺序列出
> 命令，并写明每条命令在本说明书所描述的这个状态下实际跑出的结果。下面每一条命令
> 都是先执行、再记录下来的——没有一条是不经重新运行就照抄 `README.md` 或
> `docs/STATUS.md` 的——所以如果某个数字看起来不对，更可能是本章已经过时，而不是
> 写错了。机制留给 `02`–`09` 讲；本章只负责告诉读者该敲什么。

## Install

```bash
git clone https://github.com/rayford295/ray-resilience && cd ray-resilience
python -m pip install -e ".[deepcase]"
```

`pyproject.toml` declares `requires-python = ">=3.10"`; CI
(`.github/workflows/test.yml`) pins `3.11`. This chapter's commands were run on both a `3.13`
interpreter and re-checked against what CI pins — the `deepcase` extra
(`h3>=4.0`) is the only one needed for the steps below through "Rebuild a
deep case"; `gateway` (`fastapi`, `uvicorn`) is added later, only for the
agent gateway section, and `geo` (`numpy`, `pandas`, `shapely`, `matplotlib`)
is not needed for anything in this chapter at all.

> **中文。** `pyproject.toml` 声明的是 `requires-python = ">=3.10"`；CI
> （`.github/workflows/test.yml`）钉住的是 `3.11`。本章的命令在 `3.13` 解释器上
> 跑过一遍，也对照 CI 钉住的版本复核过——`deepcase` 这个可选依赖组（`h3>=4.0`）是
> 从这里到"重建一个深度案例"一节为止唯一需要的；`gateway`（`fastapi`、
> `uvicorn`）要到智能体网关一节才会装；`geo`（`numpy`、`pandas`、`shapely`、
> `matplotlib`）本章全程都用不到。

## Run the tests

```bash
python -m unittest discover -s tests
```

This ran **262 tests green with 1 skipped, in 5.0 seconds** against this
chapter's own state. The skip is deliberate and it is the install line above
that causes it: `AskRequestValidationTests` exercises `gateway/main.py`,
which needs the optional `gateway` extra you do not install until the agent
gateway section further down. Add it and the same command reports **266,
none skipped**. A count is only meaningful next to the extras it was run
with — that pairing is what the closing note's warning about frozen numbers
is really about, and this one is two lines from the command it describes.
Expect two extra lines mid-run that are not a failure: `N anchor(s) checked,
N failure(s)`, printed twice, once with one deliberately broken anchor and
one failure, once against the whole real `docs` tree with zero. Both come from
`tests/test_manual_anchors.py` exercising the CLI in `scripts/manual_anchors.py`
directly rather than importing its functions — a real rough edge, not a bug
in your setup; `11` names it as one.

The app has its own suite, separate from the Python one:

```bash
cd app && npm ci && npm test
```

This ran **44 tests across 6 files, all green, in under 200 ms** —
`app/src/lib/citations.test.js`, `coverage.test.js`, `watch.test.js`,
`data.test.js`, `area.test.js`, and `clickSuppression.test.js`. It has no
optional-extra caveat: `npm ci` installs everything it needs.

> **中文。** 这一次运行是 **262 个测试通过、1 个被跳过，用时 5.0 秒**，是针对本章
> 所描述的这个状态跑出来的。这个跳过是刻意的，而且正是上面那条安装命令造成的：
> `AskRequestValidationTests` 检验的是 `gateway/main.py`，它需要可选依赖组
> `gateway`，而你要到本章后面的智能体网关一节才会装它。装上之后同一条命令报的是
> **266 个、一个都不跳**。一个计数只有和它当时装了哪些可选依赖放在一起才有意义——
> 本章末尾关于"把具体数字冻在文字里"的告诫，真正说的就是这种成对关系，而这一处离
> 它所描述的那条命令只隔了两行。运行过程中会多出两行、不是失败："`N anchor(s)
> checked, N failure(s)`"会打印两次，一次针对一个故意造出来的坏锚点、一次失败，
> 一次针对真实的整棵 `docs` 树、零次失败。这两行都来自 `tests/test_manual_anchors.py`
> 直接跑 `scripts/manual_anchors.py` 的命令行入口，而不是导入它的函数——这是一个真实
> 存在的粗糙之处，不是你本地环境的问题；`11` 章把它记在名下。
>
> app 有一套独立于 Python 那套的测试：先 `cd app`，再 `npm ci && npm test`。这一次
> 运行是 **6 个文件、44 个测试全部通过，用时不到 200 毫秒**——
> `app/src/lib/citations.test.js`、`coverage.test.js`、`watch.test.js`、
> `data.test.js`、`area.test.js`、`clickSuppression.test.js`。它没有可选依赖那一层
> 附带条件：`npm ci` 会把它需要的东西全部装齐。

## Run the app

```bash
npm run dev
```

(from inside `app/`, after the `npm ci` above). This first runs `npm run
sync-artifacts`, which copies every artifact the
[distribution plane](12-glossary.md)'s allowlist currently authorizes out of
`events/` into `app/public/events/` and
redacts workstation paths in the ones flagged for it — the run behind this
chapter copied **16 authorised artifact(s)**, redacting **3**. Vite then
starts at `http://localhost:5173/` in under 100 ms. Stop it with `Ctrl-C`.

The app works from this alone: **no API key, no external service, no
gateway.** It reads the committed, hashed deep-case artifacts synced above
and nothing else — the resident dossier, the planner layers, the lineage
viewer, and the validity badges are all built from files already in the
repository. What it cannot do without the next section is answer a
free-text question through the LLM chat panel; without a reachable gateway
it renders a declared-outage message rather than failing silently or
inventing a stand-in backend.

> **中文。** 在 `app/` 目录下、`npm ci` 之后运行 `npm run dev`。这条命令先跑
> `npm run sync-artifacts`，把发布平面的允许清单当前授权的每一份制品从
> `events/` 复制到 `app/public/events/`，并对其中标了脱敏标记的文件做工作站路径
> 脱敏——支撑本章这次运行复制了 **16 份已授权制品**，脱敏了其中 **3 份**。随后
> Vite 在不到 100 毫秒内启动于 `http://localhost:5173/`。用 `Ctrl-C` 停止。
>
> 仅凭这一步，应用就能跑起来：**不需要 API 密钥、不需要外部服务、不需要网关。**
> 它读取的只是上一步同步进来的、已提交且已哈希的深度案例制品——居民端档案卡片、
> 规划者图层、溯源查看器、有效性徽章，全都是从仓库里已有的文件构建出来的。它在没有
> 下一节的情况下唯一做不到的，是通过大模型对话面板回答自由文本问题；联系不上网关时，
> 它会渲染一条"已声明的服务不可用"提示，而不是悄悄失败或换上一个假装存在的后端。

## Run the agent gateway

```bash
ollama pull gpt-oss:20b
python -m pip install -e ".[deepcase,gateway]"
uvicorn gateway.main:app --port 8080
```

`ollama pull` needs a running Ollama daemon first (`ollama serve`, or the
desktop app) — this chapter's run started one explicitly and the pull
finished at **13 GB**. The `gateway` extra adds `fastapi>=0.110` and
`uvicorn>=0.29` on top of `deepcase`. Once `uvicorn` is up,
`GET http://127.0.0.1:8080/health` returned:

```
{"status":"ok","events":["eaton-2025","ian-2022","milton-2024"]}
```

The gateway is still local-only at this point — no key, no hosted
endpoint — but it is now a second thing that has to be running (Ollama)
alongside the app; that is a different claim from "no services" above, and
this chapter states both rather than picking the more flattering one. A
question through the full chain, run directly against the code rather than
over HTTP (`python scripts/ask_steward.py --role planner --lat 34.19 --lon
-118.10 --question "How severe is the damage in this area?"`), came back
authorized under `allow-planner-damage-tier3` with a cited, four-sentence
answer and `"verifiability": "retained"` — end to end, through the real
`gpt-oss:20b` model, not a stub. Provider is swappable without touching code:
`STEWARD_LLM_BASE_URL`, `STEWARD_LLM_MODEL`, and `STEWARD_LLM_API_KEY` default
to `http://localhost:11434/v1`, `gpt-oss:20b`, and empty, respectively.

Do not point `STEWARD_CORS_ORIGINS` at `*` and expose this past `localhost`.
`11` states exactly why.

> **中文。** `ollama pull` 需要先有一个正在运行的 Ollama 守护进程（`ollama serve`，
> 或者桌面版应用）——本章这次运行显式起了一个，拉取在 **13 GB** 处完成。`gateway`
> 这个可选依赖组会在 `deepcase` 之上再装 `fastapi>=0.110` 和 `uvicorn>=0.29`。
> `uvicorn` 起来之后，访问 `GET http://127.0.0.1:8080/health` 返回了上面那行 JSON。
>
> 到这一步网关仍然是纯本地的——不需要密钥，不需要托管端点——但现在多了一个必须
> 保持运行的东西（Ollama），这和上一节"不需要任何服务"是不同的两句话，本章把两句
> 都如实写出来，而不是只挑好听的那句。跳过 HTTP、直接对代码提一个问题
> （`python scripts/ask_steward.py --role planner --lat 34.19 --lon -118.10
> --question "How severe is the damage in this area?"`），得到的是在
> `allow-planner-damage-tier3` 规则下被授权、带引证的四句回答，`"verifiability":
> "retained"`——是端到端跑通真实的 `gpt-oss:20b` 模型，不是打桩。模型提供方不改代码
> 就能换：`STEWARD_LLM_BASE_URL`、`STEWARD_LLM_MODEL`、`STEWARD_LLM_API_KEY` 分别
> 默认为 `http://localhost:11434/v1`、`gpt-oss:20b`、空。
>
> 不要把 `STEWARD_CORS_ORIGINS` 设成 `*` 再把这套网关暴露到 `localhost` 之外。`11`
> 章说明了确切理由。

## Rebuild a deep case — and why you probably cannot

`scripts/build_eaton_case.py`, `scripts/build_milton_case.py`, and
`scripts/build_ian_case.py` each take a `--data-root` argument that defaults
to a path on the maintainer's own workstation — a private, roughly 33 GB
corpus of DINS points, matched cross-view samples, and raw imagery that this
repository was never intended to carry. Pointed at anything else, the build
fails the way a fresh clone's attempt would:

```
$ python scripts/build_eaton_case.py --data-root /tmp/nonexistent-corpus
FileNotFoundError: registry file missing: /tmp/nonexistent-corpus/_registry/profiles/Eaton_Fire_profile.json
```

on a missing input file, not a plausible-looking substitute. **`events/`
cannot be regenerated from a fresh clone**, and no amount of correctly
installing dependencies changes that — the gap is data, not code.

What a third party can verify instead, without that corpus, is threefold,
and `06` walks all three field by field: the committed artifacts themselves —
every GeoJSON grid this project ships; each artifact's own sha256 in its
event's `artifact_manifest.jsonl`; and each event's `audit_log.jsonl`, the
append-only record of which outcome checks ran, against what, and whether
they passed. Reproducibility here means checking that a committed output is
what its own hash and audit trail say it is, not rerunning the pipeline that
produced it.

> **中文。** `scripts/build_eaton_case.py`、`scripts/build_milton_case.py`、
> `scripts/build_ian_case.py` 各自都带一个 `--data-root` 参数，默认值是维护者本人
> 工作站上的一个路径——一份私有的、约 33 GB 的语料，装着 DINS 点位、经匹配的跨视角
> 样本和原始影像，本仓库从一开始就没打算装下它。指向别的任何地方，构建都会像一次全新
> clone 的尝试那样失败：上面那条 `FileNotFoundError` 命令示例，失败在缺失输入文件，
> 而不是给出一个看起来能蒙混过关的替代品。**`events/` 无法从一次全新 clone 里重建**，
> 依赖装得再对也改变不了这一点——缺的是数据，不是代码。
>
> 没有那份语料，第三方能核实的是三件事，`06` 章逐字段走过全部三件：已提交的制品
> 本身——本项目发布的每一份 GeoJSON 网格；每份制品自己在其事件 `artifact_manifest.jsonl`
> 里的 sha256；以及每个事件的 `audit_log.jsonl`——记录着哪些结果检查针对什么跑过、
> 是否通过的追加式日志。这里的"可复现"，指的是核实一份已提交产物是否与它自己的哈希
> 和审计轨迹所说的一致，而不是重新跑一遍产出它的那条流水线。

## Check your own work

Before pushing, run the same gates CI runs:

```bash
python -m unittest discover -s tests
cd app && npm test
python scripts/publication_boundary.py plan --check
python scripts/manual_anchors.py check docs README.md src/geosteward/live/__init__.py
```

The third returned `allowlist matches the distribution policy` and exit `0`
against this state — 16 files allowed, 14 denied by name and rule (parcel
resolution, internal audience). The fourth returned `0 failure(s)` and exit
`0` — this chapter deliberately does not print the anchor *count* it
returned, because that count grows every time this manual gains a sentence,
and a specific number frozen into prose is exactly the kind of fact this
project keeps finding stale; treat `0 failure(s)` as the thing to check, not
any total next to it. These four are drawn from CI's two parallel jobs in
`.github/workflows/test.yml`: the first, third, and fourth are the
`unit-tests` job, in this same order; `npm test` is one step inside the
separate `app-build` job, which also builds the PWA and runs one more gate
this list does not repeat — `python scripts/publication_boundary.py verify
app/dist`, checking the assembled site rather than the plan. A green run of
all four here is not a smaller copy of CI; it is most of what CI checks, run
locally, in the same order within each job.

> **中文。** 推送之前，跑一遍 CI 跑的同一组关卡：`python -m unittest discover -s
> tests`；`cd app` 后 `npm test`；`python scripts/publication_boundary.py plan
> --check`；`python scripts/manual_anchors.py check docs README.md
> src/geosteward/live/__init__.py`。第三条在这个状态下返回了
> `allowlist matches the distribution policy` 和退出码 `0`——16 个文件被允许，14 个
> 按名字和规则被拒绝（地块级分辨率、内部受众）。第四条返回了 `0 failure(s)` 和退出码
> `0`——本章故意不把它返回的锚点*总数*写出来，因为这个数字每次本说明书增加一句话都会
> 变，把一个具体数字冻在文字里，正是本项目反复发现会过时的那类事实；要核对的是
> `0 failure(s)` 这件事本身，而不是它旁边的任何总数。这四道关卡取自
> `.github/workflows/test.yml` 里并行的两个 job：第一、三、四道属于 `unit-tests`
> 这个 job，顺序与此处一致；`npm test` 是另一个独立的 `app-build` job 里的一步，
> 这个 job 还会构建 PWA、再跑一道本清单没有重复列出的关卡——
> `python scripts/publication_boundary.py verify app/dist`，核对的是组装好的站点，
> 而不是发布计划。本地把这四道跑绿，不是 CI 的一个缩小版，而是 CI 检查内容的大部分，
> 只是放在本地跑、且在各自 job 内部顺序一致。
