#!/usr/bin/env python3
"""podcast_to_reel.py — convert a tutor-guardian podcast into a 9:16 marketing Reel.

Usage:
    python scripts/podcast_to_reel.py --input docs/lesson_....mp3 --report docs/lesson_assets/reports/...md --title "..." --output docs/marketing/reels_output/

Requirements: ffmpeg + ffprobe (system)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEAL = "#01696F"
AMBER = "#F59E0B"
DEFAULT_SCREENSHOT = ROOT / "docs" / "marketing" / "screenshots" / "final" / "01_02_onboarding_welcome.png"
# NOTE: Noto Sans Arabic has no emoji/middle-dot glyphs — they render as
# tofu boxes in drawtext. Stick to Arabic-script punctuation only.
WATERMARK_TEXT = "المربّي الذكي — مجاني ١٠٠٪"
CTA_LINES = ["التطبيق مجاني ١٠٠٪", "بلا إعلانات، بلا اشتراكات", "رابط التحميل في الوصف"]


def _slugify(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name).strip("_")[:80]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw)


def get_audio_duration(path: str) -> float:
    r = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    return float(r.stdout.strip())


def extract_takeaways(report_path: str) -> list[str]:
    text = Path(report_path).read_text(encoding="utf-8")
    quotes: list[str] = []
    for m in re.finditer(r'"([^"\n]{20,220})"\s*\[', text):
        q = m.group(1).strip()
        if q and q not in quotes:
            quotes.append(q)
    in_takeaways = False
    for line in text.splitlines():
        if "مقتطفات" in line or "Key Takeaways" in line:
            in_takeaways = True
            continue
        if in_takeaways:
            if line.startswith("###") or (line.startswith("##") and "Takeaways" not in line):
                break
            m = re.match(r"[-*]\s*\"?(.+?)\"?\s*(?:\[\d|\n|$)", line)
            if m:
                q = m.group(1).strip('"').strip()
                if len(q) > 20 and q not in quotes:
                    quotes.append(q)
    return quotes[:6]


def load_transcript(mp3_path: str) -> list[dict] | None:
    base = Path(mp3_path).stem
    candidates = [
        ROOT / "docs" / "marketing" / "transcripts" / f"{base}.json",
        ROOT / "docs" / "marketing" / "transcripts" / f"{base}.srt",
    ]
    for c in candidates:
        if not c.exists():
            continue
        if c.suffix == ".json":
            data = json.loads(c.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "segments" in data:
                return [{"start": s["start"], "end": s["end"], "text": s.get("text", "").strip()} for s in data["segments"]]
            if isinstance(data, list):
                return data
        if c.suffix == ".srt":
            return _parse_srt(c.read_text(encoding="utf-8"))
    return None


def _parse_srt(text: str) -> list[dict]:
    out = []
    for b in re.split(r"\n\s*\n", text.strip()):
        lines = b.strip().splitlines()
        if len(lines) < 3:
            continue
        time_line = next((l for l in lines if " --> " in l), None)
        if not time_line:
            continue
        start, end = time_line.split(" --> ")
        txt = " ".join(l for l in lines if l != time_line and not l.strip().isdigit())
        out.append({"start": _srt_t(start), "end": _srt_t(end), "text": txt.strip()})
    return out


def _srt_t(t: str) -> float:
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def find_best_segment(takeaway: str, transcript: list[dict], audio_dur: float) -> tuple[float, float] | None:
    words = set(re.findall(r"[\u0600-\u06FF\u0750-\u077F]+", takeaway))
    if not words:
        return None
    best = None
    best_score = -1
    window, step = 14.0, 1.5
    t = 0.0
    while t + window <= audio_dur:
        score = 0
        for seg in transcript:
            if seg["end"] < t or seg["start"] > t + window:
                continue
            seg_words = set(re.findall(r"[\u0600-\u06FF\u0750-\u077F]+", seg["text"]))
            score += len(words & seg_words)
        if score > best_score:
            best_score = score
            best = (t, t + window)
        t += step
    if best and best_score > 0:
        return best
    return None


def build_timed_lines(takeaways: list[str], audio_dur: float, transcript: list[dict] | None, target: float) -> tuple[float, float, list[dict]]:
    # Distribute takeaways across target duration.
    per = min(14.0, max(7.0, target / max(1, len(takeaways))))
    raw = []
    cursor = 0.0
    for q in takeaways[:5]:
        dur = max(7.0, min(per, len(q) / 4.5))
        raw.append({"start": cursor, "end": cursor + dur, "text": q})
        cursor += dur
        if cursor >= target - 6:
            break
    real_dur = min(max(cursor + 6, 30.0), min(60.0, audio_dur - 5))
    if transcript:
        bounds = find_best_segment(raw[0]["text"], transcript, audio_dur) if raw else None
        if bounds:
            start = max(0.0, bounds[0] - 2.0)
            end = min(audio_dur, start + real_dur)
        else:
            start = min(8.0, audio_dur * 0.05)
            end = min(start + real_dur, audio_dur)
        timed = []
        for seg in transcript:
            if seg["end"] <= start or seg["start"] >= end:
                continue
            timed.append({"start": max(0.0, seg["start"] - start), "end": min(end - start, seg["end"] - start), "text": seg["text"]})
        # If transcript too sparse, fall back to takeaway-based subtitles.
        if not timed or len(" ".join(t["text"] for t in timed).split()) < 10:
            timed = [{"start": s["start"] * (end - start) / raw[-1]["end"],
                      "end": s["end"] * (end - start) / raw[-1]["end"],
                      "text": s["text"]} for s in raw if s["start"] < end - start]
        return start, end, timed
    start = min(8.0, audio_dur * 0.05)
    end = min(start + real_dur, audio_dur)
    timed = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in raw if s["end"] <= end - start]
    return start, end, timed


def _escape(s: str) -> str:
    # ASCII '%' triggers drawtext expansion and NO escaping variant survives
    # the filter parser ("Stray %") — the whole line silently fails to render
    # (bit us on «مجاني 100%»). The Arabic percent sign ٪ renders perfectly
    # in Noto Sans Arabic, so substitute it.
    return (
        s.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "٪")
    )


def _wrap(text: str, max_chars: int = 34) -> list[str]:
    words = text.split()
    lines, cur = [], []
    length = 0
    for w in words:
        if length + len(w) + (1 if cur else 0) > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            length = len(w)
        else:
            cur.append(w)
            length += len(w) + (1 if length else 0)
    if cur:
        lines.append(" ".join(cur))
    return lines


def render_reel(mp3_path: str, output_path: str, title: str, timed_lines: list[dict], clip_start: float, clip_end: float, screenshot: Path | None = None) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    duration = clip_end - clip_start
    w, h = 1080, 1920
    screenshot_file = str(screenshot) if screenshot and screenshot.exists() else str(DEFAULT_SCREENSHOT)

    chains: list[str] = []
    last = "[0:v]"

    # Background: blurred screenshot, darkened
    chains.append(f"{last}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=18:18,eq=brightness=-0.28:contrast=1.05[bg]")
    last = "[bg]"
    # Top amber bar
    chains.append(f"{last}drawbox=y=0:x=0:width={w}:height=12:color=0xF59E0B:t=fill[topbar]")
    last = "[topbar]"
    # Brand top-right
    chains.append(
        f"{last}drawtext=text='المربّي الذكي':fontfile=/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf:"
        f"fontsize=54:fontcolor=white:borderw=3:bordercolor=black:x=w-tw-50:y=45:enable='between(t\\,0\\,{duration})'[brand]"
    )
    last = "[brand]"

    # Subtitles
    for i, line in enumerate(timed_lines):
        wrapped = _wrap(line["text"], 28)
        for idx, ltext in enumerate(wrapped):
            y = int(h * 0.40 + idx * 92)
            alpha = f"if(lt(t\\,{line['start']+0.25})\\,(t-{line['start']})/0.25\\,if(gt(t\\,{line['end']-0.25})\\,({line['end']}-t)/0.25\\,1))"
            chains.append(
                f"{last}drawtext=text='{_escape(ltext)}':fontfile=/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf:"
                f"fontsize=72:fontcolor=white:borderw=5:bordercolor=0x111111:x=(w-tw)/2:y={y}:"
                f"enable='between(t\\,{line['start']:.2f}\\,{line['end']:.2f})':alpha='{alpha}'[sub{i}_{idx}]"
            )
            last = f"[sub{i}_{idx}]"

    # Watermark (bottom center, hidden in last 6s)
    wm_end = max(0.0, duration - 6.0)
    chains.append(
        f"{last}drawtext=text='{_escape(WATERMARK_TEXT)}':fontfile=/usr/share/fonts/truetype/noto/NotoSansArabic.ttf:"
        f"fontsize=38:fontcolor=white@0.9:borderw=2:bordercolor=black:x=(w-tw)/2:y=h-th-155:"
        f"enable='between(t\\,0\\,{wm_end})'[wm]"
    )
    last = "[wm]"

    # CTA panel last 6s
    cta_start = max(0.0, duration - 6.0)
    cta_y = h - 420
    cta_h = 360
    cta_w = w - 120
    # Outer border
    chains.append(f"{last}drawbox=x=58:y={cta_y-2}:w={cta_w+4}:h={cta_h+4}:color=0xF59E0B:t=fill[ctaborder]")
    last = "[ctaborder]"
    # Inner fill
    chains.append(f"{last}drawbox=x=60:y={cta_y}:w={cta_w}:h={cta_h}:color=0x0B1021@0.96:t=fill[ctafill]")
    last = "[ctafill]"
    sizes = [54, 40, 38]
    colors = ["white", "0x94a3b8", "0xcbd5e1"]
    ys = [cta_y + 65, cta_y + 145, cta_y + 225]
    for idx, (line, size, color, y) in enumerate(zip(CTA_LINES, sizes, colors, ys)):
        alpha = f"if(lt(t\\,{cta_start+0.3})\\,(t-{cta_start})/0.3\\,1)"
        chains.append(
            f"{last}drawtext=text='{_escape(line)}':fontfile=/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf:"
            f"fontsize={size}:fontcolor={color}:borderw=3:bordercolor=black:x=(w-tw)/2:y={y}:"
            f"enable='between(t\\,{cta_start}\\,{duration})':alpha='{alpha}'[cta{idx}]"
        )
        last = f"[cta{idx}]"

    filter_complex = ";".join(chains)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", screenshot_file,
        "-ss", str(clip_start), "-t", str(duration), "-i", mp3_path,
        "-filter_complex", filter_complex,
        "-map", last, "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd)


def load_lesson_index() -> dict:
    idx = json.loads((ROOT / "docs" / "lesson_index.json").read_text(encoding="utf-8"))
    return {l["lesson_id"]: l for l in idx["lessons"]}


def pick_unrendered(n: int, output_dir: Path, manifest: dict | None = None) -> list[tuple[str, Path, Path, str]]:
    """Return up to n (lesson_id, mp3, report, title) that are not in manifest."""
    lookup = load_lesson_index()
    out = []
    for lid, lesson in lookup.items():
        if len(out) >= n:
            break
        podcasts = lesson["assets"].get("podcasts", [])
        reports = lesson["assets"].get("reports", [])
        if not podcasts or not reports:
            continue
        mp3 = ROOT / "docs" / podcasts[0]["file"].split("/")[-1]
        report = ROOT / reports[0]["file"]
        if not mp3.exists() or not report.exists():
            continue
        title = lesson.get("seo_title") or lesson.get("title_ar", "") or lesson["lesson_id"]
        if title == lesson["lesson_id"]:
            # lesson_index lacks an Arabic title — fall back to the report H1
            # so filenames/captions stay human-readable Arabic.
            try:
                for line in report.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("#"):
                        title = line.strip().lstrip("# ").strip()[:60] or title
                        break
            except OSError:
                pass
        slug = _slugify(title)
        if manifest and slug in manifest.get("rendered", []):
            continue
        out.append((lid, mp3, report, title))
    return out


def update_manifest(output_dir: Path, entry: dict) -> None:
    mpath = output_dir / "manifest.json"
    manifest: dict = {"rendered": []}
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    manifest.setdefault("rendered", []).append(entry)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Podcast to Reel generator")
    parser.add_argument("--input", "-i", help="Single source MP3 path")
    parser.add_argument("--report", "-r", help="Single report markdown path")
    parser.add_argument("--title", "-t", help="Single Reel title")
    parser.add_argument("--batch", "-b", type=int, help="Number of reels to batch-generate from lesson_index")
    parser.add_argument("--output", "-o", default=str(ROOT / "docs" / "marketing" / "reels_output"))
    parser.add_argument("--duration", "-d", type=float, default=42.0)
    parser.add_argument("--screenshot")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Batch mode
    if args.batch:
        manifest: dict = {"rendered": []}
        mpath = out_dir / "manifest.json"
        if mpath.exists():
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        jobs = pick_unrendered(args.batch, out_dir, manifest)
        print(f"Batch: {len(jobs)} reels queued")
        for lid, mp3, report, title in jobs:
            try:
                out_path = out_dir / f"reel_{_slugify(title)}.mp4"
                # avoid overwriting by appending lesson_id if collision
                if out_path.exists():
                    out_path = out_dir / f"reel_{_slugify(title)}_{lid}.mp4"
                audio_dur = get_audio_duration(str(mp3))
                takeaways = extract_takeaways(str(report))
                transcript = load_transcript(str(mp3))
                start, end, timed = build_timed_lines(takeaways, audio_dur, transcript, args.duration)
                screenshot = Path(args.screenshot) if args.screenshot else DEFAULT_SCREENSHOT
                render_reel(str(mp3), str(out_path), title, timed, start, end, screenshot)
                update_manifest(out_dir, {"lesson_id": lid, "title": title, "file": str(out_path.name), "rendered_at": import_time()})
                print(f"  OK: {out_path.name}")
            except Exception as e:
                print(f"  FAIL {lid}: {e}")
        return

    if not (args.input and args.report and args.title):
        parser.error("--input, --report, --title are required unless --batch is used")

    audio_dur = get_audio_duration(args.input)
    print(f"Audio duration: {audio_dur:.1f}s")

    takeaways = extract_takeaways(args.report)
    print(f"Extracted {len(takeaways)} takeaways")
    for t in takeaways[:5]:
        print("  -", t[:100])

    transcript = load_transcript(args.input)
    print("Transcript available:", bool(transcript))

    start, end, timed = build_timed_lines(takeaways, audio_dur, transcript, args.duration)
    print(f"Selected clip: {start:.1f}s - {end:.1f}s ({end-start:.1f}s)")
    for line in timed[:6]:
        print(f"  {line['start']:.1f}-{line['end']:.1f}: {line['text'][:60]}")

    out_path = out_dir / f"reel_{_slugify(args.title)}.mp4"
    screenshot = Path(args.screenshot) if args.screenshot else DEFAULT_SCREENSHOT
    render_reel(args.input, str(out_path), args.title, timed, start, end, screenshot)
    print(f"Done: {out_path}")


def import_time() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()