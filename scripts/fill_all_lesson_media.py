#!/usr/bin/env python3
"""Fill missing lesson media so EVERY lesson in docs/lesson_index.json has both a
podcast (edge-tts) and a video (PIL title card + ffmpeg). The index uses short
lesson_ids (lesson_<age>_<topic>_<NN>) while the lesson source files use long
names; we resolve via age_group + topic_path + trailing number.

Reuses the same narration/card/render logic as gen_tts_podcasts + gen_lesson_videos.
Run:  python scripts/fill_all_lesson_media.py
Then rsync docs/ to the VPS (no backend rebuild needed — docs is volume-mounted).
"""
import asyncio
import glob
import json
import os
import pathlib
import subprocess

import arabic_reshaper
import edge_tts
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

BASE = pathlib.Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
DOCS = BASE / "docs"
INDEX = DOCS / "lesson_index.json"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
VOICE = "ar-EG-SalmaNeural"
W, H = 1280, 720
GRAD = {
    "development":       ((14, 165, 233), (4, 120, 87)),
    "medical":          ((99, 102, 241), (76, 29, 149)),
    "cyber":            ((56, 189, 248), (3, 105, 161)),
    "islamic_parenting": ((245, 158, 11), (22, 101, 52)),
}

_FILES = {os.path.basename(f)[:-5] for f in glob.glob(str(LESSONS_DIR / "*.json"))}


def resolve_file(entry: dict) -> str | None:
    """Map an index entry (short id) to its long-named lesson file stem."""
    lid = entry["lesson_id"]
    nn = lid.split("_")[-1]
    cand = f"lesson_{entry['age_group']}_{entry['topic_path']}_{nn}"
    if cand in _FILES:
        return cand
    return lid if lid in _FILES else None


def narration(d: dict) -> str:
    parts = [d["title"] + ".", "", d.get("summary", "")]
    if d.get("try_this"):
        parts += ["", "والآن، نشاط تجرّبه:", d["try_this"]]
    refl = d.get("reflection_prompts") or []
    if refl:
        parts += ["", "وللتأمّل:", " ".join(refl)]
    return "\n".join(parts)


def _ar(t: str) -> str:
    return get_display(arabic_reshaper.reshape(t))


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


def make_card(title: str, domain: str, out: pathlib.Path):
    top, bot = GRAD.get(domain, GRAD["development"])
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        row = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(FONT, 64)
    f_sub = ImageFont.truetype(FONT, 30)
    lines = _wrap(d, title, f_title, W - 200)
    y = (H - len(lines) * 82) // 2 - 20
    for ln in lines:
        s = _ar(ln)
        w = d.textlength(s, font=f_title)
        d.text(((W - w) / 2 + 2, y + 2), s, font=f_title, fill=(0, 0, 0))
        d.text(((W - w) / 2, y), s, font=f_title, fill=(255, 255, 255))
        y += 82
    sub = _ar("المربي الذكي · فيديو الدرس")
    sw = d.textlength(sub, font=f_sub)
    d.text(((W - sw) / 2, H - 90), sub, font=f_sub, fill=(255, 255, 255))
    img.save(out)


def render(card: pathlib.Path, audio: pathlib.Path, out: pathlib.Path) -> bool:
    cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(card), "-i", str(audio),
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
           "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 50_000


async def synth(text: str, out: pathlib.Path):
    await edge_tts.Communicate(text, VOICE, rate="-5%").save(str(out))


def save(index):
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                     encoding="utf-8")


async def main():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    tmp = DOCS / "_card_fill_tmp.png"
    pod_done = vid_done = skipped = 0
    processed = 0

    for entry in index["lessons"]:
        assets = entry.setdefault("assets", {})
        need_pod = not assets.get("podcasts")
        need_vid = not assets.get("videos")
        if not need_pod and not need_vid:
            continue
        stem = resolve_file(entry)
        if stem is None:
            print(f"✗ {entry['lesson_id']}: no source file", flush=True)
            skipped += 1
            continue
        d = json.loads((LESSONS_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        lid = entry["lesson_id"]  # keep the index id for filenames (app-facing)
        domain = d.get("domain", "development")
        title = d.get("title", lid)
        pod = DOCS / f"{lid}_podcast.mp3"
        out = DOCS / f"{lid}_video.mp4"

        # 1) Podcast — reuse on-disk file if already generated (resumable).
        if need_pod:
            try:
                if not (pod.exists() and pod.stat().st_size >= 10 * 1024):
                    await synth(narration(d), pod)
                if pod.stat().st_size < 10 * 1024:
                    raise RuntimeError("tiny output")
                assets["podcasts"] = [{"file": f"docs/{lid}_podcast.mp3",
                                       "size_bytes": pod.stat().st_size,
                                       "language": "ar"}]
                pod_done += 1
                print(f"🎧 {lid}: {round(pod.stat().st_size/1024)} KB", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"✗ podcast {lid}: {e}", flush=True)
                pod.unlink(missing_ok=True)

        # 2) Video — reuse on-disk file if present; else render from whatever
        # podcast audio this lesson has (new {lid}_podcast.mp3, or a pre-existing
        # long-named NotebookLM podcast already linked in the index).
        audio = pod if pod.exists() else None
        if audio is None:
            for pc in assets.get("podcasts", []):
                cand = BASE / pc["file"]
                if cand.exists():
                    audio = cand
                    break
        if need_vid and audio is not None:
            if not (out.exists() and out.stat().st_size > 50_000):
                make_card(title, domain, tmp)
                render(tmp, audio, out)
            if out.exists() and out.stat().st_size > 50_000:
                assets["videos"] = [{"file": f"docs/{lid}_video.mp4",
                                     "size_bytes": out.stat().st_size,
                                     "language": "ar"}]
                vid_done += 1
                print(f"🎬 {lid}: {round(out.stat().st_size/1024)} KB", flush=True)
            else:
                print(f"✗ video {lid}: ffmpeg failed", flush=True)

        processed += 1
        if processed % 5 == 0:  # checkpoint so progress survives a kill
            save(index)

    tmp.unlink(missing_ok=True)
    save(index)
    print(f"\nDone: +{pod_done} podcasts, +{vid_done} videos, {skipped} skipped",
          flush=True)


if __name__ == "__main__":
    asyncio.run(main())
