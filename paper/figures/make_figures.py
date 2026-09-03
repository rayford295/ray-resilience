#!/usr/bin/env python
"""Concept figures for the RAY / Ray Resilience paper. Pure matplotlib, no data
inputs: every number quoted here is copied from the paper text and STATUS.

    python paper/figures/make_figures.py        # writes paper/figures/fig*.png

Canvas units are inches (1 data unit = 1 inch), so every box and font size
below is a print measurement. `fit_text` shrinks a label until it fits the
width it was given, so a wording change cannot silently overflow a box.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent
DPI = 300

# One palette for every figure.
NAVY = "#1F3A5F"      # harness / structure
TEAL = "#2A9D8F"      # data & evidence
AMBER = "#E9A23B"     # agent / model
AMBER_TXT = "#B7761A"
CORAL = "#D95F43"     # deny / refusal
SLATE = "#5B6770"     # secondary text
PAPER = "#F7F5F0"     # card fill
INK = "#1B1B1B"
BAND = "#EEF2F6"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "none"})


def canvas(w: float, h: float):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def fit_text(ax, x, y, s, max_w, size, min_size=5.0, **kw):
    """Draw text, shrinking the font until the rendered width is <= max_w inches."""
    t = ax.text(x, y, s, fontsize=size, **kw)
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    while size > min_size:
        w = t.get_window_extent(renderer).width / fig.dpi
        if w <= max_w:
            break
        size -= 0.25
        t.set_fontsize(size)
    return t


def box(ax, x, y, w, h, title=None, body=None, *, fill=PAPER, edge=NAVY, title_color=None,
        title_size=9.0, body_size=7.0, radius=0.12, lw=1.4, pad=0.13, title_gap=0.27):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                                linewidth=lw, edgecolor=edge, facecolor=fill))
    ty = y + h - pad
    if title:
        fit_text(ax, x + pad, ty, title, w - 2 * pad, title_size, ha="left", va="top",
                 fontweight="bold", color=title_color or edge)
        ty -= title_gap
    if body:
        fit_text(ax, x + pad, ty, body, w - 2 * pad, body_size, ha="left", va="top",
                 color=INK, linespacing=1.32)


def arrow(ax, p, q, color=NAVY, lw=1.4, style="-|>", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, linewidth=lw, color=color,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, shrinkA=2, shrinkB=2))


def note(ax, x, y, s, max_w, size=7.0, color=SLATE, ha="left", va="center", style="italic", weight="normal"):
    return fit_text(ax, x, y, s, max_w, size, ha=ha, va=va, color=color, style=style, fontweight=weight,
                    linespacing=1.3)


# ---------------------------------------------------------------------------
# Figure 1 — three planes on top of one harness
# ---------------------------------------------------------------------------
def fig1_architecture():
    W, H = 7.5, 5.0
    fig, ax = canvas(W, H)

    pw, ph, py = 2.2, 1.5, 3.2
    xs = [0.3, 2.65, 5.0]
    box(ax, xs[0], py, pw, ph, "Data plane",
        "GitHub Actions, hourly + on push\n• Tier-1 watch: USGS · NWS · NHC · NIFC\n"
        "• Deep-case builders: Eaton, Milton, Ian\n• Every artifact: SHA-256 + audit row\n• Append-only snapshots",
        edge=TEAL, body_size=6.8)
    box(ax, xs[1], py, pw, ph, "Presentation plane",
        "Installable PWA, keyless, offline\n• Resident mode: plain-language dossier\n"
        "• Planner mode: weights, area query\n• Lineage viewer to source snapshots\n• Keeps working if the agent is down",
        edge=NAVY, body_size=6.8)
    box(ax, xs[2], py, pw, ph, "Agent plane (Ray)",
        "Any OpenAI-compatible endpoint\npre-check → grounded generation\n→ citation post-check → audit\n"
        "• Cites [artifact:…] or refuses\n• Every refusal names its rule",
        edge=AMBER, title_color=AMBER_TXT, body_size=6.8)

    # arrows between planes (labels live in the legend line below)
    ym = py + ph / 2
    arrow(ax, (xs[0] + pw, ym), (xs[1], ym), color=TEAL, lw=1.8)
    arrow(ax, (xs[2], ym), (xs[1] + pw, ym), color=AMBER, lw=1.8)
    arrow(ax, (xs[0] + pw * 0.55, py), (xs[2] + pw * 0.45, py), color=TEAL, rad=0.14, ls="--", lw=1.4)

    ly = py - 0.6
    note(ax, 0.3, ly, "→ published artifacts (pass the distribution plane)", 2.4, 6.6, color=TEAL)
    note(ax, 2.75, ly, "← cited answers + badges", 1.9, 6.6, color=AMBER_TXT)
    note(ax, 4.55, ly, "⇢ evidence store: published events only, hashed grids", 2.7, 6.6, color=TEAL)

    # CI gate strip
    gy = py - 0.95
    ax.add_patch(FancyBboxPatch((0.3, gy), 6.9, 0.3, boxstyle="round,pad=0,rounding_size=0.08",
                                linewidth=0, facecolor=CORAL))
    fit_text(ax, W / 2, gy + 0.15,
             "CI gate: the assembled public site is verified against the distribution plane; a violating deploy fails",
             6.6, 7.0, ha="center", va="center", color="white", fontweight="bold")

    # harness band
    hy, hh = 0.3, 2.0
    ax.add_patch(FancyBboxPatch((0.3, hy), 6.9, hh, boxstyle="round,pad=0,rounding_size=0.16",
                                linewidth=1.8, edgecolor=NAVY, facecolor=BAND))
    ax.text(0.45, hy + hh - 0.14, "Steward Harness", fontsize=11.5, fontweight="bold", color=NAVY, va="top")
    note(ax, 2.3, hy + hh - 0.24, "enforced in code between every stage, and between the model and every sentence",
         4.8, 7.2)

    cw, ch, cy = 1.6, 1.32, hy + 0.17
    cxs = [0.44, 2.13, 3.82, 5.51]
    cards = [
        ("Outcome validity", "Executable spatial checks:\nCRS, join integrity, bounds.\nPer-tile uncertainty is\nmandatory, or the build fails."),
        ("Process validity", "SHA-256 per artifact;\nappend-only audit rows\n(agent, inputs, UTC).\nFailures recorded, never erased."),
        ("Institutional validity", "One YAML policy, two planes:\nclaim = what may be asserted,\ndistribution = what may ship.\nOrdered rules, default deny."),
        ("Verifiability", "retained > re-derivable >\ncited-only; weakest link.\nA license attribute gates\nredistribution by rule."),
    ]
    for x, (t, b) in zip(cxs, cards):
        box(ax, x, cy, cw, ch, t, b, fill="white", edge=NAVY, title_size=8.4, body_size=6.6)

    fig.savefig(OUT / "fig1_architecture.png", dpi=DPI, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 — the life of one question
# ---------------------------------------------------------------------------
def fig2_lifecycle():
    W, H = 7.5, 3.7
    fig, ax = canvas(W, H)

    steps = [
        ("Question", "role: resident or\nplanner; a point or\na drawn area\n(exactly one)", NAVY),
        ("Policy\npre-check", "claim plane: role ×\ntier × resolution ×\nin-AOI × verifiability;\nfirst match wins", NAVY),
        ("Evidence\nstore", "published events\nonly; hashed H3 r9\ngrids; declared\nunknowns; model-\nderived grids skipped", TEAL),
        ("Grounded\ngeneration", "the LLM sees the\nevidence block only;\nevery fact tagged\n[artifact:…]", AMBER),
        ("Citation\npost-check", "every factual sentence\ncites or is refused;\nclosed exemption set;\nat most 3 drafts", NAVY),
        ("Audit +\nanswer", "H3 cell, not the point;\nquestion as sha256;\nrule id on refusals;\nbadges in the app", NAVY),
    ]
    n = len(steps)
    bw, bh, gap = 1.06, 1.55, 0.2
    x0 = (W - (n * bw + (n - 1) * gap)) / 2
    y = 1.05
    centers = []
    for i, (t, b, c) in enumerate(steps):
        x = x0 + i * (bw + gap)
        box(ax, x, y, bw, bh, t, b, edge=c, title_size=8.0, body_size=6.2, title_gap=0.42,
            title_color=(AMBER_TXT if c == AMBER else c), pad=0.1)
        centers.append(x + bw / 2)
        if i < n - 1:
            arrow(ax, (x + bw, y + bh / 2), (x + bw + gap, y + bh / 2), color=NAVY)

    dy, dh = 0.22, 0.48
    for i, text in ((1, "deny → the refusal\nnames the rule;\nno model call"),
                    (2, "no evidence →\nsays so; never\nextrapolates"),
                    (4, "uncited fact after\n3 drafts → answer\nrefused, not patched")):
        arrow(ax, (centers[i], y), (centers[i], dy + dh), color=CORAL)
        ax.add_patch(FancyBboxPatch((centers[i] - bw / 2, dy), bw, dh, boxstyle="round,pad=0,rounding_size=0.08",
                                    linewidth=1.1, edgecolor=CORAL, facecolor="#FBEDE8"))
        fit_text(ax, centers[i], dy + dh / 2, text, bw - 0.1, 6.0, ha="center", va="center", color=CORAL,
                 linespacing=1.25)

    ax.text(0.3, H - 0.2, "One question through the gateway", fontsize=11, fontweight="bold", color=NAVY, va="top")
    note(ax, 0.3, H - 0.55, "Two deterministic gates bracket the model: nothing reaches the reader uncited,\n"
         "and nothing is logged finer than the claim plane lets an answer use.", 6.9, 7.2, va="top")

    fig.savefig(OUT / "fig2_lifecycle.png", dpi=DPI, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 — verifiability axis and license attribute
# ---------------------------------------------------------------------------
def fig3_verifiability():
    W, H = 7.5, 4.1
    fig, ax = canvas(W, H)
    ax.text(0.3, H - 0.2, "What can a reader do to check this claim, and may the evidence be kept?",
            fontsize=10.5, fontweight="bold", color=NAVY, va="top")

    ay = 3.2
    arrow(ax, (0.6, ay), (6.9, ay), color=NAVY, lw=2.0)
    note(ax, 0.6, ay + 0.18, "stronger", 1.0, 7.0)
    note(ax, 6.85, ay + 0.18, "weaker", 1.0, 7.0, ha="right")

    cols = [
        ("retained", TEAL, TEAL,
         "The evidence bytes are committed\nand hashed. Anyone can re-open\nthe artifact and recompute the\ndigest.",
         "e.g. H3 r9 damage, exposure and\nSVI grids; DINS-derived counts"),
        ("re-derivable", AMBER, AMBER_TXT,
         "Retention is forbidden by license,\nso the harness attests to the\nrequest plus a response digest:\na content-free record.",
         "e.g. facility context from a map\nAPI; a property test proves no\npayload reaches the audit"),
        ("cited-only", CORAL, CORAL,
         "A source is named but the reader\ncannot reproduce it. Grounded\nfree text is not stable even at\ntemperature zero.",
         "falls through to default-deny:\nthe citable unit is the citation,\nnever the prose"),
    ]
    cw, ch, cy = 2.1, 1.7, 1.28
    for i, (t, c, tc, body, ex) in enumerate(cols):
        x = 0.4 + i * (cw + 0.2)
        ax.plot([x + cw / 2, x + cw / 2], [ay, cy + ch], color=c, lw=1.2)
        ax.plot(x + cw / 2, ay, "o", color=c, ms=7)
        box(ax, x, cy, cw, ch, t, body, edge=c, title_color=tc, title_size=9.2, body_size=6.7)
        note(ax, x + 0.13, cy + 0.14, ex, cw - 0.26, 6.3, va="bottom")

    # weakest link
    ax.add_patch(FancyBboxPatch((0.4, 0.78), 6.7, 0.34, boxstyle="round,pad=0,rounding_size=0.08",
                                linewidth=1.1, edgecolor=NAVY, facecolor=BAND))
    fit_text(ax, W / 2, 0.95, "Weakest link: an answer's verifiability is the weakest of its citations, "
             "and a live fact may never be the only support for an answer.", 6.5, 6.9,
             ha="center", va="center", color=NAVY)

    # license row
    note(ax, 0.4, 0.58, "license attribute (distribution plane):", 2.6, 7.2, color=NAVY, style="normal", weight="bold")
    tags = [("project", TEAL), ("public-domain", TEAL), ("open-license-attribution", AMBER), ("third-party-restricted", CORAL)]
    tx = 2.7
    for name, c in tags:
        tw = 0.05 * len(name) + 0.16
        ax.add_patch(FancyBboxPatch((tx, 0.46), tw, 0.24, boxstyle="round,pad=0,rounding_size=0.06",
                                    linewidth=0, facecolor=c))
        fit_text(ax, tx + tw / 2, 0.58, name, tw - 0.06, 6.2, ha="center", va="center", color="white", fontweight="bold")
        tx += tw + 0.07
    note(ax, 0.4, 0.22, "Attribution travels inside the artifact (OSM / ODbL). "
         "Third-party-restricted classes never publish, however they reached the build.", 6.9, 6.4)

    fig.savefig(OUT / "fig3_verifiability.png", dpi=DPI, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4 — cases at a glance
# ---------------------------------------------------------------------------
def fig4_cases():
    W, H = 7.5, 4.6
    fig, ax = canvas(W, H)

    ax.add_patch(FancyBboxPatch((0.3, H - 1.0), 6.9, 0.78, boxstyle="round,pad=0,rounding_size=0.12",
                                linewidth=1.4, edgecolor=TEAL, facecolor=BAND))
    ax.text(0.45, H - 0.36, "Tier 1: nationwide watch, hourly, keyless", fontsize=9.2, fontweight="bold", color=TEAL, va="center")
    note(ax, 0.45, H - 0.72, "USGS earthquakes · NWS alerts (drawn hollow: an advisory never looks like an occurrence) · "
         "NHC tropical cyclones · NIFC/WFIGS wildfires\n"
         "· WPC Day-1 excessive-rainfall outlook as a separate product. Per-source failures are declared, not hidden.",
         6.6, 6.4, color=INK, style="normal")

    cards = [
        ("Eaton Fire 2025", "wildfire · Los Angeles County, CA", NAVY, NAVY, [
            ("18,428", "CAL FIRE DINS structure points\n→ 265-cell H3 r9 damage grid"),
            ("20", "Census tracts of CDC SVI 2022;\ndownscaling declared per feature"),
            ("2,244", "reliability-gated cross-view street\nsamples → 109-cell evidence grid"),
            ("46,341", "residents (2020 blocks, pre-event\nvintage declared) · 27 OSM facilities"),
        ], "declared: a damage class with n = 30\nlacks statistical power"),
        ("Hurricane Milton 2024", "hurricane · Horseshoe Beach + Pinellas, FL", TEAL, TEAL, [
            ("2,556", "labeled pre/post street-view pairs\n→ 15-cell grid"),
            ("5,618", "Pinellas cells with county debris\nvolumes and wind/rain covariates"),
            ("772,293", "residents · 200 OSM facilities\nacross the two AOIs"),
            ("0", "generated-imagery samples used;\nthe exclusion itself is auditable"),
        ], "declared: post-imagery is season-\ncumulative (Debby, Helene, Milton)"),
        ("Hurricane Ian 2022", "hurricane · Lee County, FL", AMBER, AMBER_TXT, [
            ("886", "matched samples\n→ 190-cell evidence grid"),
            ("4,121", "further street-view positions,\nshipped as a density-only layer"),
            ("5,428", "residents · 79 OSM facilities"),
            ("—", "no verifiable per-point severity\nlink: candor over coverage"),
        ], "declared: no per-point severity\nclaims from the density layer"),
    ]
    cw, ch, cy = 2.2, 3.05, 0.42
    for i, (t, sub, c, tc, rows, foot) in enumerate(cards):
        x = 0.3 + i * (cw + 0.15)
        ax.add_patch(FancyBboxPatch((x, cy), cw, ch, boxstyle="round,pad=0,rounding_size=0.14",
                                    linewidth=1.5, edgecolor=c, facecolor=PAPER))
        fit_text(ax, x + 0.13, cy + ch - 0.13, t, cw - 0.26, 9.4, ha="left", va="top", fontweight="bold", color=tc)
        note(ax, x + 0.13, cy + ch - 0.4, sub, cw - 0.26, 6.4, va="top")
        ry = cy + ch - 0.68
        for num, desc in rows:
            fit_text(ax, x + 0.13, ry, num, 0.62, 9.6, ha="left", va="top", fontweight="bold", color=INK)
            fit_text(ax, x + 0.8, ry + 0.01, desc, cw - 0.93, 6.1, ha="left", va="top", color=INK, linespacing=1.25)
            ry -= 0.5
        ax.plot([x + 0.13, x + cw - 0.13], [cy + 0.5, cy + 0.5], color=c, lw=0.8, alpha=0.6)
        note(ax, x + 0.13, cy + 0.12, foot, cw - 0.26, 6.0, color=tc, va="bottom")

    note(ax, 0.3, 0.2, "All source imagery traces to a hashed dataset registry (134,272 files, ~33 GB, SHA-256). "
         "Exposure, vulnerability and damage analysis exist only inside these three AOIs, and the app says so.",
         6.9, 6.3)

    fig.savefig(OUT / "fig4_cases.png", dpi=DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig1_architecture()
    fig2_lifecycle()
    fig3_verifiability()
    fig4_cases()
    for p in sorted(OUT.glob("fig*.png")):
        print(p.name, p.stat().st_size // 1024, "KB")
