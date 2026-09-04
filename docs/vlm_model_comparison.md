# Zero-shot VLM severity grading — model comparison

Generated 20260904T183227Z by `scripts/compare_vlm_models.py` from the committed eval summaries under `events/*/evidence/`. Every number is copied from a `vlm_eval_summary` file that passed its builder's fail-closed checks; nothing is recomputed here.

Blocks are **not** comparable with each other (different class counts and truth scales). Within a block, rows marked ✓ share the prompt sha256 and the seeded sample with the reference run; a ✗ row was graded on a different setup and is shown for completeness only. One pass at temperature 0 on quantised local weights each; a `model_digest` pins the weights, not the arithmetic.

## Eaton 2025 — single post-event field image, 3 repairability classes (Prompt C collapsed)

`eaton-2025` · `vlm_crossview_eval` · reference setup: sample 300 per class, seed 2026, view post_field, prompt `70d933265e16…`

| model | weights | run | same setup | samples | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall (no_or_trace_damage / damaged_repairable / destroyed) |
|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|
| `mistral-small3.2:24b` | `5a408ab55df5` | mistral-small3.2-24b | ✓ | 630 | 630 | 0.0000 | **0.9349** | **0.0365** | 0.0571 | 0.98 / 0.03 / 0.98 |
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 630 | 626 | 0.0063 | **0.9313** | **0.0391** | 0.0591 | 0.97 / 0.13 / 0.97 |
| `qwen3-vl:8b` | `901cae732162` | qwen3-vl-8b | ✓ | 630 | 605 | 0.0397 | **0.9240** | **0.0413** | 0.0694 | 0.94 / 0.32 / 0.96 |
| `gemma3:27b` | `a418f5838eaf` | gemma3-27b | ✓ | 630 | 630 | 0.0000 | **0.9143** | **0.0492** | 0.0730 | 0.90 / 0.43 / 0.97 |
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 630 | 630 | 0.0000 | **0.9095** | **0.0492** | 0.0825 | 0.89 / 0.30 / 0.99 |
| `gemma3:12b` | `f4031aab637d` | gemma3-12b | ✓ | 630 | 630 | 0.0000 | **0.9063** | **0.0508** | 0.0857 | 0.93 / 0.27 / 0.95 |
| `qwen3-vl:32b-ctx8k` | `d2b2007e0497` | qwen3-vl-32b-ctx8k | ✓ | 630 | 627 | 0.0048 | **0.9011** | **0.0526** | 0.0925 | 0.94 / 0.20 / 0.93 |

## Milton 2024 — pre/post street-view pair, 3 classes (RAPID Prompt B, Bi-Temporal set)

`milton-2024` · `vlm_bitemporal_eval` · reference setup: sample 100 per class, seed 2026, prompt `a8df1841df15…`

| model | weights | run | same setup | pairs | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall (Mild / Moderate / Severe) |
|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 300 | 300 | 0.0000 | **0.5967** | **0.2383** | 0.3300 | 0.53 / 0.31 / 0.95 |
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 300 | 300 | 0.0000 | **0.5600** | **0.2400** | 0.4000 | 0.51 / 0.52 / 0.65 |
| `gemma3:27b` | `a418f5838eaf` | gemma3-27b | ✓ | 300 | 300 | 0.0000 | **0.5000** | **0.2567** | 0.4867 | 0.63 / 0.64 / 0.23 |
| `mistral-small3.2:24b` | `5a408ab55df5` | mistral-small3.2-24b | ✓ | 300 | 300 | 0.0000 | **0.4867** | **0.2583** | 0.5100 | 0.13 / 0.80 / 0.53 |
| `qwen3-vl:8b` | `901cae732162` | qwen3-vl-8b | ✓ | 300 | 275 | 0.0833 | **0.4618** | **0.3236** | 0.4291 | 0.18 / 0.57 / 0.60 |
| `gemma3:12b` | `f4031aab637d` | gemma3-12b | ✓ | 300 | 300 | 0.0000 | **0.4267** | **0.2867** | 0.5733 | 0.16 / 0.95 / 0.17 |
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
| `gemma3:12b` | `f4031aab637d` | gemma3-12b | ✓ | 295 | 295 | 0.0000 | **0.5458** | **0.1780** | 0.2610 | 0.93 / 0.14 / 0.30 / 0.37 / 0.97 |
| `gemma3:27b` | `a418f5838eaf` | gemma3-27b | ✓ | 295 | 295 | 0.0000 | **0.5288** | **0.1873** | 0.2644 | 0.93 / 0.07 / 0.22 / 0.44 / 0.97 |
| `qwen3-vl:8b` | `901cae732162` | qwen3-vl-8b | ✓ | 295 | 282 | 0.0441 | **0.5142** | **0.1950** | 0.2766 | 0.93 / 0.11 / 0.24 / 0.35 / 0.93 |
| `qwen2.5vl:32b-ctx8k` | `fd7f6360dca6` | qwen2.5vl-32b-ctx8k | ✓ | 295 | 294 | 0.0034 | **0.5068** | **0.2058** | 0.2721 | 1.00 / 0.12 / 0.17 / 0.30 / 0.93 |
| `mistral-small3.2:24b` | `5a408ab55df5` | mistral-small3.2-24b | ✓ | 295 | 295 | 0.0000 | **0.5051** | **0.2025** | 0.2644 | 0.98 / 0.17 / 0.17 / 0.21 / 0.97 |
| `qwen2.5vl:7b` | `5ced39dfa4ba` | reference | ✓ | 295 | 295 | 0.0000 | **0.4746** | **0.2127** | 0.2881 | 0.97 / 0.00 / 0.20 / 0.18 / 1.00 |
| GPT-5-mini (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.573 | — | — | — |
| GPT-5.1 (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.570 | — | — | — |
| Gemini-3-Pro (paper, closed API) | — | RAPID paper | ✗ | — | — | — | 0.442 | — | — | — |

> reported numbers are the paper's closed-model results on the same 295 images; this run is an open model, zero-shot, temperature 0

