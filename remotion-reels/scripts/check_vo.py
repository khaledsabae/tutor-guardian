#!/usr/bin/env python3
"""
check_vo — an independent ear on the voice-over takes.

A TTS take can say a different word than its line (a judge once heard
«اتصل» where the line says «تسأل»). This asks a Gemini text model (not the
TTS model, so it does not touch the TTS quota) to write down what it hears in
each take, verbatim, and compares that with the line in vo_script.json after
folding away diacritics, tatweel, punctuation and hamza/alef/yaa variants.

Prints one row per take: OK, or DIFF with what was heard. A DIFF is a reason
to listen, not proof of a bad take (the ear can mishear too).

Usage: python3 scripts/check_vo.py v2:4 v6 ...   (a reel = all of its lines)
The API key is read like gen_vo.py does (never printed).
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_vo import OUT, SCRIPT, api_key  # noqa: E402

MODEL = "gemini-2.5-flash"
ASK = ("Transcribe this Arabic speech exactly as spoken, word for word, in Arabic script. "
       "Do not correct, complete or explain anything. Output only the transcript.")


def fold(s: str) -> str:
    s = re.sub(r"[ً-ْٰـ]", "", s)  # harakat, dagger alef, tatweel
    s = re.sub(r"[أإآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"[^ء-ي\s]", " ", s).replace("غوغل", "جوجل")  # both spellings of Google are said the same
    return " ".join(s.split())


def hear(mp3: Path) -> str:
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/mp3", "data": base64.b64encode(mp3.read_bytes()).decode()}},
                                    {"text": ASK}]}],
            "generationConfig": {"temperature": 0}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": api_key(), "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=120))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def main() -> int:
    spec = json.loads(SCRIPT.read_text())["reels"]
    wanted: list[tuple[str, int]] = []
    for a in sys.argv[1:]:
        reel, _, n = a.partition(":")
        wanted += [(reel, int(n))] if n else [(reel, i) for i in range(1, len(spec[reel]) + 1)]
    bad = 0
    for reel, i in wanted:
        text = spec[reel][i - 1]["text"]
        try:
            heard = hear(OUT / f"{reel}_{i}.mp3")
        except urllib.error.HTTPError as e:
            print(f"{reel}:{i}  ERROR HTTP {e.code}")
            bad += 1
            continue
        ok = fold(heard) == fold(text)
        bad += not ok
        print(f"{reel}:{i}  {'OK  ' if ok else 'DIFF'}  {text}" + ("" if ok else f"\n           heard: {heard}"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
