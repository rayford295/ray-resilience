#!/usr/bin/env python
"""Build the compact accuracy profile paired with Table 3."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


OUT = Path(__file__).resolve().parent / "fig2_vlm_accuracy.png"

MODELS = [
    "qwen2.5vl:7b",
    "qwen3-vl:32b",
    "qwen2.5vl:32b",
    "gemma3:27b",
    "mistral:24b",
    "gemma3:12b",
    "qwen3-vl:8b",
]

TASKS = ["Palisades", "Milton pairs", "Eaton"]
COLORS = ["#176B87", "#D88A2A", "#5B5BAA"]

ACCURACY = np.array([
    [0.475, 0.597, 0.910],
    [0.554, 0.381, 0.901],
    [0.507, 0.560, 0.931],
    [0.529, 0.500, 0.914],
    [0.505, 0.487, 0.935],
    [0.546, 0.427, 0.906],
    [0.514, 0.462, 0.924],
])


def main() -> None:
    # A shared axis is a visual profile only; task columns are not comparable.
    fig, ax = plt.subplots(figsize=(3.25, 1.78))
    fig.patch.set_facecolor("white")
    y = np.arange(len(MODELS))
    offsets = [-0.16, 0.0, 0.16]

    ax.axhspan(-0.48, 0.48, color="#F2F5F7", zorder=0)
    for j, (task, color, offset) in enumerate(zip(TASKS, COLORS, offsets)):
        values = ACCURACY[:, j]
        ax.hlines(y + offset, 0.35, values, color=color, linewidth=2.6, alpha=0.24, zorder=1)
        ax.scatter(
            values,
            y + offset,
            s=20,
            facecolor="white",
            edgecolor=color,
            linewidth=1.15,
            label=task,
            zorder=3,
        )
        best = values.argmax()
        ax.scatter(values[best], y[best] + offset, s=22, color=color, edgecolor="white", linewidth=0.6, zorder=4)

    # The closed numbers are reference marks, not additional open-model rows.
    ax.axvline(0.573, color=COLORS[0], linewidth=0.8, linestyle=(0, (3, 2)), alpha=0.75, zorder=1)
    ax.axvline(0.591, color=COLORS[1], linewidth=0.8, linestyle=(0, (3, 2)), alpha=0.75, zorder=1)

    ax.set_xlim(0.35, 1.0)
    ax.set_ylim(-0.48, len(MODELS) - 0.48)
    ax.invert_yaxis()
    ax.set_yticks(y, labels=MODELS)
    ax.tick_params(axis="y", length=0, labelsize=5.8, pad=2, colors="#24313B")
    ax.set_xticks([0.4, 0.6, 0.8, 1.0], labels=[".4", ".6", ".8", "1.0"])
    ax.tick_params(axis="x", length=0, labelsize=5.5, pad=1.5, colors="#66737D")
    ax.grid(axis="x", color="#DDE4E8", linewidth=0.65, zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="white",
               markeredgecolor=color, markeredgewidth=1.0, markersize=4.4, label=task)
        for task, color in zip(TASKS, COLORS)
    ]
    legend_handles.append(Line2D([0], [0], color="#7B8790", linewidth=0.8,
                                 linestyle=(0, (3, 2)), label="closed RAPID"))
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.12),
        ncol=4,
        frameon=False,
        handletextpad=0.25,
        columnspacing=0.65,
        borderaxespad=0,
        fontsize=5.6,
    )
    ax.set_xlabel("accuracy", fontsize=5.8, color="#66737D", labelpad=1)
    fig.subplots_adjust(left=0.30, right=0.99, top=0.78, bottom=0.17)
    fig.savefig(OUT, dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
