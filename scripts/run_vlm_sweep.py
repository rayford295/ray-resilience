#!/usr/bin/env python
"""Run the three zero-shot VLM builders for several served models, one model
at a time, each run tagged with the model's slug so the outputs sit next to
the reference run instead of overwriting it; then regenerate the comparison.

For every model (in the order given) and every case:

  palisades  scripts/build_palisades_vlm.py        --images <root>  --run-tag auto
  milton     scripts/build_milton_vlm_bitemporal.py --images <root> --pairs-csv <csv> --sample N --run-tag auto
  eaton      scripts/build_eaton_vlm.py            --dataset <root> --sample N --run-tag auto

Each builder is a subprocess with `STEWARD_LLM_MODEL=<model>`; its stdout goes
to `<log-dir>/<slug>__<case>.log`. After each run the driver asks the Ollama
server how the model was placed (`/api/ps`: total size, size in VRAM,
context length) and records that with the elapsed time in
`<log-dir>/sweep_summary.json` — the "does it fit the GPU" answer lives next
to the accuracy, because a model spilled to CPU is a different run. A model
that is not served is skipped and recorded, never pulled from here. A failed
case is recorded and the sweep continues with the next one; the builders'
own fail-closed checks decide what counts as failed. Every case is
resumable (the builders skip already-graded images by sha256 / pair id), so
re-running the sweep after an interruption finishes the remainder.

With `--commit-push`, each model's finished cases are committed and pushed as
soon as its last case ends (allowlist and comparison page regenerated first),
so a sweep that dies overnight has already published every completed model.

    python scripts/run_vlm_sweep.py --models gemma3:27b qwen3-vl:32b \\
        --palisades-images .../SVI_PalisadesFireImages \\
        --milton-images .../Bi-temporal_hurricane --milton-pairs-csv .../Location.csv \\
        --eaton-dataset .../EATON_wildfire_mapillary_matched
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geosteward.deepcase.vlm_severity import model_slug, tagged_path  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CASES = ("palisades", "milton", "eaton")
EVAL_FILE = {
    "palisades": "events/palisades-2025/evidence/vlm_severity_eval.json",
    "milton": "events/milton-2024/evidence/vlm_bitemporal_eval.json",
    "eaton": "events/eaton-2025/evidence/vlm_crossview_eval.json",
}


def ollama_root(base_url: str) -> str:
    return base_url.rstrip("/").removesuffix("/v1")


def served_models(base_url: str) -> dict[str, str | None]:
    """name -> digest for every model the server has on disk; {} if unreachable."""
    try:
        with urllib.request.urlopen(f"{ollama_root(base_url)}/api/tags", timeout=5) as resp:
            return {m.get("name") or m.get("model"): m.get("digest") for m in json.load(resp).get("models", [])}
    except Exception:
        return {}


def placement(base_url: str, model: str) -> dict | None:
    """How the server holds `model` right now: bytes total / in VRAM, context.
    None when it is not loaded (already evicted) or the server is unreachable."""
    try:
        with urllib.request.urlopen(f"{ollama_root(base_url)}/api/ps", timeout=5) as resp:
            for m in json.load(resp).get("models", []):
                if m.get("name") == model or m.get("model") == model:
                    size, vram = m.get("size") or 0, m.get("size_vram") or 0
                    return {"size_bytes": size, "size_vram_bytes": vram,
                            "gpu_fraction": round(vram / size, 3) if size else None,
                            "context_length": m.get("context_length"),
                            "quantization": ((m.get("details") or {}).get("quantization_level")),
                            "parameter_size": ((m.get("details") or {}).get("parameter_size"))}
    except Exception:
        return None
    return None


def unload(base_url: str, model: str) -> None:
    body = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
    req = urllib.request.Request(f"{ollama_root(base_url)}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def builder_command(case: str, args: argparse.Namespace) -> list[str] | None:
    py = sys.executable
    if case == "palisades":
        if not args.palisades_images:
            return None
        return [py, "scripts/build_palisades_vlm.py", "--images", str(args.palisades_images), "--run-tag", "auto"]
    if case == "milton":
        if not (args.milton_images and args.milton_pairs_csv):
            return None
        cmd = [py, "scripts/build_milton_vlm_bitemporal.py", "--images", str(args.milton_images),
               "--pairs-csv", str(args.milton_pairs_csv), "--seed", str(args.seed), "--run-tag", "auto"]
        if args.milton_sample:
            cmd += ["--sample", str(args.milton_sample)]
        return cmd
    if case == "eaton":
        if not args.eaton_dataset:
            return None
        cmd = [py, "scripts/build_eaton_vlm.py", "--dataset", str(args.eaton_dataset), "--seed", str(args.seed), "--run-tag", "auto"]
        if args.eaton_sample:
            cmd += ["--sample", str(args.eaton_sample)]
        return cmd
    raise ValueError(case)


def run_case(model: str, case: str, cmd: list[str], base_url: str, log_dir: Path, timeout_s: float) -> dict:
    slug = model_slug(model)
    log = log_dir / f"{slug}__{case}.log"
    env = {**os.environ, "STEWARD_LLM_MODEL": model, "STEWARD_LLM_BASE_URL": base_url, "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n=== {time.strftime('%Y-%m-%dT%H:%M:%S')} {model} {case}\n$ {' '.join(cmd)}\n")
        fh.flush()
        try:
            proc = subprocess.run(cmd, cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout_s)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = -1
            fh.write(f"\n!!! timeout after {timeout_s}s\n")
    elapsed = round(time.time() - t0, 1)
    where = placement(base_url, model)  # read before the next model evicts it
    eval_path = REPO / tagged_path(EVAL_FILE[case], slug)
    summary = None
    if eval_path.is_file():
        d = json.loads(eval_path.read_text(encoding="utf-8"))
        summary = {k: d.get(k) for k in ("n_images", "n_scored", "unanswered_rate", "accuracy", "ncse", "adjacent_error_rate", "run_id")}
    return {"model": model, "slug": slug, "case": case, "returncode": rc, "elapsed_s": elapsed,
            "status": "ok" if rc == 0 else ("timeout" if rc == -1 else "failed"),
            "placement": where, "eval": summary, "log": log.as_posix(), "eval_file": eval_path.relative_to(REPO).as_posix()}


COMMIT_PATHS = ("events", "app/public/publication_allowlist.json",
                "docs/vlm_model_comparison.md", "docs/vlm_model_comparison.json")


def git(*argv: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=check)


def commit_model(model: str, model_results: list[dict]) -> dict:
    """Commit one model's finished cases and push. Runs after the model's last
    case, so no partial file of a case still running can be staged (the cases
    are sequential and the next model has not started). Regenerates the
    publication allowlist first — the tagged prediction files are new paths
    the policy has to classify, and CI's `plan --check` fails on any file the
    committed allowlist does not mention — then the comparison page. A
    regeneration or push failure is recorded, never raised: the sweep goes on
    and the next model's commit carries the backlog."""
    py = sys.executable
    plan_rc = subprocess.run([py, "scripts/publication_boundary.py", "plan"], cwd=REPO,
                             capture_output=True, text=True, encoding="utf-8", errors="replace").returncode
    subprocess.run([py, "scripts/compare_vlm_models.py", "--out", "docs/vlm_model_comparison.md",
                    "--json", "docs/vlm_model_comparison.json"], cwd=REPO, capture_output=True)
    check_rc = subprocess.run([py, "scripts/publication_boundary.py", "plan", "--check"], cwd=REPO,
                              capture_output=True, text=True, encoding="utf-8", errors="replace").returncode
    git("add", "-A", "--", *COMMIT_PATHS)
    if git("diff", "--cached", "--quiet").returncode == 0:
        return {"status": "nothing_to_commit", "plan_rc": plan_rc, "check_rc": check_rc}

    lines = [f"evidence: {model} zero-shot VLM runs (tagged {model_slug(model)}); allowlist and comparison regenerated", ""]
    for r in model_results:
        ev = r.get("eval") or {}
        pl = r.get("placement") or {}
        gpu = pl.get("gpu_fraction")
        if r["status"] == "ok" and ev:
            lines.append(f"- {r['case']}: n_scored {ev.get('n_scored')}/{ev.get('n_images')}, accuracy {ev.get('accuracy')}, "
                         f"NCSE {ev.get('ncse')}, adjacent-error {ev.get('adjacent_error_rate')}, unanswered {ev.get('unanswered_rate')}; "
                         f"run {ev.get('run_id')}; {r.get('elapsed_s')} s")
        elif r["status"] == "skipped_done":
            lines.append(f"- {r['case']}: already graded before this sweep (tagged eval present)")
        else:
            lines.append(f"- {r['case']}: {r['status']} (builder exit {r.get('returncode')}); see the driver log, nothing "
                         f"from this case is claimed")
        if gpu is not None:
            lines.append(f"  placement: {pl.get('size_vram_bytes', 0) / 1e9:.1f} of {pl.get('size_bytes', 0) / 1e9:.1f} GB in VRAM "
                         f"({gpu:.0%}), context {pl.get('context_length')}, {pl.get('quantization')}")
    lines += ["", "Produced by scripts/run_vlm_sweep.py --commit-push, one commit per model as its three cases finish.",
              f"publication_boundary plan --check exit {check_rc}.", "",
              "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"]
    msg = Path(os.environ.get("TEMP", ".")) / f"vlm_sweep_commit_{model_slug(model)}.txt"
    msg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    c = git("commit", "-F", str(msg))
    if c.returncode != 0:
        return {"status": "commit_failed", "detail": (c.stderr or c.stdout)[-500:], "check_rc": check_rc}
    sha = git("rev-parse", "--short", "HEAD").stdout.strip()
    p = git("push", "origin", "HEAD")
    return {"status": "pushed" if p.returncode == 0 else "push_failed", "commit": sha, "check_rc": check_rc,
            "detail": None if p.returncode == 0 else (p.stderr or p.stdout)[-500:]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True, help="served Ollama model names, run in this order")
    ap.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    ap.add_argument("--palisades-images", type=Path, default=None)
    ap.add_argument("--milton-images", type=Path, default=None)
    ap.add_argument("--milton-pairs-csv", type=Path, default=None)
    ap.add_argument("--milton-sample", type=int, default=100, help="pairs per class (the reference run used 100)")
    ap.add_argument("--eaton-dataset", type=Path, default=None)
    ap.add_argument("--eaton-sample", type=int, default=300, help="samples per class (the reference run used 300)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--base-url", default=os.environ.get("STEWARD_LLM_BASE_URL", "http://localhost:11434/v1"))
    ap.add_argument("--log-dir", type=Path, default=Path(os.environ.get("TEMP", ".")) / "vlm_sweep")
    ap.add_argument("--case-timeout", type=float, default=6 * 3600, help="seconds per (model, case)")
    ap.add_argument("--skip-done", action="store_true", help="skip a (model, case) whose tagged eval file already exists")
    ap.add_argument("--no-unload", action="store_true", help="leave the last model resident after each model's cases")
    ap.add_argument("--no-report", action="store_true", help="do not regenerate docs/vlm_model_comparison.md at the end")
    ap.add_argument("--commit-push", action="store_true",
                    help="after each model's cases: regenerate the allowlist and comparison, commit that model's tagged outputs, push")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    args.log_dir.mkdir(parents=True, exist_ok=True)
    served = served_models(args.base_url)
    plan, results = [], []
    for model in args.models:
        for case in args.cases:
            cmd = builder_command(case, args)
            if cmd is None:
                continue
            plan.append((model, case, cmd))
    for model, case, cmd in plan:
        print(f"[plan] {model:>24} {case:<10} {'served' if model in served else 'NOT SERVED'}")
    if args.dry_run:
        return 0

    summary_path = args.log_dir / "sweep_summary.json"
    started = time.strftime("%Y-%m-%dT%H:%M:%S")

    def checkpoint(finished: bool = False) -> None:
        body = {"started": started, "base_url": args.base_url, "results": results}
        if finished:
            body["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        summary_path.write_text(json.dumps(body, indent=1), encoding="utf-8")

    current = None
    for model in args.models:
        model_results = []
        for m, case, cmd in plan:
            if m != model:
                continue
            if model not in served:
                r = {"model": model, "slug": model_slug(model), "case": case, "status": "not_served", "eval": None}
                results.append(r)
                continue
            if args.skip_done and (REPO / tagged_path(EVAL_FILE[case], model_slug(model))).is_file():
                r = {"model": model, "slug": model_slug(model), "case": case, "status": "skipped_done", "eval": None}
                results.append(r)
                model_results.append(r)
                continue
            if current and current != model and not args.no_unload:
                unload(args.base_url, current)
            current = model
            print(f"[run ] {model} {case} …", flush=True)
            r = run_case(model, case, cmd, args.base_url, args.log_dir, args.case_timeout)
            results.append(r)
            model_results.append(r)
            gpu = r["placement"] and r["placement"].get("gpu_fraction")
            ev = r["eval"] or {}
            print(f"[done] {model} {case}: {r['status']} in {r['elapsed_s']}s; "
                  f"GPU {gpu if gpu is not None else '?'}; acc {ev.get('accuracy')} NCSE {ev.get('ncse')}", flush=True)
            checkpoint()
        if args.commit_push and any(r["status"] == "ok" for r in model_results):
            c = commit_model(model, model_results)
            results.append({"model": model, "slug": model_slug(model), "case": "commit", **c})
            print(f"[git ] {model}: {c['status']} {c.get('commit') or ''} {c.get('detail') or ''}", flush=True)
            checkpoint()
    if current and not args.no_unload:
        unload(args.base_url, current)

    checkpoint(finished=True)
    print(f"summary: {summary_path}")
    if not args.no_report and not args.commit_push:
        subprocess.run([sys.executable, "scripts/compare_vlm_models.py", "--out", "docs/vlm_model_comparison.md",
                        "--json", "docs/vlm_model_comparison.json"], cwd=REPO, check=False)
    failed = [r for r in results if r["status"] in ("failed", "timeout")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
