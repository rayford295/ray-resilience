#!/usr/bin/env python
"""Milton 2024 (Horseshoe Beach): zero-shot VLM grading of pre/post street-view pairs.

Stage `evidence.vlm_bitemporal` for `events/milton-2024/`. Input is the public
Bi-Temporal street-view set — images from the Hugging Face release
(`Rayford295/BiTemporal-StreetView-Damage`, `final_label_image/`) and the pair
table from the Figshare record (10.6084/m9.figshare.28801208.v2,
`LLM(GPT-4o-mini).csv`) whose `root` column names each pair as
`<pre_id>_vs_<post_id>(k)` and carries the pair's coordinates and the human
perception label. That CSV is also what the committed
`evidence/bitemporal_h3_r9_grid.geojson` was built from, so its labels are the
truth here, and the Hugging Face folder label is recorded beside them with the
disagreement count declared.

RAPID's pre/post prompt (Prompt B) is used verbatim; the model is any
OpenAI-compatible vision endpoint (local Ollama by default). A stratified
`--sample N` grades N pairs per class, seeded, so a laptop-sized run is a
declared subset rather than a silent one.

Writes, through the Steward Harness:

  snapshots/registry/BiTemporal_StreetView_Damage_profile.json   dataset_registry_snapshot (internal)
  snapshots/bitemporal/pair_table.json.gz                        source_snapshot_ccby (internal: coordinates)
  snapshots/vlm/prompt_bitemporal_3class.txt                     vlm_prompt (public)
  evidence/vlm_bitemporal_predictions.jsonl                      vlm_prediction_records (lineage)
  evidence/vlm_bitemporal_eval.json                              vlm_eval_summary (public)
  evidence/vlm_bitemporal_h3_r9_grid.geojson                     evidence_grid (tile, public)

Fail-closed on: >20% off-schema answers; accuracy/NCSE outside [0,1]; fewer
than 95% of graded pairs falling inside the committed bitemporal grid's cells
(the sample must be about the same place the event already describes).
Resumable by pair id.

    python scripts/build_milton_vlm_bitemporal.py --images <dir>/final_label_image \\
        --pairs-csv <dir>/llm_pairs.csv --sample 100
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp  # noqa: E402
from geosteward.deepcase.vlm_severity import (  # noqa: E402
    BITEMPORAL_PROMPT,
    HURRICANE_CLASSES,
    HURRICANE_TO_CANONICAL,
    aggregate_h3,
    classify_pair,
    normalise_label,
    record_to_row,
    sha256_text,
    summarize,
)
from geosteward.gateway.llm import chat_completion  # noqa: E402
from geosteward.harness.audit import AuditLog, sha256_file  # noqa: E402
from geosteward.harness.checks.outcome import (  # noqa: E402
    check_bounds,
    check_crs,
    check_uncertainty_present,
)

EVENT_ID = "milton-2024"
STAGE = "evidence.vlm_bitemporal"
MAX_UNANSWERED_RATE = 0.20
MIN_IN_GRID = 0.95
FOLDER_LABEL = {"folder_0": "Mild", "folder_1": "Moderate", "folder_2": "Severe"}
HF_URL = "https://huggingface.co/datasets/Rayford295/BiTemporal-StreetView-Damage"
FIGSHARE_DOI = "10.6084/m9.figshare.28801208.v2"


def fail_closed(audit: AuditLog, results) -> None:
    for r in results:
        audit.record("check", STAGE, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{STAGE}] outcome check failed: {r.check}: {r.detail}")


def model_identity() -> dict[str, str | None]:
    base_url = os.environ.get("STEWARD_LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.environ.get("STEWARD_LLM_MODEL", "gpt-oss:20b")
    digest = None
    try:
        root = base_url.rstrip("/").removesuffix("/v1")
        with urllib.request.urlopen(f"{root}/api/tags", timeout=5) as resp:
            for m in json.load(resp).get("models", []):
                if m.get("name") == model or m.get("model") == model:
                    digest = m.get("digest")
    except Exception:
        pass
    return {"model": model, "base_url": base_url, "digest": digest}


_ID_RE = re.compile(r"^(\d+?)(?:_(\d{4}))?(?:_\d)?\.png$")
_PAIR_DIR_RE = re.compile(r"^(\d+)_vs_(\d+)(?:\(\d+\))?$")


def index_images(images_root: Path) -> dict[str, list[Path]]:
    by_id: dict[str, list[Path]] = {}
    for p in images_root.rglob("*.png"):
        m = _ID_RE.match(p.name)
        if m:
            by_id.setdefault(m.group(1), []).append(p)
    return by_id


def index_pair_dirs(images_root: Path) -> dict[str, Path]:
    """`<pre>_vs_<post>` -> directory, for the original release layout in which
    every pair is its own folder (`folder_k/<pre>_vs_<post>(n)/<pre>_2023.png,
    <post>_2024.png`). The Hugging Face zip flattens this into `no_damage/`
    and `folder_k/`; both layouts resolve through `load_pairs`."""
    out: dict[str, Path] = {}
    for d in images_root.rglob("*"):
        if d.is_dir():
            m = _PAIR_DIR_RE.match(d.name)
            if m:
                out.setdefault(f"{m.group(1)}_vs_{m.group(2)}", d)
    return out


def _is_pre(p: Path) -> bool:
    return p.parent.name == "no_damage" or p.stem.endswith("_2023")


def _folder_label(p: Path) -> str | None:
    """The `folder_k` the post image sits under, at whatever depth."""
    for parent in (p.parent, *p.parents):
        if parent.name in FOLDER_LABEL:
            return FOLDER_LABEL[parent.name]
    return None


def load_pairs(csv_path: Path, images_root: Path) -> tuple[list[dict], dict]:
    """Pair rows with resolved image paths; the `root` workstation path is
    consumed here and never written anywhere. Resolves the pair directory
    layout first (exact), then falls back to id lookup (Hugging Face layout)."""
    by_id = index_images(images_root)
    pair_dirs = index_pair_dirs(images_root)
    pairs, dropped = [], {"unresolved_pre": 0, "unresolved_post": 0, "bad_label": 0}
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            base = re.sub(r"\(\d+\)$", "", row["root"].rstrip("/").split("/")[-1])
            pre_id, post_id = base.split("_vs_")
            pair_dir = pair_dirs.get(f"{pre_id}_vs_{post_id}")
            if pair_dir is not None:
                pre = [p for p in pair_dir.glob(f"{pre_id}_*.png") if _is_pre(p)]
                post = [p for p in pair_dir.glob(f"{post_id}_*.png") if not _is_pre(p)]
            else:
                pre = [p for p in by_id.get(pre_id, []) if _is_pre(p)]
                post = [p for p in by_id.get(post_id, []) if not _is_pre(p)]
            truth = normalise_label(row["human_damage_perception"], HURRICANE_CLASSES)
            if not pre:
                dropped["unresolved_pre"] += 1; continue
            if not post:
                dropped["unresolved_post"] += 1; continue
            if truth is None:
                dropped["bad_label"] += 1; continue
            pairs.append({
                "pair_id": f"{pre_id}_vs_{post_id}", "pre": sorted(pre)[0], "post": sorted(post)[0],
                "truth": truth, "folder_label": _folder_label(sorted(post)[0]),
                "lat": round(float(row["lat"]), 6), "lon": round(float(row["lon"]), 6),
            })
    return pairs, dropped


def stratified(pairs: list[dict], per_class: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for cls in HURRICANE_CLASSES:
        pool = [p for p in pairs if p["truth"] == cls]
        rng.shuffle(pool)
        out.extend(pool[:per_class])
    return out


def committed_grid_cells(ctx: EventContext) -> set[str]:
    grid = ctx.event_dir / "evidence" / "bitemporal_h3_r9_grid.geojson"
    data = json.loads(grid.read_text(encoding="utf-8"))
    return {f["properties"]["h3_cell"] for f in data["features"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True, help="extracted final_label_image/ directory")
    ap.add_argument("--pairs-csv", type=Path, required=True, help="Figshare LLM(GPT-4o-mini).csv")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--sample", type=int, default=None, help="pairs PER CLASS to grade (stratified, seeded); default all")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--resolution", type=int, default=9)
    ap.add_argument("--timeout", type=float, default=240.0)
    args = ap.parse_args()

    import h3

    ctx = EventContext(event_id=EVENT_ID, event_dir=args.events_root / EVENT_ID, hazard="hurricane")
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    all_pairs, dropped = load_pairs(args.pairs_csv, args.images)
    chosen = stratified(all_pairs, args.sample, args.seed) if args.sample else all_pairs
    disagreement = sum(1 for p in all_pairs if p["folder_label"] and p["folder_label"] != p["truth"])

    # --- snapshots -----------------------------------------------------------
    counts = {c: sum(1 for p in all_pairs if p["truth"] == c) for c in HURRICANE_CLASSES}
    ctx.write_json(
        "snapshots/registry/BiTemporal_StreetView_Damage_profile.json",
        {
            "schema_version": "yifan-disaster-registry-v1",
            "dataset_name": "BiTemporal_StreetView_Damage",
            "generated_utc": utc_stamp(),
            "event": "Hurricane Milton 2024 (2024-season cumulative)",
            "hazard_type": "hurricane",
            "role": "public pre/post street-view pairs with human perception labels (RAPID Dataset B line)",
            "n_pairs_in_table": len(all_pairs) + sum(dropped.values()),
            "n_pairs_resolved": len(all_pairs),
            "dropped": dropped,
            "label_counts": counts,
            "canonical_label_field": "human_damage_perception",
            "canonical_label_map": HURRICANE_TO_CANONICAL,
            "folder_label_disagreements": disagreement,
            "sources": {"images": HF_URL, "pair_table": f"doi:{FIGSHARE_DOI} LLM(GPT-4o-mini).csv"},
            "licenses": {"images": "CC BY-NC 4.0 (Hugging Face card)", "pair_table": "CC BY 4.0 (Figshare)"},
            "attribution": "Yang, Y. (2025). Hyperlocal disaster damage assessment using bi-temporal street-view imagery and pre-trained vision models. CEUS 121, 102335.",
            "pair_table_file": args.pairs_csv.name,
            "pair_table_sha256": sha256_file(args.pairs_csv),
            "images_local_layout": "pair directories" if index_pair_dirs(args.images) else "no_damage/ + folder_k/ (Hugging Face zip)",
            "images_local_root_name": args.images.name,
        },
        kind="dataset_registry_snapshot", agent="snapshot.registry",
        inputs=[HF_URL, f"doi:{FIGSHARE_DOI}"],
        notes=f"{len(all_pairs)} resolvable pairs; {disagreement} folder/table label disagreements declared",
    )
    snap = ctx.event_dir / "snapshots" / "bitemporal" / "pair_table.json.gz"
    snap.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(snap, "wt", encoding="utf-8") as f:
        json.dump([{k: p[k] for k in ("pair_id", "truth", "folder_label", "lat", "lon")} for p in all_pairs], f)
    ctx.register(Artifact(
        path=snap, kind="source_snapshot_ccby", agent=STAGE, created_utc=utc_stamp(),
        inputs=[f"doi:{FIGSHARE_DOI}"],
        notes="pair ids, coordinates and labels only; the table's workstation paths are dropped. CC BY 4.0, attribution in the registry profile",
    ))
    prompt_path = ctx.event_dir / "snapshots" / "vlm" / "prompt_bitemporal_3class.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(BITEMPORAL_PROMPT, encoding="utf-8")
    prompt_artifact = ctx.register(Artifact(
        path=prompt_path, kind="vlm_prompt", agent=STAGE, created_utc=utc_stamp(),
        inputs=["RAPID Prompt--Damage Recognition Agent, section B"],
        notes="verbatim RAPID pre/post 3-class prompt; sha256 cited by every run record",
    ))

    # --- grading -------------------------------------------------------------
    identity = model_identity()
    run_meta = {"model": identity["model"], "model_digest": identity["digest"],
                "prompt_sha256": sha256_text(BITEMPORAL_PROMPT), "temperature": 0.0, "run_id": audit.run_id,
                "sample_per_class": args.sample, "seed": args.seed if args.sample else None}

    def call(messages, response_format):
        return chat_completion(messages, timeout=args.timeout, response_format=response_format, temperature=0.0)

    pred_path = ctx.event_dir / "evidence" / "vlm_bitemporal_predictions.jsonl"
    existing = {}
    if pred_path.exists():
        for line in pred_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line); existing[r["pair_id"]] = r
    records, n_new = [], 0
    with pred_path.open("a", encoding="utf-8") as out:
        for i, p in enumerate(chosen, 1):
            if p["pair_id"] in existing:
                records.append(existing[p["pair_id"]]); continue
            rec = classify_pair(call, p["pre"], p["post"], p["truth"], latlon=(p["lat"], p["lon"]), pair_id=p["pair_id"])
            rec["folder_label"] = p["folder_label"]
            rec.update(run_meta)
            out.write(record_to_row(rec) + "\n"); out.flush()
            records.append(rec); n_new += 1
            print(f"[{i}/{len(chosen)}] {p['truth']:>8} -> {rec['pred'] or rec['status']:>12}  {rec['latency_s']}s", flush=True)

    summary = summarize(records, HURRICANE_CLASSES)
    cells = committed_grid_cells(ctx)
    in_grid = sum(1 for r in records if h3.latlng_to_cell(r["lat"], r["lon"], args.resolution) in cells)
    fail_closed(audit, [
        check_bounds("unanswered_rate", summary["unanswered_rate"] or 0.0, 0.0, MAX_UNANSWERED_RATE),
        check_bounds("accuracy", summary["accuracy"] if summary["accuracy"] is not None else -1.0, 0.0, 1.0),
        check_bounds("ncse", summary["ncse"] if summary["ncse"] is not None else -1.0, 0.0, 1.0),
        check_bounds("pairs_in_committed_grid", in_grid / len(records) if records else 0.0, MIN_IN_GRID, 1.0),
    ])
    ctx.register(Artifact(
        path=pred_path, kind="vlm_prediction_records", agent=STAGE, created_utc=utc_stamp(),
        inputs=[prompt_artifact.path.name, snap.name],
        notes=f"{len(records)} pair records ({n_new} new this run); coordinates from the pair table; lineage-only",
    ))

    features = aggregate_h3(records, HURRICANE_CLASSES, resolution=args.resolution)
    collection = {
        "type": "FeatureCollection", "crs_declared": "EPSG:4326", "features": features,
        "properties": {
            "h3_resolution": args.resolution, "n_cells": len(features), "n_pairs": len(records),
            "resolution_cap": "tile", "model_derived": True, **run_meta,
            "source": "zero-shot VLM pre/post grading vs human perception labels (Bi-Temporal set), aggregated by pair coordinates",
            "companion_grid": "evidence/bitemporal_h3_r9_grid.geojson",
        },
    }
    fail_closed(audit, [check_crs("EPSG:4326"), check_uncertainty_present(features[0]["properties"])])
    grid_rel = f"evidence/vlm_bitemporal_h3_r{args.resolution}_grid.geojson"
    ctx.write_json(grid_rel, collection, kind="evidence_grid", agent=STAGE, inputs=[pred_path.name],
                   notes=f"{len(features)} cells; per-tile agreement of a zero-shot model with human labels")

    eval_doc = {
        **run_meta, "event_id": EVENT_ID, "dataset": "BiTemporal_StreetView_Damage",
        "generated_utc": utc_stamp(), **summary,
        "n_pairs_available": len(all_pairs), "pairs_in_committed_grid": in_grid, "grid": grid_rel,
        "object_indicator_rate": {
            k: round(sum(1 for r in records if (r.get("objects") or {}).get(k) == 1) / len(records), 4)
            for k in ("debris_pile", "fallen_tree", "flooded_road", "damaged_building", "downed_lines")
        } if records else {},
        "reference": {
            "paper": "RAPID (arXiv 2606.21819) Dataset B, 3-class bi-temporal",
            "reported_accuracy": {"GPT-5.1": 0.591, "GPT-5-mini": 0.503, "Gemini-3-Pro": 0.493},
            "note": "the paper graded 150 pairs of this set with closed models; this run is an open model on a seeded stratified sample, temperature 0",
        },
        "uncertainty": {
            "model_derived": True,
            "sample": f"{args.sample} per class, seed {args.seed}" if args.sample else "all resolvable pairs",
            "single_run": "one pass at temperature 0; quantised local weights",
            "truth_source": "Figshare pair table human_damage_perception; Hugging Face folder labels disagree on "
                            f"{disagreement} of {len(all_pairs)} pairs and are recorded per pair, not used as truth",
            "event_attribution": "2024-season cumulative, not Milton-specific (as the companion grid declares)",
            "object_indicators": "model-reported presence flags with no ground truth here; rates are descriptive only",
            "claim_support": "none — evaluation only; no policy rule authorises claims from these predictions",
        },
    }
    fail_closed(audit, [check_uncertainty_present(eval_doc)])
    ctx.write_json("evidence/vlm_bitemporal_eval.json", eval_doc, kind="vlm_eval_summary", agent=STAGE,
                   inputs=[pred_path.name], notes="accuracy / NCSE / confusion for the run")
    audit.record("stage", STAGE, payload={
        "status": "ok", "n_pairs": summary["n_images"], "n_scored": summary["n_scored"],
        "accuracy": summary["accuracy"], "ncse": summary["ncse"], "unanswered_rate": summary["unanswered_rate"],
        "pairs_in_committed_grid": in_grid, "model": identity["model"], "model_digest": identity["digest"],
    })
    print(json.dumps({k: summary[k] for k in ("n_images", "n_scored", "accuracy", "ncse", "adjacent_error_rate", "unanswered_rate")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
