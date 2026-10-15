#!/usr/bin/env python3
"""«اسمعها من نور» — record a story, one file per page, with sentence timings.

Run from the repo root:

    python3 mobile/tool/gen_story_narration.py layla_star --lang ar --voice Sulafat
    python3 mobile/tool/gen_story_narration.py --all --lang ar --voice Sulafat

Writes, per story:
    docs/stories/narration/<lang>/<id>.json      the manifest the reader reads
    docs/stories/narration/<lang>/<id>_p<N>.m4a  one AAC file per page

How the timings are exact without a forced aligner: every sentence is
synthesised on its own and the page file is the sentences joined with a short
silence, so each sentence's start and end are known by construction. The
manifest stores each page's text verbatim; the app plays a page only when the
text still matches (lib/features/stories/narration/story_narration.dart), so
correcting a story silences the corrected page instead of reading old words.

Engine: Gemini TTS, key GEMINI_API_KEY from the project .env (never printed).
edge-tts is not an option — tried and rejected. No music, ever: the files are
voice only.

⚠️ This calls a paid API. Generating the whole library is Khaled's decision
(voice + cost); one story was sampled first (see the PR).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORIES = {"ar": ROOT / "mobile/assets/data/stories.json",
           "en": ROOT / "mobile/assets/data/stories_en.json"}
RATE = 24000
GAP_S = 0.45  # silence between sentences
DEFAULT_MODEL = "gemini-3.8-flash-tts"

STYLE = {
    "ar": """# AUDIO PROFILE: راوية قصص أطفال
## THE SCENE: غرفة هادئة قبل النوم، والراوية تقرأ لطفل صغير.
### DIRECTOR'S NOTES
Style: warm, gentle, smiling storyteller; clear Modern Standard Arabic (فصحى) with correct i'rab. No music, no sound effects.
Pace: slow and calm, short pauses at commas.
#### TRANSCRIPT
{TEXT}""",
    "en": """# AUDIO PROFILE: Children's storyteller
## THE SCENE: A quiet room before bedtime; the narrator reads to a young child.
### DIRECTOR'S NOTES
Style: warm, gentle, smiling storyteller; clear and natural. Arabic words (Allah, salah, wudu) pronounced correctly. No music, no sound effects.
Pace: slow and calm, short pauses at commas.
#### TRANSCRIPT
{TEXT}""",
}

_END = re.compile(r"[.!?؟…]+[»”\"'’]*(?=\s|$)")


def sentences(text: str) -> list[tuple[int, int]]:
    """Character ranges [from, to) of the sentences in [text], trimmed."""
    out, start = [], 0
    for m in _END.finditer(text):
        out.append((start, m.end()))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    trimmed = []
    for a, b in out:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            trimmed.append((a, b))
    return trimmed


def api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    # A worktree has no .env of its own; the main checkout's is the one.
    for env in (ROOT / ".env", Path.home() / "projects/tutor-guardian/.env"):
        if key or not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        sys.exit("GEMINI_API_KEY is not set (project .env)")
    return key


def synth(text: str, lang: str, voice: str, model: str, key: str, usage: dict) -> bytes:
    """16-bit mono PCM at 24 kHz for one sentence."""
    body = {
        "contents": [{"parts": [{"text": STYLE[lang].replace("{TEXT}", text)}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(5):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=180))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise SystemExit(f"TTS failed: HTTP {e.code} {e.read()[:200]!r}")
    meta = data.get("usageMetadata", {})
    usage["audio_tokens"] = usage.get("audio_tokens", 0) + meta.get("candidatesTokenCount", 0)
    usage["text_tokens"] = usage.get("text_tokens", 0) + meta.get("promptTokenCount", 0)
    raw = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw)) as w:
            assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
            return w.readframes(w.getnframes())
    return raw


def trim_silence(pcm: bytes, threshold: int = 300) -> bytes:
    """Drop leading/trailing near-silence so the gaps are ours, not the model's."""
    import array
    a = array.array("h", pcm)
    lo, hi = 0, len(a)
    while lo < hi and abs(a[lo]) < threshold:
        lo += 1
    while hi > lo and abs(a[hi - 1]) < threshold:
        hi -= 1
    pad = int(RATE * 0.06)
    return a[max(0, lo - pad):min(len(a), hi + pad)].tobytes()


def encode_m4a(pcm: bytes, out: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp.name, "-c:a", "aac",
                        "-b:a", "48k", "-ac", "1", "-movflags", "+faststart", str(out)], check=True)
    os.unlink(tmp.name)


def record_story(story: dict, lang: str, voice: str, model: str, out_dir: Path,
                 server_prefix: str, key: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    usage: dict = {}
    pages = []
    for n, page in enumerate(story["pages"], start=1):
        text = page["text"]
        pcm = b""
        spans = []
        gap = b"\0\0" * int(RATE * GAP_S)
        for a, b in sentences(text):
            clip = trim_silence(synth(text[a:b], lang, voice, model, key, usage))
            if pcm:
                pcm += gap
            start = len(pcm) / 2 / RATE
            pcm += clip
            spans.append({"from": a, "to": b, "start": round(start, 3),
                          "end": round(len(pcm) / 2 / RATE, 3)})
        name = f"{story['id']}_p{n}.m4a"
        encode_m4a(pcm, out_dir / name)
        pages.append({"audio": f"{server_prefix}/{name}", "text": text, "sentences": spans})
        print(f"  {story['id']} p{n}: {len(spans)} sentences, {len(pcm) / 2 / RATE:.1f}s")
    manifest = {"voice": f"{model}/{voice}", "language": lang, "pages": pages}
    (out_dir / f"{story['id']}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return usage


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--lang", choices=["ar", "en"], default="ar")
    ap.add_argument("--voice", default="Sulafat")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, help="default docs/stories/narration/<lang>")
    args = ap.parse_args()
    library = json.loads(STORIES[args.lang].read_text(encoding="utf-8"))
    chosen = library if args.all else [s for s in library if s["id"] in args.ids]
    if not chosen:
        sys.exit("no stories chosen")
    out = args.out or ROOT / "docs/stories/narration" / args.lang
    prefix = f"docs/stories/narration/{args.lang}"
    key = api_key()
    total = {"audio_tokens": 0, "text_tokens": 0}
    for story in chosen:
        u = record_story(story, args.lang, args.voice, args.model, out, prefix, key)
        for k in total:
            total[k] += u.get(k, 0)
    print(f"usage: {total['audio_tokens']} audio tokens, {total['text_tokens']} text tokens")


if __name__ == "__main__":
    main()
