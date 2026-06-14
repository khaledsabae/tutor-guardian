#!/usr/bin/env python3
"""Local-ish alternative to NotebookLM: narrate each new lesson as an MP3 using
edge-tts (Microsoft free neural TTS, Arabic Egyptian voice). Reads only the
PUBLIC lesson text (title + summary + activity), saves docs/<lid>_podcast.mp3,
and links it into docs/lesson_index.json so the lesson shows '🎧 استمع للبودكاست'.

Run:  python scripts/gen_tts_podcasts.py [--only <lesson_id>] [--voice ar-EG-SalmaNeural]
Then rsync docs/ to the VPS + restart backend.
"""
import argparse
import asyncio
import json
import pathlib

import edge_tts

BASE = pathlib.Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
DOCS = BASE / "docs"
INDEX = BASE / "docs" / "lesson_index.json"
DEFAULT_VOICE = "ar-EG-SalmaNeural"


def narration(d: dict) -> str:
    parts = [d["title"] + ".", "", d.get("summary", "")]
    if d.get("try_this"):
        parts += ["", "والآن، نشاط تجرّبه:", d["try_this"]]
    refl = d.get("reflection_prompts") or []
    if refl:
        parts += ["", "وللتأمّل:", " ".join(refl)]
    return "\n".join(parts)


async def synth(text: str, out: pathlib.Path, voice: str):
    communicate = edge_tts.Communicate(text, voice, rate="-5%")
    await communicate.save(str(out))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    args = ap.parse_args()

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {l["lesson_id"]: l for l in index["lessons"]}

    new = [f for f in sorted(LESSONS_DIR.glob("*.json"))
           if f.stem.rsplit("_", 1)[-1].startswith("b")]
    if args.only:
        new = [f for f in new if f.stem == args.only]

    done = 0
    for f in new:
        d = json.loads(f.read_text(encoding="utf-8"))
        lid = d["id"]
        rel = f"docs/{lid}_podcast.mp3"
        out = DOCS / f"{lid}_podcast.mp3"
        try:
            await synth(narration(d), out, args.voice)
            size = out.stat().st_size
            if size < 10 * 1024:  # < 10 KB = failed/empty
                print(f"✗ {lid}: tiny output ({size}B) — skipped")
                out.unlink(missing_ok=True)
                continue
        except Exception as e:  # noqa: BLE001
            print(f"✗ {lid}: {e}")
            continue
        entry = by_id.get(lid)
        if entry is not None:
            a = entry.setdefault("assets", {})
            a["podcasts"] = [{"file": rel, "size_bytes": size, "language": "ar"}]
        done += 1
        print(f"✓ {lid}: {round(size/1024)} KB")

    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\nDone: {done}/{len(new)} lesson podcasts (TTS)")


if __name__ == "__main__":
    asyncio.run(main())
