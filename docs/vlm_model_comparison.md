# Zero-shot VLM severity grading — model comparison

Generated 20260904T071647Z by `scripts/compare_vlm_models.py` from the committed eval summaries under `events/*/evidence/`. Every number is copied from a `vlm_eval_summary` file that passed its builder's fail-closed checks; nothing is recomputed here.

Blocks are **not** comparable with each other (different class counts and truth scales). Within a block, rows marked ✓ share the prompt sha256 and the seeded sample with the reference run; a ✗ row was graded on a different setup and is shown for completeness only. One pass at temperature 0 on quantised local weights each; a `model_digest` pins the weights, not the arithmetic.

## Eaton 2025 — single post-event field image, 3 repairability classes (Prompt C collapsed)

`eaton-2025` · `vlm_crossview_eval` · reference setup: sample 300 per class, seed 2026, view post_field, prompt `70d933265e16…`

| model | weights | run | same setup | samples | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall (no_or_trace_damage / damaged_repairable / destroyed) |
|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 630 | 626 | 0.0063 | **0.9313** | **0.0391** | 0.0591 | 0.97 / 0.13 / 0.97 |
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 630 | 630 | 0.0000 | **0.9095** | **0.0492** | 0.0825 | 0.89 / 0.30 / 0.99 |
| `qwen3-vl:32b-ctx8k` | `d2b2007e0497` | qwen3-vl-32b-ctx8k | ✓ | 630 | 627 | 0.0048 | **0.9011** | **0.0526** | 0.0925 | 0.94 / 0.20 / 0.93 |

## Milton 2024 — pre/post street-view pair, 3 classes (RAPID Prompt B, Bi-Temporal set)

`milton-2024` · `vlm_bitemporal_eval` · reference setup: sample 100 per class, seed 2026, prompt `a8df1841df15…`

| model | weights | run | same setup | pairs | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall (Mild / Moderate / Severe) |
|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 300 | 300 | 0.0000 | **0.5967** | **0.2383** | 0.3300 | 0.53 / 0.31 / 0.95 |
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 300 | 300 | 0.0000 | **0.5600** | **0.2400** | 0.4000 | 0.51 / 0.52 / 0.65 |
| `qwen3-vl:32b-ctx8k` | `d2b2007e0497` | qwen3-vl-32b-ctx8k | ✓ | 300 | 299 | 0.0033 | **0.3813** | **0.4314** | 0.3746 | 0.01 / 0.14 / 1.00 |
| GPT-5.1 (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.591 | — | — | — |
| GPT-5-mini (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.503 | — | — | — |
| Gemini-3-Pro (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.493 | — | — | — |

> the paper graded 150 pairs of this set with closed models; this run is an open model on a seeded stratified sample, temperature 0

## Palisades 2025 — single post-event image, 5 DINS classes (RAPID Prompt C, Dataset C2)

`palisades-2025` · `vlm_severity_eval` · reference setup: sample all per class, prompt `70d933265e16…`

| model | weights | run | same setup | images | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall (0_No_Damage / 1_Affected_1_9 / 2_Minor_10_25 / 3_Major_26_50 / 4_Destroyed_50plus) |
|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|
| `qwen3-vl:32b-ctx8k` | `d2b2007e0497` | qwen3-vl-32b-ctx8k | ✓ | 295 | 294 | 0.0034 | **0.5544** | **0.1760** | 0.2449 | 0.88 / 0.28 / 0.30 / 0.35 / 0.93 |
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 295 | 294 | 0.0034 | **0.5068** | **0.2058** | 0.2721 | 1.00 / 0.12 / 0.17 / 0.30 / 0.93 |
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 295 | 295 | 0.0000 | **0.4746** | **0.2127** | 0.2881 | 0.97 / 0.00 / 0.20 / 0.18 / 1.00 |
| GPT-5-mini (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.573 | — | — | — |
| GPT-5.1 (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.570 | — | — | — |
| Gemini-3-Pro (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.442 | — | — | — |

> reported numbers are the paper's closed-model results on the same 295 images; this run is an open model, zero-shot, temperature 0

