#!/usr/bin/env python
"""Record the OASIS demo video: a genuine, scripted walk through the live
landing page and the locally served app + gateway, then cut it to under
three minutes.

Each scene is recorded by Playwright as its own clip (real time, 1280x720).
Post-processing (ffmpeg from imageio-ffmpeg) speeds up only the waiting
inside long scenes, prepends title cards, and concatenates. Nothing shown is
mocked: the answers come from the local gateway over Ollama, the refusals
from the policy file, the maps from the committed artifacts.

Prerequisites (see README quick start):
    uvicorn gateway.main:app --port 8080          # with Ollama serving gpt-oss:20b
    cd app && npm run dev -- --port 5173          # the PWA
    python -m pip install playwright imageio-ffmpeg && python -m playwright install chromium

    python docs/demo/record_demo.py --out docs/demo/out
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LANDING = "https://rayford295.github.io/ray-resilience/"
APP = "http://localhost:5173/"
SIZE = {"width": 1280, "height": 720}
FONT = "C\\:/Windows/Fonts/arialbd.ttf"  # ffmpeg drawtext escaping for Windows paths


def scene(pw, out: Path, name: str, fn) -> Path:
    """Run `fn(page)` in a fresh context that records video; return the clip path."""
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport=SIZE, record_video_dir=str(out / "raw"), record_video_size=SIZE,
                              device_scale_factor=1)
    page = ctx.new_page()
    started = time.time()
    try:
        fn(page)
    finally:
        video = page.video
        ctx.close()
        browser.close()
    path = Path(video.path())
    target = out / "raw" / f"{name}.webm"
    if target.exists():
        target.unlink()
    path.rename(target)
    print(f"[scene] {name}: {time.time() - started:.1f}s -> {target.name}", flush=True)
    return target


# --------------------------------------------------------------------------- scenes
def s1_landing(page):
    page.goto(LANDING, wait_until="networkidle")
    page.wait_for_timeout(3500)
    for y in (500, 1000, 1500):
        page.mouse.wheel(0, y)
        page.wait_for_timeout(2200)


def dismiss_welcome_if_any(page):
    btn = page.locator("button.linkish.dim")
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(600)


def s2_resident(page):
    page.goto(APP, wait_until="networkidle")
    page.wait_for_timeout(3500)
    # the getting-started card's "try an address" fills the example address and switches to resident mode
    try_btn = page.locator("button.linkish").first
    if try_btn.count():
        try_btn.click()
    else:
        page.get_by_role("tab", name="resident").click()
    page.wait_for_timeout(1200)
    box = page.get_by_placeholder("US address")
    if not (box.input_value() or "").strip():
        box.fill("2200 Lake Ave, Altadena, CA")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Look up").click()
    page.wait_for_timeout(9000)   # geocode + fly-to + dossier render
    page.mouse.wheel(0, 300)
    page.wait_for_timeout(3000)


def s3_planner(page):
    page.goto(APP, wait_until="networkidle")
    page.wait_for_timeout(2500)
    dismiss_welcome_if_any(page)
    page.get_by_role("tab", name="planner").click()
    page.wait_for_timeout(1500)
    page.locator("select").first.select_option("eaton-priority")
    page.wait_for_timeout(3500)
    slider = page.locator("input[type=range]").first
    for value in ("0.2", "0.35", "0.5", "0.65", "0.8", "0.95", "0.5"):
        slider.evaluate("(el, v) => { const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; "
                        "setter.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); "
                        "el.dispatchEvent(new Event('change', {bubbles: true})); }", value)
        page.wait_for_timeout(1400)
    page.get_by_role("button", name="show lineage & provenance").click()
    page.wait_for_timeout(3500)
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(3000)
    # the parcel-level source is denied by the distribution plane: it is not on the site
    page.evaluate("() => fetch('/events/eaton-2025/exposure/dins_points_restricted.csv.gz').then(r => r.status)")
    page.wait_for_timeout(500)


def ask(page, question: str, timeout_ms: int = 240_000):
    page.get_by_placeholder("How ").fill(question)
    page.wait_for_timeout(700)
    page.get_by_role("button", name="Ask", exact=True).click()
    page.wait_for_selector("button:has-text('Ask'):not([disabled])", timeout=timeout_ms)
    page.wait_for_timeout(2500)


def s4_ask(page):
    page.goto(APP, wait_until="networkidle")
    page.wait_for_timeout(2500)
    try_btn = page.locator("button.linkish").first
    if try_btn.count():
        try_btn.click()
    else:
        page.get_by_role("tab", name="resident").click()
    page.wait_for_timeout(1000)
    box = page.get_by_placeholder("US address")
    if not (box.input_value() or "").strip():
        box.fill("2200 Lake Ave, Altadena, CA")
    page.get_by_role("button", name="Look up").click()
    page.wait_for_timeout(7000)
    # a question the policy refuses before any model call: the refusal names the rule
    ask(page, "Was my house at this address destroyed?", timeout_ms=60_000)
    page.wait_for_timeout(3000)
    # a question the resident may ask: grounded answer, every sentence cited
    ask(page, "What evidence covers this address?")
    page.wait_for_timeout(4000)
    page.get_by_role("tab", name="planner").click()
    page.wait_for_timeout(1500)
    ask(page, "How severe is the damage here?")
    page.wait_for_timeout(5000)


# --------------------------------------------------------------------------- post-processing
def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(ff: str, path: Path) -> float:
    r = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def title_card(ff: str, out: Path, name: str, lines: list[str], seconds: float) -> Path:
    target = out / f"{name}.mp4"
    text = "|".join(lines)
    filters = []
    for i, line in enumerate(lines):
        y = f"(h/2)-{(len(lines) - 1) * 40}+{i * 80}" if i == 0 else f"(h/2)-{(len(lines) - 1) * 40}+{i * 80}"
        size = 46 if i == 0 else 30
        color = "white" if i == 0 else "0xBFD3E6"
        safe = line.replace(":", "\\:").replace("'", "’")
        filters.append(f"drawtext=fontfile='{FONT}':text='{safe}':fontcolor={color}:fontsize={size}:x=(w-text_w)/2:y={y}")
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", f"color=c=0x1F3A5F:s={SIZE['width']}x{SIZE['height']}:d={seconds}",
                    "-vf", ",".join(filters), "-r", "30", "-pix_fmt", "yuv420p", "-an", str(target)],
                   check=True, capture_output=True)
    return target


def speed_clip(ff: str, src: Path, out: Path, factor: float) -> Path:
    """Re-time a clip by `factor` (2.0 = twice as fast); normalise to 30 fps mp4."""
    target = out / f"{src.stem}.mp4"
    subprocess.run([ff, "-y", "-i", str(src), "-vf", f"setpts=PTS/{factor},fps=30,scale={SIZE['width']}:{SIZE['height']}",
                    "-an", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", str(target)],
                   check=True, capture_output=True)
    return target


def concat(ff: str, parts: list[Path], target: Path) -> None:
    lst = target.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(target)],
                   check=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("docs/demo/out"))
    ap.add_argument("--skip-record", action="store_true", help="reuse raw clips already in <out>/raw")
    ap.add_argument("--max-seconds", type=float, default=175.0, help="target total length (hard limit is 180)")
    args = ap.parse_args()
    out = args.out
    (out / "raw").mkdir(parents=True, exist_ok=True)

    if not args.skip_record:
        with sync_playwright() as pw:
            scene(pw, out, "s1_landing", s1_landing)
            scene(pw, out, "s2_resident", s2_resident)
            scene(pw, out, "s3_planner", s3_planner)
            scene(pw, out, "s4_ask", s4_ask)

    ff = ffmpeg_exe()
    raw = {p.stem: p for p in (out / "raw").glob("s*.webm")}
    durations = {k: probe_duration(ff, p) for k, p in raw.items()}
    print("raw durations", json.dumps({k: round(v, 1) for k, v in durations.items()}), flush=True)

    # Budget: cards ~14 s; scenes 1-3 at 1.25x; scene 4 (model latency) absorbs the rest.
    cards = 4 * 3.5
    base = {"s1_landing": 1.25, "s2_resident": 1.25, "s3_planner": 1.25}
    fixed = cards + sum(durations[k] / f for k, f in base.items() if k in durations)
    remaining = max(args.max_seconds - fixed, 30.0)
    f4 = max(1.0, durations.get("s4_ask", 0.0) / remaining)
    factors = {**base, "s4_ask": round(f4, 2)}
    print("speed factors", factors, flush=True)

    parts = [
        title_card(ff, out, "c0", ["Ray Resilience", "An accountable GeoAI system for place-based disaster intelligence",
                                   "OASIS @ ACM SIGSPATIAL 2026 · Track A"], 3.5),
        speed_clip(ff, raw["s1_landing"], out, factors["s1_landing"]),
        title_card(ff, out, "c1", ["Resident mode", "An address gets one of three answers: covered, outside, or not determined"], 3.5),
        speed_clip(ff, raw["s2_resident"], out, factors["s2_resident"]),
        title_card(ff, out, "c2", ["Planner mode", "The trade-off is the planner's: priority = t x damage + (1-t) x SVI, every move audit-logged",
                                   "Lineage from any layer back to hashed source snapshots"], 3.5),
        speed_clip(ff, raw["s3_planner"], out, factors["s3_planner"]),
        title_card(ff, out, "c3", ["Ask Ray", "Refusals name the policy rule; answers cite an artifact for every sentence",
                                   f"Local open model over Ollama - model latency shown at {factors['s4_ask']}x"], 3.5),
        speed_clip(ff, raw["s4_ask"], out, factors["s4_ask"]),
    ]
    final = out / "ray-resilience-demo.mp4"
    concat(ff, parts, final)
    total = probe_duration(ff, final)
    print(f"final: {final} ({total:.1f}s)", flush=True)
    if total >= 180:
        print("!!! over three minutes — lower --max-seconds", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
