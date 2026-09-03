#!/usr/bin/env python
"""Eaton Fire 2025: zero-shot VLM severity grading of the matched cross-view set.

Stage `evidence.vlm_crossview` for `events/eaton-2025/`. Input is the
EATON_wildfire_mapillary_matched set (2,244 post-event field images, each with
a pre-event Mapillary counterpart, a 3-class repairability label derived from
CAL FIRE DINS, a `match_quality` of `good` or `usable`, and the post-event
point's coordinates). This is the set that `evidence.crossview_coverage` only
counted; here the post-event image of each sample is graded.

The prompt is RAPID's wildfire Prompt C, verbatim and unchanged — the same
`prompt_sha256` as `events/palisades-2025/`, so the two evaluations differ in
data and truth scale, not in wording. Prompt C is a single-image prompt, so
the model sees the post-event field image only; the pre-event Mapillary image
is not shown (declared, not hidden). Its five DINS classes are collapsed onto
the dataset's three repairability classes by DINS semantics
(`vlm_severity.DINS5_TO_REPAIRABILITY3`): both the 5-class prediction and the
collapsed one are in every record, and the evaluation is on the collapsed
scale because that is the scale the truth is on.

Writes, through the Steward Harness:

  evidence/prompt_wildfire_5class.txt                 vlm_prompt (public)
  evidence/vlm_crossview_predictions.jsonl            vlm_prediction_records (lineage: sample coordinates)
  evidence/vlm_crossview_eval.json                    vlm_eval_summary (public)
  evidence/vlm_crossview_h3_r9_grid.geojson           evidence_grid (tile, public, model_derived)

The dataset registry snapshot already committed by `evidence.crossview_coverage`
(`snapshots/registry/EATON_wildfire_mapillary_matched_profile.json`) is the
input, not rewritten. The event dossier is not touched.

Fail-closed on: >20% off-schema answers; accuracy/NCSE outside [0,1]; fewer
than 95% of graded samples falling inside the committed
`evidence/crossview_h3_r9_coverage.geojson` cells (the sample must be about
the ground the event already describes). Resumable by image sha256. A
stratified `--sample N` grades N samples per class, seeded; the minority class
(`damaged_repairable`, n=30) is always fully included when N >= 30.

    python scripts/build_eaton_vlm.py --dataset <root>/EATON_wildfire_mapillary_matched --sample 100
    python scripts/build_eaton_vlm.py --dataset ... --limit 6            # smoke run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp  # noqa: E402
from geosteward.deepcase.vlm_severity import (  # noqa: E402
    DINS5_TO_REPAIRABILITY3,
    REPAIRABILITY_CLASSES,
    REPAIRABILITY_TO_CANONICAL,
    WILDFIRE_CLASSES,
    WILDFIRE_PROMPT,
    aggregate_h3,
    classify_image,
    collapse_wildfire_prediction,
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

EVENT_ID = "eaton-2025"
STAGE = "evidence.vlm_crossview"
DATASET = "EATON_wildfire_mapillary_matched"
MAX_UNANSWERED_RATE = 0.20
MIN_IN_GRID = 0.95
QUALITY_ALLOWED = ("good", "usable")
VIEW_COLUMN = {"post_field": "post_event_field_path", "post_remote": "post_event_remote_path"}
REGISTRY_SNAPSHOT = f"snapshots/registry/{DATASET}_profile.json"
COMPANION_GRID = "evidence/crossview_h3_r9_coverage.geojson"


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


def load_samples(dataset_root: Path, view: str, quality: tuple[str, ...]) -> tuple[list[dict], dict]:
    """Manifest rows that pass the quality gate, with the graded image resolved.
    The DINS record id (`dependency_group_id`) is parcel-level lineage the
    dataset already holds; it is not copied into anything this stage writes."""
    column = VIEW_COLUMN[view]
    samples, dropped = [], {"quality_gate": 0, "bad_label": 0, "missing_image": 0}
    with (dataset_root / "manifest.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["match_quality"] not in quality:
                dropped["quality_gate"] += 1; continue
            if row["label_name"] not in REPAIRABILITY_CLASSES:
                dropped["bad_label"] += 1; continue
            image = dataset_root / row[column]
            if not image.is_file():
                dropped["missing_image"] += 1; continue
            samples.append({
                "sample_id": row["sample_id"], "split": row["split"], "truth": row["label_name"],
                "match_quality": row["match_quality"], "image": image,
                "lat": round(float(row["post_latitude"]), 6), "lon": round(float(row["post_longitude"]), 6),
            })
    return samples, dropped


def stratified(samples: list[dict], per_class: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for cls in REPAIRABILITY_CLASSES:
        pool = [s for s in samples if s["truth"] == cls]
        rng.shuffle(pool)
        out.extend(pool[:per_class])
    return out


def committed_grid_cells(ctx: EventContext) -> set[str]:
    data = json.loads((ctx.event_dir / COMPANION_GRID).read_text(encoding="utf-8"))
    return {f["properties"]["h3_cell"] for f in data["features"]}


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["image_sha256"]: r for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True, help=f"{DATASET} root (holds manifest.csv and images/)")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--view", choices=sorted(VIEW_COLUMN), default="post_field",
                    help="which post-event image is graded (default: the street-level field image)")
    ap.add_argument("--quality", default=",".join(QUALITY_ALLOWED),
                    help="comma list of match_quality values admitted (default: good,usable — the dataset's own gate)")
    ap.add_argument("--sample", type=int, default=None, help="samples PER CLASS to grade (stratified, seeded); default all")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--limit", type=int, default=None, help="only the first N of the chosen samples (smoke run)")
    ap.add_argument("--resolution", type=int, default=9)
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    import h3

    quality = tuple(q.strip() for q in args.quality.split(",") if q.strip())
    ctx = EventContext(event_id=EVENT_ID, event_dir=args.events_root / EVENT_ID, hazard="wildfire")
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    registry = ctx.event_dir / REGISTRY_SNAPSHOT
    if not registry.is_file():
        raise FileNotFoundError(f"{registry} is missing: run the crossview_coverage stage first")

    all_samples, dropped = load_samples(args.dataset, args.view, quality)
    chosen = stratified(all_samples, args.sample, args.seed) if args.sample else list(all_samples)
    if args.limit:
        per = max(1, args.limit // len(REPAIRABILITY_CLASSES))
        picked, seen = [], {c: 0 for c in REPAIRABILITY_CLASSES}
        for s in chosen:
            if seen[s["truth"]] < per:
                picked.append(s); seen[s["truth"]] += 1
        chosen = picked[: args.limit]

    # --- prompt snapshot (same bytes, same sha256, as the Palisades run) ---
    # evidence/, not snapshots/: the prompt is public, and nothing under snapshots/ ships.
    prompt_path = ctx.event_dir / "evidence" / "prompt_wildfire_5class.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(WILDFIRE_PROMPT, encoding="utf-8")
    prompt_artifact = ctx.register(Artifact(
        path=prompt_path, kind="vlm_prompt", agent=STAGE, created_utc=utc_stamp(),
        inputs=["RAPID Prompt--Damage Recognition Agent, section C"],
        notes="verbatim RAPID wildfire 5-class prompt; sha256 cited by every run record; collapsed to 3 classes at evaluation",
    ))

    # --- grading ---------------------------------------------------------------
    identity = model_identity()
    run_meta = {
        "model": identity["model"], "model_digest": identity["digest"],
        "prompt_sha256": sha256_text(WILDFIRE_PROMPT), "temperature": 0.0, "run_id": audit.run_id,
        "view": args.view, "quality_gate": list(quality),
        "sample_per_class": args.sample, "seed": args.seed if args.sample else None,
    }

    def call(messages, response_format):
        return chat_completion(messages, timeout=args.timeout, response_format=response_format, temperature=0.0)

    pred_path = ctx.event_dir / "evidence" / "vlm_crossview_predictions.jsonl"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing(pred_path)
    records, n_new = [], 0
    with pred_path.open("a", encoding="utf-8") as out:
        for i, s in enumerate(chosen, 1):
            digest = sha256_file(s["image"])
            if digest in existing:
                records.append(existing[digest]); continue
            rec = classify_image(call, s["image"], s["truth"], relative_to=args.dataset)
            # Prompt C answers on the 5-class DINS scale; the truth is 3-class.
            # Keep both: the raw prediction is what the model said, the
            # collapsed one is what it is scored on.
            rec["pred_dins5"] = rec["pred"]
            rec["pred"] = collapse_wildfire_prediction(rec["pred"]) if rec["status"] == "ok" else None
            # Location is the dataset's post-event point, not EXIF (field
            # images carry none); recorded as given.
            rec["lat"], rec["lon"] = s["lat"], s["lon"]
            rec["location_source"] = "manifest post_latitude/post_longitude"
            rec.update({k: s[k] for k in ("sample_id", "split", "match_quality")})
            rec.update(run_meta)
            out.write(record_to_row(rec) + "\n"); out.flush()
            records.append(rec); n_new += 1
            print(f"[{i}/{len(chosen)}] {s['truth']:>20} -> {rec['pred_dins5'] or rec['status']:>20}  {rec['latency_s']}s", flush=True)

    summary = summarize(records, REPAIRABILITY_CLASSES)
    cells = committed_grid_cells(ctx)
    in_grid = sum(1 for r in records if h3.latlng_to_cell(r["lat"], r["lon"], args.resolution) in cells)
    fail_closed(audit, [
        check_bounds("unanswered_rate", summary["unanswered_rate"] or 0.0, 0.0, MAX_UNANSWERED_RATE),
        check_bounds("accuracy", summary["accuracy"] if summary["accuracy"] is not None else -1.0, 0.0, 1.0),
        check_bounds("ncse", summary["ncse"] if summary["ncse"] is not None else -1.0, 0.0, 1.0),
        check_bounds("samples_in_committed_grid", in_grid / len(records) if records else 0.0, MIN_IN_GRID, 1.0),
    ])
    ctx.register(Artifact(
        path=pred_path, kind="vlm_prediction_records", agent=STAGE, created_utc=utc_stamp(),
        inputs=[prompt_artifact.path.name, REGISTRY_SNAPSHOT],
        notes=f"{len(records)} per-sample records ({n_new} new this run); post-event point coordinates; lineage-only",
    ))

    features = aggregate_h3(
        records, REPAIRABILITY_CLASSES, resolution=args.resolution,
        location_source="dataset manifest post-event point (post_latitude/post_longitude), not EXIF",
    )
    collection = {
        "type": "FeatureCollection", "crs_declared": "EPSG:4326", "features": features,
        "properties": {
            "h3_resolution": args.resolution, "n_cells": len(features), "n_samples": len(records),
            "resolution_cap": "tile", "model_derived": True, **run_meta,
            "source": f"zero-shot VLM grading of {args.view} images vs {DATASET} label_name, aggregated by post-event point",
            "companion_grid": COMPANION_GRID,
        },
    }
    fail_closed(audit, [check_crs("EPSG:4326"), check_uncertainty_present(features[0]["properties"])])
    grid_rel = f"evidence/vlm_crossview_h3_r{args.resolution}_grid.geojson"
    ctx.write_json(grid_rel, collection, kind="evidence_grid", agent=STAGE, inputs=[pred_path.name, COMPANION_GRID],
                   notes=f"{len(features)} cells; per-tile agreement of a zero-shot model with the matched set's labels")

    pred5_hist = {c: sum(1 for r in records if r.get("pred_dins5") == c) for c in WILDFIRE_CLASSES}
    eval_doc = {
        **run_meta, "event_id": EVENT_ID, "dataset": DATASET,
        "generated_utc": utc_stamp(), **summary,
        "n_samples_available": len(all_samples), "dropped_at_load": dropped,
        "samples_in_committed_grid": in_grid, "grid": grid_rel,
        "prediction_histogram_dins5": pred5_hist,
        "collapse_map_dins5_to_repairability3": DINS5_TO_REPAIRABILITY3,
        "canonical_label_map": REPAIRABILITY_TO_CANONICAL,
        "reference": {
            "same_prompt_same_model": "events/palisades-2025/evidence/vlm_severity_eval.json (5-class, RAPID Dataset C2)",
            "note": "no published closed-model number exists for this set; the 3-class task is easier than the 5-class one by construction, so the two accuracies are not comparable as numbers",
        },
        "uncertainty": {
            "model_derived": True,
            "sample": f"{args.sample} per class, seed {args.seed}" if args.sample else "all samples passing the quality gate",
            "single_run": "one pass at temperature 0; quantised local weights",
            "view": f"{args.view} image only; the pre-event Mapillary counterpart is not shown to the model (Prompt C is single-image)",
            "truth_source": "dataset label_name (3-class repairability derived from CAL FIRE DINS by the matched set's protocol); the prompt's 5 DINS classes are collapsed onto it before scoring",
            "minority_class": "damaged_repairable has n=30 in the whole set; its recall is reported, no rate claim is supported from it",
            "match_quality": f"samples admitted: {', '.join(quality)}; the dataset's own gate, recorded per record",
            "claim_support": "none — evaluation only; no policy rule authorises claims from these predictions",
        },
    }
    fail_closed(audit, [check_uncertainty_present(eval_doc)])
    ctx.write_json("evidence/vlm_crossview_eval.json", eval_doc, kind="vlm_eval_summary", agent=STAGE,
                   inputs=[pred_path.name], notes="accuracy / NCSE / confusion for the run, on the collapsed 3-class scale")
    audit.record("stage", STAGE, payload={
        "status": "ok", "n_samples": summary["n_images"], "n_scored": summary["n_scored"],
        "accuracy": summary["accuracy"], "ncse": summary["ncse"], "unanswered_rate": summary["unanswered_rate"],
        "samples_in_committed_grid": in_grid, "model": identity["model"], "model_digest": identity["digest"],
    })
    print(json.dumps({k: summary[k] for k in ("n_images", "n_scored", "accuracy", "ncse", "adjacent_error_rate", "unanswered_rate")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
