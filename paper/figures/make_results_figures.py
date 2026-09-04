#!/usr/bin/env python
"""Result figures for the RAY paper, drawn from the committed VLM eval files.

Nothing here is typed in: accuracy, NCSE, confusion matrices and latencies are
read from `events/*/evidence/vlm_*_eval[.tag].json` and the prediction records
next to them, the same files `docs/vlm_model_comparison.md` is rendered from.

    python paper/figures/make_results_figures.py   # writes fig5_governed.png, fig6_results.png, fig7_milton_bias.png

Form choices (dataviz method): magnitude -> horizontal bars, one hue; the 7B
reference is the baseline and is drawn as an outlined bar; the paper's
closed-model number is a dashed reference line, never a bar (different sample
for Milton). Confusion matrices are row-normalised heatmaps in one sequential
hue with the value printed in every cell, so colour is never the only channel.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVENTS = REPO / "events"
DPI = 300

NAVY, TEAL, AMBER, AMBER_TXT, CORAL = "#1F3A5F", "#2A9D8F", "#E9A23B", "#B7761A", "#D95F43"
SLATE, INK, PAPER, BAND, GRID = "#5B6770", "#1B1B1B", "#F7F5F0", "#EEF2F6", "#D9DEE3"
TEAL_DARK = "#1B6B62"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": "none",
                     "axes.titleweight": "bold", "axes.titlecolor": NAVY})

#: served model -> (slug used in tagged file names, label in the figure). None slug = reference run.
MODELS = [
    ("qwen2.5vl:7b", None, "qwen2.5vl:7b (ref.)"),
    ("qwen3-vl:32b-ctx8k", "qwen3-vl-32b-ctx8k", "qwen3-vl:32b"),
    ("qwen2.5vl:32b-ctx8k", "qwen2.5vl-32b-ctx8k", "qwen2.5vl:32b"),
    ("gemma3:27b", "gemma3-27b", "gemma3:27b"),
    ("mistral-small3.2:24b", "mistral-small3.2-24b", "mistral-small3.2:24b"),
    ("gemma3:12b", "gemma3-12b", "gemma3:12b"),
    ("qwen3-vl:8b", "qwen3-vl-8b", "qwen3-vl:8b"),
]
CASES = [  # (event dir, eval stem, predictions stem, panel title, closed-model reference from the eval file)
    ("palisades-2025", "vlm_severity_eval", "vlm_predictions", "Palisades 2025 · single image · 5 DINS classes"),
    ("milton-2024", "vlm_bitemporal_eval", "vlm_bitemporal_predictions", "Milton 2024 · pre/post pair · 3 classes"),
    ("eaton-2025", "vlm_crossview_eval", "vlm_crossview_predictions", "Eaton 2025 · single image · 3 repairability classes"),
]


def tagged(stem: str, slug: str | None, suffix: str) -> str:
    return f"{stem}.{slug}{suffix}" if slug else f"{stem}{suffix}"


def load_eval(event: str, stem: str, slug: str | None) -> dict:
    return json.loads((EVENTS / event / "evidence" / tagged(stem, slug, ".json")).read_text(encoding="utf-8"))


def load_latencies(event: str, stem: str, slug: str | None) -> list[float]:
    p = EVENTS / event / "evidence" / tagged(stem, slug, ".jsonl")
    return [json.loads(l)["latency_s"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def closed_reference(ev: dict) -> tuple[str, float] | None:
    ref = (ev.get("reference") or {}).get("reported_accuracy") or {}
    if not ref:
        return None
    name, acc = max(ref.items(), key=lambda kv: kv[1])
    return name, acc


def style_axis(ax):
    ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, colors=SLATE, labelsize=7)
    for s in ax.spines.values():
        s.set_visible(False)


# ---------------------------------------------------------------------------
# Figure 5 — accuracy per case, NCSE beside it, latency as its own panel
# ---------------------------------------------------------------------------
def fig5_results():
    fig, axes2 = plt.subplots(2, 2, figsize=(7.5, 5.1), gridspec_kw={"wspace": 0.62, "hspace": 0.5})
    axes = [axes2[0][0], axes2[0][1], axes2[1][0], axes2[1][1]]
    fig.patch.set_facecolor("white")
    titles = ["Palisades 2025 — single image, 5 DINS classes",
              "Milton 2024 — pre/post pair, 3 classes",
              "Eaton 2025 — single image, 3 repairability classes"]
    for ax, (event, stem, _pred, _t), title in zip(axes[:3], CASES, titles):
        rows = []
        for model, slug, label in MODELS:
            ev = load_eval(event, stem, slug)
            rows.append((label, ev["accuracy"], ev["ncse"], slug is None))
        rows.sort(key=lambda r: r[1])  # low -> high; barh draws bottom-up so the best ends on top
        ys = range(len(rows))
        for y, (label, acc, ncse, is_ref) in zip(ys, rows):
            if is_ref:
                ax.barh(y, acc, height=0.64, color="white", edgecolor=NAVY, lw=1.2, hatch="////", zorder=3)
            else:
                ax.barh(y, acc, height=0.64, color=TEAL, zorder=3)
            ax.text(acc + 0.015, y, f"{acc:.3f}", va="center", ha="left", fontsize=6.8, color=INK, zorder=4)
            ax.text(0.015, y, f"NCSE {ncse:.3f}", va="center", ha="left", fontsize=5.6,
                    color=(NAVY if is_ref else "white"), zorder=4,
                    bbox=(dict(boxstyle="round,pad=0.15", fc="white", ec="none") if is_ref else None))
        ax.set_yticks(list(ys))
        ax.set_yticklabels([r[0] for r in rows], fontsize=6.8, color=INK)
        cr = closed_reference(load_eval(event, stem, None))
        if cr:
            name, acc = cr
            ax.axvline(acc, color=CORAL, lw=1.1, ls=(0, (4, 2)), zorder=5)
            ax.text(acc - 0.015, len(rows) - 0.22, f"{name} {acc:.3f} (closed, paper)", color=CORAL, fontsize=6.0,
                    ha="right", va="center")
        ax.set_xlim(0, 1.0)
        ax.set_ylim(-0.6, len(rows) + 0.3)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(["0", ".25", ".50", ".75", "1"])
        ax.set_title(title, fontsize=7.6, loc="left", pad=5)
        style_axis(ax)
        ax.set_xlabel("accuracy", fontsize=6.8, color=SLATE, labelpad=2)

    # latency panel: median with p90 whisker, per model, all three cases pooled per model
    ax = axes[3]
    lat_rows = []
    for model, slug, label in MODELS:
        pooled = []
        for event, stem, pred, _t in CASES:
            pooled += load_latencies(event, pred, slug)
        pooled.sort()
        lat_rows.append((label, statistics.median(pooled), pooled[int(0.9 * len(pooled))], pooled[-1]))
    lat_rows.sort(key=lambda r: -r[1])
    for y, (label, med, p90, mx) in enumerate(lat_rows):
        ax.plot([med, p90], [y, y], color=TEAL, lw=2.4, solid_capstyle="round", zorder=3)
        ax.plot(med, y, "o", color=TEAL_DARK, ms=5.4, zorder=4)
        ax.plot(mx, y, marker="|", color=CORAL, ms=8, mew=1.3, ls="none", zorder=4)
        ax.text(mx * 1.18, y, f"{mx:.0f} s", va="center", ha="left", fontsize=6.0, color=CORAL)
    ax.set_xscale("log")
    ax.set_xlim(2, 600)
    ax.set_xticks([3, 10, 30, 100, 300])
    ax.set_xticklabels(["3", "10", "30", "100", "300"])
    ax.set_yticks(range(len(lat_rows)))
    ax.set_yticklabels([r[0] for r in lat_rows], fontsize=6.8, color=INK)
    ax.set_ylim(-0.6, len(lat_rows) + 0.3)
    ax.set_title("Seconds per sample (log), all cases", fontsize=7.6, loc="left", pad=5)
    ax.set_xlabel("\u25cf median   \u25ac to p90   | max", fontsize=6.8, color=SLATE, labelpad=2)
    style_axis(ax)

    fig.text(0.02, 0.985, "Six open VLMs against a 7B reference — one pass, temperature 0, same seeded samples and prompt digests",
             fontsize=8.4, fontweight="bold", color=NAVY, va="top")
    fig.text(0.02, 0.945, "Hatched bar = qwen2.5vl:7b reference run.  Dashed line = the closed model's published accuracy (same 295 images for Palisades;\n"
             "a different 150-pair subset for Milton).  Panels use different class counts and are not comparable with each other.",
             fontsize=6.6, color=SLATE, va="top", style="italic", linespacing=1.35)
    fig.subplots_adjust(left=0.17, right=0.975, top=0.82, bottom=0.08)
    fig.savefig(HERE / "fig6_results.png", dpi=DPI, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6 — Milton: seven row-normalised confusion matrices
# ---------------------------------------------------------------------------
def fig6_milton_bias():
    cmap = LinearSegmentedColormap.from_list("teal_seq", ["#F4FAF9", "#BFE3DD", "#6CBFB4", TEAL, TEAL_DARK, "#0F4A44"])
    fig, axes = plt.subplots(1, 7, figsize=(7.5, 2.75))
    fig.patch.set_facecolor("white")
    for ax, (model, slug, label) in zip(axes, MODELS):
        ev = load_eval("milton-2024", "vlm_bitemporal_eval", slug)
        classes = ev["classes"]
        m = ev["confusion_rows_truth_cols_pred"]
        n_unans = ev.get("n_unparseable", 0) + ev.get("n_unknown_label", 0)
        norm = [[c / sum(row) if sum(row) else 0 for c in row] for row in m]
        ax.imshow(norm, cmap=cmap, vmin=0, vmax=1, aspect="equal")
        for i in range(3):
            for j in range(3):
                v = norm[i][j]
                ax.text(j, i, f"{v:.2f}".lstrip("0") if v < 1 else "1.0", ha="center", va="center", fontsize=6.6,
                        color="white" if v > 0.55 else INK, fontweight="bold" if i == j else "normal")
            ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=NAVY, lw=1.1))
        ax.set_xticks(range(3))
        ax.set_yticks(range(3))
        ax.set_xticklabels([c[:3] for c in classes], fontsize=6.2, color=SLATE)
        ax.set_yticklabels([c[:3] for c in classes] if ax is axes[0] else [], fontsize=6.2, color=SLATE)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        sub = f"acc {ev['accuracy']:.2f}"
        if n_unans:
            sub += f"\n{n_unans} unanswered"
        ax.set_title(f"{label}\n{sub}", fontsize=6.4, pad=4, color=NAVY if slug else INK, linespacing=1.15)
        if slug is None:
            for s in ax.spines.values():
                s.set_visible(True)
                s.set_edgecolor(NAVY)
                s.set_linewidth(1.2)
    axes[0].set_ylabel("truth (human perception)", fontsize=6.6, color=SLATE)
    fig.text(0.5, 0.045, "predicted class  ·  each row sums to 1 (unanswered pairs are excluded from the rows and counted in the title)",
             ha="center", fontsize=6.6, color=SLATE)
    fig.text(0.01, 0.985, "Milton 2024 pre/post pairs: every model fails in its own fixed direction",
             fontsize=8.6, fontweight="bold", color=NAVY, va="top")
    fig.text(0.01, 0.905, "Row-normalised confusion, 100 pairs per class, outlined diagonal = correct. Dark cells off the diagonal are the bias:\n"
             "qwen3-vl:32b pushes Mild and Moderate to Severe; gemma3:12b and mistral pull Severe down to Moderate. No vote across them would fix it.",
             fontsize=6.4, color=SLATE, va="top", style="italic", linespacing=1.35)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.64, bottom=0.16, wspace=0.18)
    fig.savefig(HERE / "fig7_milton_bias.png", dpi=DPI, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 7 — what happens to a model's guess under the harness
# ---------------------------------------------------------------------------
def _fit(ax, x, y, s, max_w, size, min_size=5.0, **kw):
    t = ax.text(x, y, s, fontsize=size, **kw)
    r = ax.figure.canvas.get_renderer()
    while size > min_size and t.get_window_extent(r).width / ax.figure.dpi > max_w:
        size -= 0.25
        t.set_fontsize(size)
    return t


def _box(ax, x, y, w, h, title, body, edge, fill=PAPER, title_color=None, ts=8.4, bs=6.4, pad=0.12, gap=0.26):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.11", lw=1.4, edgecolor=edge, facecolor=fill))
    _fit(ax, x + pad, y + h - pad, title, w - 2 * pad, ts, ha="left", va="top", fontweight="bold", color=title_color or edge)
    _fit(ax, x + pad, y + h - pad - gap, body, w - 2 * pad, bs, ha="left", va="top", color=INK, linespacing=1.3)


def _arrow(ax, p, q, color=NAVY, lw=1.4, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=lw, color=color,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, shrinkA=2, shrinkB=2))


def fig7_governed():
    W, H = 7.5, 4.55
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    ax.text(0.3, H - 0.2, "A model's guess on its way to becoming evidence — and where it stops", fontsize=10.5,
            fontweight="bold", color=NAVY, va="top")
    _fit(ax, 0.3, H - 0.5, "Model output is a distinct evidence class, model_derived: it carries its own measured accuracy or it carries nothing.",
         6.9, 7.0, ha="left", va="top", color=SLATE, style="italic")

    # top row: the pipeline
    y, h, w, gap = 2.5, 1.2, 1.62, 0.14
    xs = [0.3 + i * (w + gap) for i in range(4)]
    steps = [
        ("Labelled image", "RAPID Prompt B or C, verbatim.\nprompt_sha256 in every record:\nan edit shows as a different\nprompt, not a changed number.", TEAL, TEAL),
        ("Open VLM, local", "Any OpenAI-compatible vision\nendpoint; here Ollama on one\n24 GB GPU. Model digest and\nVRAM placement recorded.", AMBER, AMBER_TXT),
        ("One record per sample", "image sha256 · truth · prediction\n· response digest · latency.\nUnparseable is recorded as\nunparseable, never coerced.", NAVY, NAVY),
        ("Evaluation, fail-closed", "accuracy, NCSE, per-class recall.\nAbort if >20% off-schema, a\nmetric leaves [0,1], <95% in the\nevent's grid, or no uncertainty.", NAVY, NAVY),
    ]
    for x, (t, b, e, tc) in zip(xs, steps):
        _box(ax, x, y, w, h, t, b, e, title_color=tc)
    for i in range(3):
        _arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))

    # the product
    py, ph = 1.55, 0.58
    ax.add_patch(FancyBboxPatch((0.3, py), 6.9, ph, boxstyle="round,pad=0,rounding_size=0.1", lw=1.6, edgecolor=TEAL, facecolor=BAND))
    _fit(ax, 0.45, py + ph / 2, "H3 r9 agreement grid + eval summary, flagged model_derived", 3.9, 8.4, ha="left", va="center",
         fontweight="bold", color=TEAL)
    _fit(ax, 7.05, py + ph / 2, "sits beside the human-labelled grid it is evaluated against;\nevery number re-checkable from the records, without a GPU",
         2.75, 6.2, ha="right", va="center", color=SLATE, style="italic", linespacing=1.3)
    _arrow(ax, (xs[3] + w / 2, y), (xs[3] + w / 2, py + ph), color=TEAL, lw=1.8)

    # three gates
    gy, gh, gw = 0.22, 1.0, 2.2
    gates = [
        ("Publication planner", "classifies it as an evaluation\nproduct; the allowlist is\nregenerated and CI-checked", TEAL, "→ published as an evaluation"),
        ("Claim plane", "no rule admits model_derived\nevidence at any role, tier\nor resolution", CORAL, "→ default deny"),
        ("Gateway evidence store", "skips it and records the\nexclusion (Section 5, third\nincident)", CORAL, "→ never cited"),
    ]
    for i, (t, b, c, verdict) in enumerate(gates):
        x = 0.3 + i * (gw + 0.15)
        _box(ax, x, gy, gw, gh, t, b, c, fill="white", ts=8.0, bs=6.2, gap=0.24)
        _fit(ax, x + gw - 0.12, gy + 0.09, verdict, gw - 0.24, 6.6, ha="right", va="bottom", fontweight="bold", color=c)
        _arrow(ax, (0.3 + 3.45, py), (x + gw / 2, gy + gh), color=c, lw=1.2, rad=0.0 if i == 1 else (0.18 if i == 0 else -0.18))

    fig.savefig(HERE / "fig5_governed.png", dpi=DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig5_results()
    fig6_milton_bias()
    fig7_governed()
    for p in sorted(HERE.glob("fig[567]_*.png")):
        print(p.name, p.stat().st_size // 1024, "KB")
