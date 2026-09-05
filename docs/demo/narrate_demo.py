#!/usr/bin/env python
"""Add an English voice-over and burned-in subtitles to the assembled demo.

Reads the parts written by record_demo.py (title cards and scene clips in
<out>/) to recover the timeline, synthesises each narration block with the
Windows speech engine (offline, no key; `--voice` picks an installed voice),
places every block at its scene's start (never overlapping the previous
block; a block that would overrun is time-stretched up to 1.3x), burns the
same text as subtitles, writes an .srt beside the video, and muxes the result:

    python docs/demo/narrate_demo.py --out docs/demo/out --voice "Microsoft Zira Desktop"

Output: <out>/ray-resilience-demo-narrated.mp4 and .srt
"""

from __future__ import annotations

import argparse
import json
import subprocess
import textwrap
import wave
from pathlib import Path

PARTS = ["c0", "s1_landing", "c1", "s2_resident", "c2", "s3_planner", "c3", "s4_ask"]

#: (anchor part, offset as a fraction of that part's duration, narration text)
NARRATION = [
    ("c0", 0.0,
     "Ray Resilience is an accountable GeoAI system for place-based disaster intelligence: "
     "three deep cases, one harness, and a nationwide hourly hazard watch."),
    ("c1", 0.0,
     "In resident mode an address gets one of three answers: covered, outside the evaluated areas, "
     "or not determined. This Altadena address is covered: residents, structures assessed, the destroyed "
     "share, and the declared unknowns, never a single parcel."),
    ("c2", 0.0,
     "In planner mode the trade-off belongs to the planner: priority is t times damage plus one minus t times "
     "social vulnerability. Moving the slider re-ranks the tiles, and every move is audit-logged. Lineage traces "
     "the layer back to hashed source snapshots, including a rejected run the harness kept."),
    ("c3", 0.0,
     "Ask Ray. The agent runs inside the Steward Harness: a policy pre-check before any model call, and a citation "
     "post-check after it."),
    ("s4_ask", 0.16,
     "A question about a single house is refused before the model is called, and the refusal names the rule: "
     "no parcel-level claims for anyone."),
    ("s4_ask", 0.42,
     "A question the resident may ask goes to a local open model. Every sentence must cite an artifact; a draft "
     "that does not is refused, and the refusal says why. When the draft passes, the answer carries its citations "
     "and the declared unknowns."),
    ("s4_ask", 0.76,
     "Switching to planner unlocks tile-level damage where Tier-3 evidence exists. The system computes more than "
     "it is allowed to say, says only what it can cite, and keeps the record, including of its own failures. "
     "Ray Resilience: a steward of evidence, not an oracle."),
]


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(ff: str, path: Path) -> float:
    r = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise SystemExit(f"no duration for {path}")


def tts(text: str, wav: Path, voice: str, rate: int) -> None:
    txt = wav.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SelectVoice('{voice}'); $s.Rate = {rate}; "
        f"$s.SetOutputToWaveFile('{wav}'); "
        f"$s.Speak([IO.File]::ReadAllText('{txt}', [Text.Encoding]::UTF8)); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True, capture_output=True)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def stretch(ff: str, src: Path, factor: float) -> Path:
    dst = src.with_name(src.stem + "_fast.wav")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-filter:a", f"atempo={factor:.3f}", str(dst)], check=True)
    return dst


def srt_time(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def esc_path(p: Path) -> str:
    return p.resolve().as_posix().replace(":", "\\:")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("docs/demo/out"))
    ap.add_argument("--voice", default="Microsoft Zira Desktop")
    ap.add_argument("--rate", type=int, default=0, help="SAPI rate, -10..10 (0 = normal)")
    ap.add_argument("--video", default="ray-resilience-demo.mp4")
    args = ap.parse_args()
    out = args.out
    ff = ffmpeg_exe()
    video = out / args.video
    total = duration(ff, video)

    # timeline from the parts
    starts, t = {}, 0.0
    lengths = {}
    for name in PARTS:
        d = duration(ff, out / f"{name}.mp4")
        starts[name], lengths[name] = t, d
        t += d
    print(f"video {total:.1f}s; parts end at {t:.1f}s", flush=True)

    aud = out / "narration"
    aud.mkdir(exist_ok=True)
    blocks, prev_end = [], -1.0
    for i, (anchor, frac, text) in enumerate(NARRATION):
        wav = aud / f"n{i:02d}.wav"
        tts(text, wav, args.voice, args.rate)
        length = wav_seconds(wav)
        planned = starts[anchor] + frac * lengths[anchor]
        start = max(planned, prev_end + 0.35)
        # the next block's planned start bounds this one
        if i + 1 < len(NARRATION):
            na, nf, _ = NARRATION[i + 1]
            limit = starts[na] + nf * lengths[na] - 0.35
        else:
            limit = total - 0.5
        if start + length > limit:
            factor = min(1.3, (start + length) / max(limit - start, 1.0) * 1.0)
            factor = max(1.0, (length / max(limit - start, 1.0)))
            factor = min(1.3, factor)
            if factor > 1.01:
                wav = stretch(ff, wav, factor)
                length = wav_seconds(wav)
        end = start + length
        if end > total - 0.2:
            print(f"!!! block {i} ends at {end:.1f}s beyond the video ({total:.1f}s); shorten the text", flush=True)
        blocks.append({"i": i, "start": round(start, 2), "end": round(end, 2), "text": text, "wav": wav})
        prev_end = end
        print(f"[{i}] {start:6.1f}-{end:6.1f}s ({length:4.1f}s, planned {planned:.1f}) {text[:60]}…", flush=True)

    # subtitles: one drawtext per block, text from a file, wrapped to <= 2 lines
    filters = []
    for b in blocks:
        lines = textwrap.wrap(b["text"], 62)
        if len(lines) > 2:  # keep two lines: rewrap wider
            lines = textwrap.wrap(b["text"], 78)
        sub = aud / f"s{b['i']:02d}.txt"
        with open(sub, "w", encoding="utf-8", newline="\n") as fh:  # LF only: drawtext reads CR as an extra line
            fh.write("\n".join(lines))
        filters.append(
            f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':textfile='{esc_path(sub)}':fontsize=23:fontcolor=white:"
            f"box=1:boxcolor=black@0.6:boxborderw=10:line_spacing=5:x=(w-text_w)/2:y=h-th-40:"
            f"enable='between(t\\,{b['start']}\\,{b['end'] + 0.25})'"
        )
    vf = ",".join(filters)

    # audio: each block delayed to its start, mixed, trimmed to the video
    inputs, achain = [], []
    for k, b in enumerate(blocks, start=1):
        inputs += ["-i", str(b["wav"])]
        achain.append(f"[{k}:a]adelay={int(b['start'] * 1000)}|{int(b['start'] * 1000)},aformat=sample_rates=48000:channel_layouts=mono[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(1, len(blocks) + 1)) + f"amix=inputs={len(blocks)}:normalize=0:dropout_transition=0,volume=1.0[aout]"
    fc = ";".join(achain + [mix])

    target = out / "ray-resilience-demo-narrated.mp4"
    cmd = [ff, "-y", "-loglevel", "error", "-i", str(video), *inputs, "-filter_complex", fc, "-vf", vf,
           "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(target)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + r.stderr[-3000:])

    srt = target.with_suffix(".srt")
    srt.write_text("".join(f"{b['i'] + 1}\n{srt_time(b['start'])} --> {srt_time(b['end'] + 0.25)}\n{b['text']}\n\n" for b in blocks),
                   encoding="utf-8")
    (out / "narration_timeline.json").write_text(json.dumps([{k: (str(v) if isinstance(v, Path) else v) for k, v in b.items()} for b in blocks], indent=1), encoding="utf-8")
    print(f"wrote {target} ({duration(ff, target):.1f}s) and {srt.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
