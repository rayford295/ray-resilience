#!/usr/bin/env python
"""Side-by-side table of every zero-shot VLM evaluation committed under
`events/*/evidence/`, one block per (event, task), one row per model run.

Reads the `vlm_eval_summary` files the three builders write —
`vlm_severity_eval[.tag].json` (Palisades, 5 DINS classes),
`vlm_bitemporal_eval[.tag].json` (Milton pairs, 3 classes),
`vlm_crossview_eval[.tag].json` (Eaton, 3 repairability classes) — and
renders accuracy / NCSE / adjacent-error / per-class recall per model, with
the paper's closed-model numbers (where the eval file cites them) as
reference rows. Nothing is computed from predictions here; every number is
copied from an eval file that already passed the builder's fail-closed
checks, so the table can be regenerated from the committed tree alone.

Rows within a block are comparable only when they share the prompt sha256
and the sample (per-class count and seed); a row that differs is flagged in
the `same setup` column instead of being dropped. Blocks are never
comparable with each other: the tasks have different class counts.

    python scripts/compare_vlm_models.py                       # print markdown
    python scripts/compare_vlm_models.py --out docs/vlm_model_comparison.md --json docs/vlm_model_comparison.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import utc_stamp  # noqa: E402

TASKS = {
    "vlm_severity_eval": ("Palisades 2025 — single post-event image, 5 DINS classes (RAPID Prompt C, Dataset C2)", "images"),
    "vlm_bitemporal_eval": ("Milton 2024 — pre/post street-view pair, 3 classes (RAPID Prompt B, Bi-Temporal set)", "pairs"),
    "vlm_crossview_eval": ("Eaton 2025 — single post-event field image, 3 repairability classes (Prompt C collapsed)", "samples"),
}
_EVAL_RE = re.compile(r"^(vlm_[a-z]+_eval)(?:\.(?P<tag>[A-Za-z0-9.\-]+))?\.json$")


def find_eval_files(events_root: Path) -> list[Path]:
    out = []
    for event_dir in sorted(p for p in events_root.iterdir() if p.is_dir() and p.name != "archive"):
        evidence = event_dir / "evidence"
        if not evidence.is_dir():
            continue
        for f in sorted(evidence.iterdir()):
            if _EVAL_RE.match(f.name):
                out.append(f)
    return out


def load_eval(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    m = _EVAL_RE.match(path.name)
    doc["_task"] = m.group(1)
    doc["_file"] = path.as_posix()
    doc.setdefault("run_tag", m.group("tag"))
    doc.setdefault("event_id", path.parents[1].name)
    return doc


def _setup_key(doc: dict) -> tuple:
    return (doc.get("prompt_sha256"), doc.get("sample_per_class"), doc.get("seed"), doc.get("view"))


def _recall_string(doc: dict) -> str:
    per = doc.get("per_class") or {}
    vals = []
    for c in doc.get("classes") or list(per):
        r = (per.get(c) or {}).get("recall")
        vals.append("—" if r is None else f"{r:.2f}")
    return " / ".join(vals)


def build_comparison(docs: list[dict]) -> dict:
    """Group eval documents by (event, task); rows sorted by accuracy, best first.
    The reference setup of a block is the untagged run's when there is one,
    else the most common setup; rows that differ are flagged, not dropped."""
    blocks: dict[tuple[str, str], list[dict]] = {}
    for d in docs:
        blocks.setdefault((d["event_id"], d["_task"]), []).append(d)
    out = {"generated_utc": utc_stamp(), "blocks": []}
    for (event_id, task), rows in sorted(blocks.items()):
        untagged = [r for r in rows if not r.get("run_tag")]
        if untagged:
            ref = _setup_key(untagged[0])
        else:
            keys = [_setup_key(r) for r in rows]
            ref = max(set(keys), key=keys.count)
        title, unit = TASKS.get(task, (task, "items"))
        table = []
        for r in rows:
            table.append({
                "model": r.get("model"),
                "model_digest": (r.get("model_digest") or "")[:12] or None,
                "run_tag": r.get("run_tag") or "reference",
                "same_setup": _setup_key(r) == ref,
                "n": r.get("n_images"),
                "n_scored": r.get("n_scored"),
                "unanswered_rate": r.get("unanswered_rate"),
                "accuracy": r.get("accuracy"),
                "ncse": r.get("ncse"),
                "adjacent_error_rate": r.get("adjacent_error_rate"),
                "per_class_recall": _recall_string(r),
                "classes": r.get("classes"),
                "prompt_sha256": r.get("prompt_sha256"),
                "sample_per_class": r.get("sample_per_class"),
                "seed": r.get("seed"),
                "run_id": r.get("run_id"),
                "generated_utc": r.get("generated_utc"),
                "file": r.get("_file"),
            })
        table.sort(key=lambda x: (x["accuracy"] is None, -(x["accuracy"] or 0.0)))
        paper = {}
        for r in rows:
            ref_block = r.get("reference") or {}
            if isinstance(ref_block.get("reported_accuracy"), dict):
                paper = ref_block["reported_accuracy"]
                paper_note = ref_block.get("note") or ref_block.get("paper")
                break
        else:
            paper_note = None
        out["blocks"].append({
            "event_id": event_id, "task": task, "title": title, "unit": unit,
            "reference_setup": {"prompt_sha256": ref[0], "sample_per_class": ref[1], "seed": ref[2], "view": ref[3]},
            "rows": table,
            "paper_reference": {"reported_accuracy": paper, "note": paper_note} if paper else None,
        })
    return out


def _fmt(x, nd=4) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def render_markdown(comp: dict) -> str:
    lines = [
        "# Zero-shot VLM severity grading — model comparison",
        "",
        f"Generated {comp['generated_utc']} by `scripts/compare_vlm_models.py` from the committed eval summaries under `events/*/evidence/`. "
        "Every number is copied from a `vlm_eval_summary` file that passed its builder's fail-closed checks; nothing is recomputed here.",
        "",
        "Blocks are **not** comparable with each other (different class counts and truth scales). Within a block, rows marked ✓ share the "
        "prompt sha256 and the seeded sample with the reference run; a ✗ row was graded on a different setup and is shown for completeness only. "
        "One pass at temperature 0 on quantised local weights each; a `model_digest` pins the weights, not the arithmetic.",
        "",
    ]
    for b in comp["blocks"]:
        lines += [f"## {b['title']}", "", f"`{b['event_id']}` · `{b['task']}` · reference setup: "
                  f"sample {b['reference_setup']['sample_per_class'] or 'all'} per class"
                  f"{', seed ' + str(b['reference_setup']['seed']) if b['reference_setup']['seed'] is not None else ''}"
                  f"{', view ' + b['reference_setup']['view'] if b['reference_setup']['view'] else ''}"
                  f", prompt `{(b['reference_setup']['prompt_sha256'] or '')[:12]}…`", ""]
        lines.append(f"| model | weights | run | same setup | {b['unit']} | in-schema | unanswered | accuracy | NCSE | adjacent-error | per-class recall ({' / '.join(b['rows'][0]['classes'] or []) if b['rows'] and b['rows'][0]['classes'] else ''}) |")
        lines.append("|---|---|---|:-:|---:|---:|---:|---:|---:|---:|---|")
        for r in b["rows"]:
            lines.append(
                f"| `{r['model']}` | `{r['model_digest'] or '—'}` | {r['run_tag']} | {'✓' if r['same_setup'] else '✗'} | "
                f"{_fmt(r['n'])} | {_fmt(r['n_scored'])} | {_fmt(r['unanswered_rate'])} | **{_fmt(r['accuracy'])}** | **{_fmt(r['ncse'])}** | "
                f"{_fmt(r['adjacent_error_rate'])} | {r['per_class_recall']} |"
            )
        if b.get("paper_reference"):
            pr = b["paper_reference"]
            for name, acc in pr["reported_accuracy"].items():
                lines.append(f"| {name} (paper, closed API) | — | RAPID paper | ✗ | — | — | — | {_fmt(acc, 3)} | — | — | — |")
            if pr.get("note"):
                lines += ["", f"> {pr['note']}"]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--out", type=Path, default=None, help="write the markdown here (default: stdout)")
    ap.add_argument("--json", type=Path, default=None, help="also write the comparison as JSON")
    args = ap.parse_args()

    docs = [load_eval(p) for p in find_eval_files(args.events_root)]
    if not docs:
        print("no vlm_*_eval*.json under", args.events_root, file=sys.stderr)
        return 1
    comp = build_comparison(docs)
    md = render_markdown(comp)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md + "\n", encoding="utf-8")
        print(f"wrote {args.out} ({sum(len(b['rows']) for b in comp['blocks'])} runs in {len(comp['blocks'])} blocks)")
    else:
        sys.stdout.write(md + "\n")
    if args.json:
        args.json.write_text(json.dumps(comp, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
