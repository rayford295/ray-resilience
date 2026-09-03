#!/usr/bin/env python
"""Palisades Fire 2025: zero-shot VLM severity grading, evaluated against LA DINS labels.

Deep-case builder for `events/palisades-2025/`, stage `evidence.vlm_severity`.
Input is the 295-image street-view set from the RAPID repository
(`I-guide/Dataset/SVI_PalisadesFireImages/<class>/*.jpg`, RAPID's Dataset C2,
folder = CAL FIRE DINS damage class). The model is whatever OpenAI-compatible
vision endpoint STEWARD_LLM_BASE_URL points at — local Ollama by default — so
the whole run is keyless and reproducible from a laptop.

What this stage writes, all through the Steward Harness:

  snapshots/registry/SVI_PalisadesFireImages_profile.json  dataset_registry_snapshot (internal)
  evidence/prompt_wildfire_5class.txt                       vlm_prompt (public)
  evidence/vlm_predictions.jsonl                            vlm_prediction_records (lineage: has EXIF coords)
  evidence/vlm_severity_eval.json                           vlm_eval_summary (public)
  evidence/vlm_severity_h3_r9_grid.geojson                  evidence_grid (tile, public) — only if images carry GPS
  dossier/event_record.json                                 event_record (written once)

Fail-closed: the stage aborts if more than 20% of answers are unparseable or
off-schema, if accuracy/NCSE leave [0, 1], or if any product lacks an
`uncertainty` block. Re-running resumes: images whose sha256 already has a
record are skipped, so an interrupted run costs nothing.

The event is NOT in `published_events`: this is an evaluation of a method on a
real, labelled case, and it becomes part of the public surface only by a
policy change that says so.

    python scripts/build_palisades_vlm.py --images ~/Documents/RAPID/I-guide/Dataset/SVI_PalisadesFireImages
    python scripts/build_palisades_vlm.py --images ... --limit 10     # smoke run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.agents.base import Artifact, EventContext, utc_stamp  # noqa: E402
from geosteward.deepcase.vlm_severity import (  # noqa: E402
    WILDFIRE_CLASSES,
    WILDFIRE_PROMPT,
    WILDFIRE_TO_CANONICAL,
    aggregate_h3,
    classify_image,
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

EVENT_ID = "palisades-2025"
STAGE = "evidence.vlm_severity"
MAX_UNANSWERED_RATE = 0.20
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def fail_closed(audit: AuditLog, results) -> None:
    for r in results:
        audit.record("check", STAGE, payload=r.as_row())
        if not r.passed:
            raise RuntimeError(f"[{STAGE}] outcome check failed: {r.check}: {r.detail}")


def model_identity() -> dict[str, str | None]:
    """Model name from the environment plus, for a local Ollama, its digest —
    the name alone does not pin weights, the digest does."""
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


def list_images(images_root: Path) -> list[tuple[Path, str]]:
    out = []
    for cls in WILDFIRE_CLASSES:
        d = images_root / cls
        if not d.is_dir():
            raise FileNotFoundError(f"expected class folder {d}")
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in IMAGE_SUFFIXES:
                out.append((p, cls))
    return out


def stage_registry_snapshot(ctx: EventContext, images: list[tuple[Path, str]], images_root: Path) -> None:
    counts = {c: 0 for c in WILDFIRE_CLASSES}
    total_bytes = 0
    for p, cls in images:
        counts[cls] += 1
        total_bytes += p.stat().st_size
    profile = {
        "schema_version": "yifan-disaster-registry-v1",
        "dataset_name": "SVI_PalisadesFireImages",
        "generated_utc": utc_stamp(),
        "event": "Palisades Fire 2025",
        "hazard_type": "wildfire",
        "role": "labelled post-event street-view set for zero-shot severity evaluation (RAPID Dataset C2)",
        "n_samples": len(images),
        "label_counts": counts,
        "canonical_label_field": "dins_folder_label",
        "canonical_label_map": WILDFIRE_TO_CANONICAL,
        "label_scheme": "CAL FIRE DINS percent structural loss, 5 classes (folder names)",
        "source": "github.com/rayford295/RAPID I-guide/Dataset/SVI_PalisadesFireImages (LA DINS 2025)",
        "files": {"n_image_files": len(images), "total_bytes": total_bytes},
        "checksums": {"note": "per-image sha256 recorded in evidence/vlm_predictions.jsonl"},
        "provenance_note": (
            "Images are per-structure street views whose truth label is the folder they were "
            "filed under by the RAPID authors from DINS records; no structure IDs are carried."
        ),
    }
    ctx.write_json(
        "snapshots/registry/SVI_PalisadesFireImages_profile.json",
        profile,
        kind="dataset_registry_snapshot",
        agent="snapshot.registry",
        inputs=[str(images_root)],
        notes=f"{len(images)} labelled images, 5 DINS classes",
    )


def stage_prompt_snapshot(ctx: EventContext) -> Artifact:
    # Under evidence/, not snapshots/: the prompt ships (it is RAPID's published
    # text and every record cites its sha256), and nothing under snapshots/ ever
    # does -- that is a structural rule of the distribution plane, not a per-file one.
    path = ctx.event_dir / "evidence" / "prompt_wildfire_5class.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(WILDFIRE_PROMPT, encoding="utf-8")
    return ctx.register(
        Artifact(
            path=path, kind="vlm_prompt", agent=STAGE, created_utc=utc_stamp(),
            inputs=["RAPID Prompt--Damage Recognition Agent, section C"],
            notes="verbatim RAPID wildfire 5-class prompt; sha256 is cited by every run record",
        )
    )


def stage_event_record(ctx: EventContext, audit: AuditLog, bbox: dict | None) -> None:
    path = ctx.event_dir / "dossier" / "event_record.json"
    if path.exists():
        return
    stage = "dossier.event_record"
    record = {
        "event_id": EVENT_ID,
        "name": "Palisades Fire",
        "hazard": "wildfire",
        "start_date": "2025-01-07",
        "location": "Pacific Palisades, Los Angeles, CA",
        **({"aoi_bbox_wgs84": bbox} if bbox else {}),
        "evidence_tier": 3,
        "model_derived": True,
        "data_sources": [
            "SVI_PalisadesFireImages labelled street-view set (RAPID Dataset C2; labels from CAL FIRE DINS)",
        ],
        "declared_unknowns": [
            "all severity values are zero-shot vision-model predictions evaluated against dataset labels: evaluation only, no damage claim is supported from them",
            "no exposure layer, no SVI join, no population layer: no exposure or vulnerability claims",
            "truth labels come from the folder each image was filed under, not from per-structure DINS records: no parcel-level claims",
            "images without EXIF GPS are absent from the tile grid; the grid covers photographed structures, not the fire perimeter",
        ],
        "uncertainty": {
            "label_crosswalk": "DINS percent-loss classes mapped to the canonical scale as in snapshots/registry profile",
        },
    }
    ctx.write_json(
        "dossier/event_record.json", record, kind="event_record", agent=stage,
        inputs=["snapshots/registry"], notes="Palisades Fire 2025 evaluation-case dossier",
    )
    audit.record("stage", stage, payload={"status": "ok"})


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["image_sha256"]: r for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True, help="root with the five DINS class folders")
    ap.add_argument("--events-root", type=Path, default=Path("events"))
    ap.add_argument("--limit", type=int, default=None, help="only the first N images (smoke run)")
    ap.add_argument("--resolution", type=int, default=9)
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    ctx = EventContext(event_id=EVENT_ID, event_dir=args.events_root / EVENT_ID, hazard="wildfire")
    audit = AuditLog(ctx.event_dir / "audit_log.jsonl")
    images = list_images(args.images)
    if args.limit:
        # Spread the smoke sample across classes rather than taking one folder.
        per = max(1, args.limit // len(WILDFIRE_CLASSES))
        picked, seen = [], {c: 0 for c in WILDFIRE_CLASSES}
        for p, c in images:
            if seen[c] < per:
                picked.append((p, c)); seen[c] += 1
        images = picked[: args.limit]

    stage_registry_snapshot(ctx, images, args.images)
    prompt_artifact = stage_prompt_snapshot(ctx)
    identity = model_identity()

    def call(messages, response_format):
        return chat_completion(messages, timeout=args.timeout, response_format=response_format, temperature=0.0)

    pred_path = ctx.event_dir / "evidence" / "vlm_predictions.jsonl"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing(pred_path)
    run_meta = {
        "model": identity["model"], "model_digest": identity["digest"],
        "prompt_sha256": sha256_text(WILDFIRE_PROMPT), "temperature": 0.0, "run_id": audit.run_id,
    }
    records: list[dict] = []
    n_new = 0
    with pred_path.open("a", encoding="utf-8") as out:
        for i, (p, cls) in enumerate(images, 1):
            digest = sha256_file(p)
            if digest in existing:
                records.append(existing[digest])
                continue
            rec = classify_image(call, p, cls, relative_to=args.images)
            rec.update(run_meta)
            out.write(record_to_row(rec) + "\n"); out.flush()
            records.append(rec); n_new += 1
            print(f"[{i}/{len(images)}] {cls:>20} -> {rec['pred'] or rec['status']:>20}  {rec['latency_s']}s", flush=True)

    summary = summarize(records)
    fail_closed(audit, [
        check_bounds("unanswered_rate", summary["unanswered_rate"] or 0.0, 0.0, MAX_UNANSWERED_RATE),
        check_bounds("accuracy", summary["accuracy"] if summary["accuracy"] is not None else -1.0, 0.0, 1.0),
        check_bounds("ncse", summary["ncse"] if summary["ncse"] is not None else -1.0, 0.0, 1.0),
    ])

    ctx.register(Artifact(
        path=pred_path, kind="vlm_prediction_records", agent=STAGE, created_utc=utc_stamp(),
        inputs=[prompt_artifact.path.name, "snapshots/registry/SVI_PalisadesFireImages_profile.json"],
        notes=f"{len(records)} per-image records ({n_new} new this run); parcel-resolution (EXIF coords), lineage-only",
    ))

    located = [r for r in records if r.get("lat") is not None]
    bbox = None
    grid_rel = None
    if located:
        features = aggregate_h3(records, resolution=args.resolution)
        lats = [r["lat"] for r in located]; lons = [r["lon"] for r in located]
        bbox = {"min_lat": round(min(lats), 3), "max_lat": round(max(lats), 3),
                "min_lon": round(min(lons), 3), "max_lon": round(max(lons), 3)}
        collection = {
            "type": "FeatureCollection", "crs_declared": "EPSG:4326", "features": features,
            "properties": {
                "h3_resolution": args.resolution, "n_cells": len(features),
                "n_images_located": len(located), "n_images_total": len(records),
                "resolution_cap": "tile", "model_derived": True, **run_meta,
                "source": "zero-shot VLM severity vs DINS folder labels, aggregated by image EXIF GPS",
            },
        }
        fail_closed(audit, [check_crs("EPSG:4326"), check_uncertainty_present(features[0]["properties"])])
        grid_rel = f"evidence/vlm_severity_h3_r{args.resolution}_grid.geojson"
        ctx.write_json(grid_rel, collection, kind="evidence_grid", agent=STAGE,
                       inputs=[pred_path.name],
                       notes=f"{len(features)} cells from {len(located)} GPS-tagged images; agreement per tile")

    eval_doc = {
        **run_meta, "event_id": EVENT_ID, "dataset": "SVI_PalisadesFireImages",
        "generated_utc": utc_stamp(), **summary,
        "n_images_with_gps": len(located), "grid": grid_rel,
        "reference": {
            "paper": "RAPID (arXiv 2606.21819) Dataset C2, 5-class wildfire",
            "reported_accuracy": {"GPT-5-mini": 0.573, "GPT-5.1": 0.570, "Gemini-3-Pro": 0.442},
            "note": "reported numbers are the paper's closed-model results on the same 295 images; this run is an open model, zero-shot, temperature 0",
        },
        "uncertainty": {
            "model_derived": True,
            "single_run": "one pass at temperature 0; quantised local weights; no repeated sampling",
            "truth_source": "dataset folder labels (DINS-derived), not per-structure field records",
            "claim_support": "none — evaluation only; no policy rule authorises claims from these predictions",
        },
    }
    fail_closed(audit, [check_uncertainty_present(eval_doc)])
    ctx.write_json("evidence/vlm_severity_eval.json", eval_doc, kind="vlm_eval_summary", agent=STAGE,
                   inputs=[pred_path.name], notes="accuracy / NCSE / confusion for the run")
    audit.record("stage", STAGE, payload={
        "status": "ok", "n_images": summary["n_images"], "n_scored": summary["n_scored"],
        "accuracy": summary["accuracy"], "ncse": summary["ncse"],
        "unanswered_rate": summary["unanswered_rate"], "model": identity["model"], "model_digest": identity["digest"],
    })
    stage_event_record(ctx, audit, bbox)
    print(json.dumps({k: summary[k] for k in ("n_images", "n_scored", "accuracy", "ncse", "adjacent_error_rate", "unanswered_rate")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
