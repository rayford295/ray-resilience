# For the Program Committee

The shortest path through this submission: one minute to understand it, two to run it,
three to watch it, then one link per criterion.

**Submission snapshot:** release [`v0.1.0-oasis`](https://github.com/rayford295/ray-resilience/releases/tag/v0.1.0-oasis)
(paper PDF, eligibility statement, demo video and subtitles attached). `main` continues to move;
the release is the frozen version.

## 60 seconds — what this is

Ray Resilience is a disaster-resilience GeoAI system whose assistant, **Ray**, may only say
what the evidence supports. Autonomous pipelines turn federal hazard feeds and event data
(CAL FIRE DINS damage points, CDC SVI, 2020 census, street-view imagery) into H3 grids for
three deep cases — Eaton Fire 2025, Hurricane Milton 2024, Hurricane Ian 2022 — behind a
nationwide hourly watch. Every stage runs inside the **Steward Harness**: executable spatial
checks and mandatory uncertainty per tile, SHA-256 lineage in an append-only audit, a
declarative policy of *who may be told what at which resolution*, a CI gate that keeps the
public build inside that policy, and citation-by-default for every sentence the agent utters.
Three times the harness caught the system violating its own rules; each incident is preserved
and each fix is a control.

## 2 minutes — run it

```bash
git clone https://github.com/rayford295/ray-resilience && cd ray-resilience
python -m pip install -e ".[deepcase,dev]"
python -m pytest -q                            # 363 tests: the verifiable evaluation environment
python scripts/publication_boundary.py plan    # every artifact under events/, allowed or denied, with the rule
python scripts/judge_demo.py                   # one end-to-end pass: fetch → harness → audit → policy decisions (~1 min, keyless)
cd app && npm ci && npm test && npm run dev    # the PWA at http://localhost:5173 (67 tests)
```

Optional, to talk to Ray: `ollama pull gpt-oss:20b`, `pip install -e ".[deepcase,gateway]"`,
`uvicorn gateway.main:app --port 8080`. Any OpenAI-compatible endpoint works.

The deep-case builders read a ~33 GB corpus that is not redistributed (`DISASTER_DATASET_ROOT`);
every committed artifact, hash, audit row and evaluation file is verifiable without it.

## 3 minutes — watch it

[`docs/demo/ray-resilience-demo.mp4`](docs/demo/ray-resilience-demo.mp4) (2:55, voice-over +
subtitles). Nothing is mocked: the live-watch badge, the address lookup, the planner
re-ranking, the lineage panel, and the three Ask Ray outcomes are the real system.
[How it was recorded](docs/demo/README.md).

## The four criteria — one best piece of evidence each

| Criterion | Where to look | What you will see |
|---|---|---|
| **Tool-Use Rigor & Autonomy** | [`scripts/run_watch.py`](scripts/run_watch.py) → [`.github/workflows/live.yml`](.github/workflows/live.yml); [`scripts/build_eaton_case.py`](scripts/build_eaton_case.py); [`scripts/run_vlm_sweep.py`](scripts/run_vlm_sweep.py) | Keyless connectors refresh hourly with per-source failure recorded, never fabricated; builders execute point-in-polygon joins, H3 binning, block-centroid allocation and label crosswalks end to end and append audit rows; six VLMs were driven through one endpoint contract with fail-closed thresholds. The human-in-the-loop points are deliberate: role, the planner's trade-off slider (audit-logged), drawn-area questions, and no LLM task planner by design ([paper §2](paper/ray-resilience-oasis2026.pdf)). |
| **Architectural Robustness & Generalizability** | [`src/geosteward/harness/policy_v1.yaml`](src/geosteward/harness/policy_v1.yaml); [`tests/`](tests/) (policy matrix, connector error envelopes, containment property test); [`src/geosteward/deepcase/svi.py`](src/geosteward/deepcase/svi.py) and [`population.py`](src/geosteward/deepcase/population.py) | Two policy planes, default deny, validated at load; CDC `-999` counted not coerced; tract→cell SVI declared as downscaling; block→tile by centroid with no areal interpolation; a timed-out model call is a recorded `LLMUnavailable`; the same harness and policy produced two hazard types in two states with no geography in the policy. |
| **Social Good Alignment** | [Paper §4](paper/ray-resilience-oasis2026.pdf); [`paper/figures/fig3_priority_tradeoff.png`](paper/figures/fig3_priority_tradeoff.png) (+ [numbers](paper/figures/fig3_priority_tradeoff.json)); rules `deny-parcel-any-role`, `deny-resident-damage-assessment`, `allow-planner-damage-tier3` in the policy | Vulnerability = CDC SVI as published; exposure = 2020 census, pre-event; damage = official or human labels, never a model guess; priority = `t·damage + (1−t)·SVI` with `t` chosen by the planner. The trade-off curve shows the damage-only and SVI-only top-ten sets share no cell, so `t` is the decision, not a tie-breaker. Equity is enforced as named rules about who may be told what. |
| **Innovation & Reflection** | [`docs/incidents/2026-08-20-publication-boundary.md`](docs/incidents/2026-08-20-publication-boundary.md); [paper §5–6](paper/ray-resilience-oasis2026.pdf); [`docs/vlm_model_comparison.md`](docs/vlm_model_comparison.md) | Model output treated as *governed evidence* (`model_derived`: carries its own accuracy or nothing; refused by the claim plane and the gateway); three self-caught violations with the fixes that followed; an honest negative result on pre/post change grading (no open model beats the 7B reference, each with a different fixed bias). |

## Known limitations

- The deep-case builders are not reproducible by third parties without the ~33 GB corpus; the committed artifacts, hashes and audit logs are.
- The agent gateway is not hosted; the public demo has no chat backend. It runs locally against any OpenAI-compatible endpoint.
- VLM results are one pass at temperature 0 on 4-bit weights on a 24 GB card; Milton and Eaton are seeded samples.
- No community co-designed the operational definitions yet; the policy file is where negotiated definitions would go.
- Three deep cases are not national analysis capability, and the app says so.

Everything else — the full status log, design records, and the bilingual technical manual — is under [`docs/`](docs/).
