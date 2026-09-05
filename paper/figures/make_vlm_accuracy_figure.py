#!/usr/bin/env python
"""Build the compact accuracy overview paired with Table 3."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402


OUT = Path(__file__).resolve().parent / "fig2_vlm_accuracy.png"

MODELS = [
    "qwen2.5vl:7b (ref.)",
    "qwen3-vl:32b",
    "qwen2.5vl:32b",
    "gemma3:27b",
    "mistral-small3.2:24b",
    "gemma3:12b",
    "qwen3-vl:8b",
]

TASKS = ["Palisades", "Milton pairs", "Eaton"]

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
    # Normalize within columns because the tasks use different class schemes.
    relative = np.column_stack([
        Normalize(vmin=ACCURACY[:, j].min(), vmax=ACCURACY[:, j].max())(ACCURACY[:, j])
        for j in range(ACCURACY.shape[1])
    ])

    fig, ax = plt.subplots(figsize=(3.15, 1.75))
    fig.patch.set_facecolor("white")
    ax.imshow(relative, cmap="Blues", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(TASKS)), labels=TASKS)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(MODELS)), labels=MODELS)
    ax.tick_params(axis="both", which="major", length=0, labelsize=6.4, pad=2)

    best = ACCURACY.argmax(axis=0)
    for i in range(ACCURACY.shape[0]):
        for j in range(ACCURACY.shape[1]):
            shade = relative[i, j]
            ax.text(
                j,
                i,
                f"{ACCURACY[i, j]:.3f}",
                ha="center",
                va="center",
                fontsize=6.5,
                color="white" if shade > 0.56 else "#1b1b1b",
                fontweight="bold" if i == best[j] else "normal",
            )

    # Thin rules keep the matrix legible when reproduced at column scale.
    ax.set_xticks(np.arange(-0.5, len(TASKS), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.39, right=0.985, top=0.84, bottom=0.035)
    fig.savefig(OUT, dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
