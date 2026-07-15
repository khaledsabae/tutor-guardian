#!/usr/bin/env python3
"""Convert a tutor-guardian path video into a YouTube Short (9:16) with captions and CTA.

Usage:
    python3 scripts/make_youtube_short.py path_4-6_development_positive_parenting
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MANIFEST = BASE / "scratch" / "path_video_manifest.json"
OUT_DIR = BASE / "docs" / "marketing" / "shorts"
LOGO = BASE / "frontend" / "icons" / "icon-512.png"


def duration_of(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_segment(input_path: str, out_path: Path, start: float, duration: float):
    """Extract and convert a segment to a vertical 9:16 Short.

    Strategy: keep the original video centered with a dynamic blurred/colored
    background, gentle zoom/pan on the main content, and a gradient overlay
    so the canvas feels alive and modern.
    """
    vf = (
        "[0:v]split=2[orig][bg];"
        "[bg]crop=min(iw\,ih*9/16):min(ih\,iw*16/9),"
        "scale=1080*1.3:1920*1.3:flags=lanczos,"
        "zoompan=z='1.25+0.00025*in':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':"
        "d=1:s=1080x1920,"
        "boxblur=12:12,"
        "colorchannelmixer=.8:.8:.8:1,"
        "eq=brightness=-0.05:contrast=1.15,split[t1][t2];"
        "[t1]colorbalance=rs=0.15:gs=-0.05:bs=-0.1[tint];"
        "[t2]colorbalance=rs=-0.1:gs=0.05:bs=0.15[sep];"
        "[tint]colorkey=0x000000:0.01:0.5[kt];"
        "[sep][kt]overlay=0:0:format=auto[bg2];"
        "[bg2]drawbox=x=0:y=0:w=iw:h=ih*0.12:color=0x0B1021@0.7:t=fill,"
        "drawbox=x=0:y=ih*0.78:w=iw:h=ih*0.22:color=0x0B1021@0.75:t=fill[bgf];"
        "[orig]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,"
        "zoompan=z='min(zoom+0.00012,1.06)':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d=1:s=1080x1920[orig2];"
        "[bgf][orig2]overlay=(W-w)/2:(H-h)/2:enable='between(t,0,1000)'[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ss", str(start), "-t", str(duration),
        "-vf", vf,
        "-af", "volume=1.2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def make_ass_captions(path_id: str, duration: float, out_path: Path):
    """Generate a minimal ASS subtitle with TikTok-style captions."""
    # Fallback script keyed by path_id — can be replaced with transcript parsing later.
    scripts = {
        "path_4-6_development_positive_parenting": [
            (0, 3, "⚠️ 90% من الأمهات بيرتكبوا الخطأ ده"),
            (3, 6, "التربية الإيجابية"),
            (6, 10, "تبدأ من الأمان"),
            (10, 15, "الطفل اللي بيحس بالقبول"),
            (15, 20, "بيتعلم بسرعة"),
            (20, 25, "مع المربّي كل درس"),
            (25, 30, "نصيحة علمية + تطبيق"),
            (30, 35, "حوّلي التحديات لنجاحات"),
            (35, duration, "حملي التطبيق مجانًا 👇"),
        ],
    }
    lines = scripts.get(path_id, [(0, duration, "اكتشف المزيد")])

    header = """[Script Info]
Title:Tutor Guardian Short Captions
ScriptType:v4.00+
PlayResX:1080
PlayResY:1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,Cairo,84,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,8,4,2,40,40,300,1
Style: TikTok,Cairo,78,&H00FFFFFF,&H000000FF,&H00FF69B4,&H80000000,-1,0,0,0,100,100,0,0,3,6,3,2,40,40,280,1
Style: CTA,Cairo,80,&H00FFFFFF,&H000000FF,&H0000FF00,&H80000000,-1,0,0,0,100,100,0,0,3,7,4,2,40,40,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ass_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        cs = int(round((t % 1) * 100))
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    style_for = {
        0: "Hook",
        len(lines) - 1: "CTA",
    }
    body = ""
    for i, (start, end, text) in enumerate(lines):
        style = style_for.get(i, "TikTok")
        body += f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}\n"

    out_path.write_text(header + body, encoding="utf-8")


def burn_captions(input_path: Path, ass_path: Path, logo: Path, out_path: Path):
    vf = (
        "[0:v]ass='{}'[sub];"
        "[1:v]scale=96:96[logo];"
        "[sub][logo]overlay=24:24:format=auto[v]"
    ).format(str(ass_path).replace("\\", "\\\\").replace("'", "\\'"))
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path), "-i", str(logo),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path_id")
    parser.add_argument("--start", type=float, default=15.0,
                        help="Segment start in seconds")
    parser.add_argument("--duration", type=float, default=55.0,
                        help="Segment duration in seconds")
    parser.add_argument("--upload", action="store_true",
                        help="Upload to YouTube after creation")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print("❌ Manifest not found:", MANIFEST)
        sys.exit(1)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = manifest.get(args.path_id)
    if not entry:
        print("❌ path_id not in manifest:", args.path_id)
        sys.exit(1)

    input_video = entry["video_path"]
    full_duration = duration_of(input_video)
    start = min(args.start, full_duration - args.duration - 1)
    duration = min(args.duration, full_duration - start - 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{args.path_id}_short_{int(start)}s_{int(duration)}s"
    segment_path = OUT_DIR / f"{stem}_segment.mp4"
    final_path = OUT_DIR / f"{stem}.mp4"
    ass_path = OUT_DIR / f"{stem}.ass"

    print(f"🎬 Creating Short from {input_video}")
    print(f"   start={start}s duration={duration}s")
    extract_segment(input_video, segment_path, start, duration)
    make_ass_captions(args.path_id, duration, ass_path)
    burn_captions(segment_path, ass_path, LOGO, final_path)

    print("✅ Short ready:", final_path)
    print("   size:", f"{final_path.stat().st_size / 1024 / 1024:.1f} MB")

    if args.upload:
        upload_script = BASE / "scripts" / "upload_youtube_short.py"
        subprocess.run([sys.executable, str(upload_script), str(final_path), args.path_id], check=True)


if __name__ == "__main__":
    main()
