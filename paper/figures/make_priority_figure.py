#!/usr/bin/env python
"""Map + trade-off curve for the planner's priority, from the committed Eaton grid.

Reads events/eaton-2025/exposure/svi_h3_r9_context.geojson (265 H3 r9 cells with
destroyed_rate and the CDC SVI RPL_THEMES percentile) and applies the app's own
formula, priority = t*damage + (1-t)*SVI (app/src/lib/data.js, priorityScores),
for t from 0 to 1. Left: the cells coloured by priority at t = 0.5 with the ten
highest outlined. Right: how the top-10 set changes with t — its overlap with
the damage-only ranking (t = 1) and with the SVI-only ranking (t = 0), plus how
many of the ten would not be in the top ten under either extreme. This is the
sensitivity analysis the planner sees live on the slider, made static.

    python paper/figures/make_priority_figure.py   # writes fig3_priority_tradeoff.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
GRID = REPO / "events" / "eaton-2025" / "exposure" / "svi_h3_r9_context.geojson"
NAVY, TEAL, AMBER, CORAL, SLATE, INK, GRIDC = "#1F3A5F", "#2A9D8F", "#E9A23B", "#D95F43", "#5B6770", "#1B1B1B", "#D9DEE3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})


def load():
    g = json.loads(GRID.read_text(encoding="utf-8"))
    cells = []
    for f in g["features"]:
        p = f["properties"]
        dmg = p.get("destroyed_rate")
        svi = p.get("RPL_THEMES")
        ring = f["geometry"]["coordinates"][0] if f["geometry"]["type"] == "Polygon" else f["geometry"]["coordinates"][0][0]
        cells.append({"id": p["h3_cell"], "dmg": dmg, "svi": svi, "n": p.get("n_structures"), "ring": ring,
                      "missing": dmg is None or svi is None})
    return cells


def scores(cells, t):
    return {c["id"]: t * (c["dmg"] or 0.0) + (1 - t) * (c["svi"] or 0.0) for c in cells}


def top(cells, t, k=10):
    s = scores(cells, t)
    return set(sorted(s, key=lambda i: -s[i])[:k])


def main():
    cells = load()
    n_missing = sum(c["missing"] for c in cells)
    ts = [round(i / 20, 2) for i in range(21)]
    top_dmg, top_svi = top(cells, 1.0), top(cells, 0.0)
    ov_dmg = [len(top(cells, t) & top_dmg) for t in ts]
    ov_svi = [len(top(cells, t) & top_svi) for t in ts]
    neither = [len(top(cells, t) - top_dmg - top_svi) for t in ts]

    fig = plt.figure(figsize=(7.5, 3.7))
    fig.patch.set_facecolor("white")
    ax_map = fig.add_axes([0.02, 0.15, 0.50, 0.74])
    ax_cur = fig.add_axes([0.62, 0.20, 0.35, 0.50])

    # --- map at t = 0.5
    t0 = 0.5
    s = scores(cells, t0)
    top0 = top(cells, t0)
    cmap = LinearSegmentedColormap.from_list("teal_seq", ["#F4FAF9", "#BFE3DD", "#6CBFB4", TEAL, "#1B6B62", "#0F4A44"])
    vmax = max(s.values()) or 1.0
    polys = [[(x, y) for x, y in c["ring"]] for c in cells]
    colors = [cmap(s[c["id"]] / vmax) if not c["missing"] else (0.93, 0.93, 0.93, 1) for c in cells]
    ax_map.add_collection(PolyCollection(polys, facecolors=colors, edgecolors="white", linewidths=0.25))
    ax_map.add_collection(PolyCollection([[(x, y) for x, y in c["ring"]] for c in cells if c["id"] in top0],
                                         facecolors="none", edgecolors=CORAL, linewidths=1.3))
    xs = [x for c in cells for x, _ in c["ring"]]
    ys = [y for c in cells for _, y in c["ring"]]
    pad = 0.004
    ax_map.set_xlim(min(xs) - pad, max(xs) + pad)
    ax_map.set_ylim(min(ys) - pad, max(ys) + pad)
    ax_map.set_aspect(1 / 0.83)  # ~cos(34.2°) so hexagons are not squashed
    ax_map.axis("off")
    ax_map.set_title("Eaton Fire 2025 — inspection priority at t = 0.5, H3 r9", fontsize=8.4, loc="left", color=NAVY, fontweight="bold")
    ax_map.text(0.0, -0.03, f"265 cells · colour = 0.5 × destroyed rate + 0.5 × SVI percentile · outline = top 10\n"
                f"grey = {n_missing} cell with a missing input (scored with 0, flagged in the app)",
                transform=ax_map.transAxes, fontsize=6.0, color=SLATE, va="top", linespacing=1.35)
    # scale bar ~1 km at this latitude (1° lon ≈ 92 km)
    x0, y0 = min(xs) + 0.002, min(ys) + 0.002
    ax_map.plot([x0, x0 + 1 / 92.0], [y0, y0], color=INK, lw=1.4)
    ax_map.text(x0 + 0.5 / 92.0, y0 + 0.0006, "1 km", ha="center", fontsize=6, color=INK)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
    cb = fig.colorbar(sm, ax=ax_map, fraction=0.03, pad=0.01, shrink=0.6)
    cb.ax.tick_params(labelsize=6, length=0)
    cb.outline.set_visible(False)

    # --- curve
    ax_cur.plot(ts, ov_dmg, color=CORAL, lw=2, marker="o", ms=3.5, label="shared with damage-only top 10 (t = 1)")
    ax_cur.plot(ts, ov_svi, color=TEAL, lw=2, marker="o", ms=3.5, label="shared with SVI-only top 10 (t = 0)")
    ax_cur.plot(ts, neither, color=NAVY, lw=1.6, ls="--", marker="s", ms=3, label="in neither extreme's top 10")
    ax_cur.axvline(0.5, color=GRIDC, lw=1)
    ax_cur.set_xlim(-0.02, 1.02)
    ax_cur.set_ylim(0, 10.5)
    ax_cur.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax_cur.set_xticklabels(["0\nSVI\nonly", ".25", ".50", ".75", "1\ndamage\nonly"], fontsize=6.6)
    ax_cur.set_yticks(range(0, 11, 2))
    ax_cur.set_ylabel("cells (of the top 10)", fontsize=7, color=SLATE)
    ax_cur.set_xlabel("t — the planner's weight on structural damage", fontsize=7, color=SLATE)
    ax_cur.grid(axis="y", color=GRIDC, lw=0.6)
    ax_cur.set_axisbelow(True)
    for sp in ax_cur.spines.values():
        sp.set_visible(False)
    ax_cur.tick_params(length=0, labelsize=6.8, colors=SLATE)
    ax_cur.set_title("Which ten cells come first depends on t", fontsize=8.4, loc="left", color=NAVY, fontweight="bold", pad=44)
    ax_cur.legend(fontsize=6.2, frameon=False, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=1,
                  handlelength=1.6, borderaxespad=0.2)

    fig.savefig(HERE / "fig3_priority_tradeoff.png", dpi=300, facecolor="white")
    summary = {"t": ts, "overlap_with_damage_only": ov_dmg, "overlap_with_svi_only": ov_svi, "in_neither": neither,
               "n_cells": len(cells), "n_missing_input": n_missing,
               "top10_at_0.5": sorted(top0), "top10_damage_only": sorted(top_dmg), "top10_svi_only": sorted(top_svi),
               "overlap_damage_vs_svi_extremes": len(top_dmg & top_svi)}
    (HERE / "fig3_priority_tradeoff.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("top10_at_0.5", "top10_damage_only", "top10_svi_only")}))


if __name__ == "__main__":
    main()
