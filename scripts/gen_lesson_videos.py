#!/usr/bin/env python3
"""Local video generator for the new lessons (NotebookLM is rate-limited).
Builds a clean title-card (domain gradient + shaped Arabic title) and renders
it over the lesson's TTS narration into an MP4 via the bundled ffmpeg. Links
the video into docs/lesson_index.json. Also fills the 3 missing 2-3 PATH videos
(docs/path_videos/<path_id>_ar_eg.mp4) from their paths' intro text.

Prereq: run scripts/gen_tts_podcasts.py first (the audio soundtrack).
Run:  python scripts/gen_lesson_videos.py
"""
import json
import pathlib
import subprocess

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

BASE = pathlib.Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
PATHS_DIR = BASE / "knowledge_base" / "curriculum" / "paths"
DOCS = BASE / "docs"
PV_DIR = DOCS / "path_videos"
INDEX = DOCS / "lesson_index.json"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
W, H = 1280, 720

GRAD = {  # (top RGB, bottom RGB) per domain
    "development":       ((14, 165, 233), (4, 120, 87)),
    "medical":          ((99, 102, 241), (76, 29, 149)),
    "cyber":            ((56, 189, 248), (3, 105, 161)),
    "islamic_parenting": ((245, 158, 11), (22, 101, 52)),
}


def _ar(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(_ar(t), font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:4]


def make_card(title: str, domain: str, subtitle: str, out: pathlib.Path):
    top, bot = GRAD.get(domain, GRAD["development"])
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        px_row = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = px_row
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(FONT, 64)
    f_sub = ImageFont.truetype(FONT, 30)
    lines = _wrap(d, title, f_title, W - 200)
    total_h = len(lines) * 82
    y = (H - total_h) // 2 - 20
    for ln in lines:
        s = _ar(ln)
        w = d.textlength(s, font=f_title)
        d.text(((W - w) / 2 + 2, y + 2), s, font=f_title, fill=(0, 0, 0))  # shadow
        d.text(((W - w) / 2, y), s, font=f_title, fill=(255, 255, 255))
        y += 82
    sub = _ar(subtitle)
    sw = d.textlength(sub, font=f_sub)
    d.text(((W - sw) / 2, H - 90), sub, font=f_sub, fill=(255, 255, 255))
    img.save(out)


def render(card: pathlib.Path, audio: pathlib.Path, out: pathlib.Path) -> bool:
    cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(card), "-i", str(audio),
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
           "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 50_000


def main():
    PV_DIR.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {l["lesson_id"]: l for l in index["lessons"]}
    tmp = DOCS / "_card_tmp.png"

    # 1) Lesson videos (need the TTS mp3).
    done = 0
    new = [f for f in sorted(LESSONS_DIR.glob("*.json"))
           if f.stem.rsplit("_", 1)[-1].startswith("b")]
    for f in new:
        d = json.loads(f.read_text(encoding="utf-8"))
        lid = d["id"]
        audio = DOCS / f"{lid}_podcast.mp3"
        if not audio.exists():
            print(f"– {lid}: no audio yet, skipped")
            continue
        make_card(d["title"], d["domain"], "المربي الذكي · فيديو الدرس", tmp)
        rel = f"docs/{lid}_video.mp4"
        out = DOCS / f"{lid}_video.mp4"
        if not render(tmp, audio, out):
            print(f"✗ {lid}: ffmpeg failed")
            continue
        entry = by_id.get(lid)
        if entry is not None:
            a = entry.setdefault("assets", {})
            a["videos"] = [{"file": rel, "size_bytes": out.stat().st_size,
                            "language": "ar"}]
        done += 1
        print(f"✓ video {lid}: {round(out.stat().st_size/1024)} KB")

    # 2) The 3 missing 2-3 PATH videos.
    pdone = 0
    for pf in sorted(PATHS_DIR.glob("path_2-3_*.json")):
        p = json.loads(pf.read_text(encoding="utf-8"))
        pid = p["id"]
        target = PV_DIR / f"{pid}_ar_eg.mp4"
        if target.exists():
            continue
        # narrate the path's title + description via the first lesson's audio
        # is wrong; instead synth a short path intro on the fly.
        intro = f"{p['title']}. {p.get('description','')[:400]}"
        audio = DOCS / f"_path_{pid}_tts.mp3"
        try:
            import asyncio, edge_tts  # noqa: E401
            asyncio.run(edge_tts.Communicate(intro, "ar-EG-SalmaNeural",
                                              rate="-5%").save(str(audio)))
        except Exception as e:  # noqa: BLE001
            print(f"✗ path {pid}: tts failed {e}")
            continue
        make_card(p["title"], p["domain"], "المربي الذكي · فيديو الوحدة", tmp)
        if render(tmp, audio, target):
            pdone += 1
            print(f"✓ path video {pid}")
        audio.unlink(missing_ok=True)

    tmp.unlink(missing_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\nDone: {done} lesson videos + {pdone} path videos")


if __name__ == "__main__":
    main()
