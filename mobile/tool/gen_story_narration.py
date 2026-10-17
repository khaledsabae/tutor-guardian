#!/usr/bin/env python3
"""«اسمعها من نور» — record a story, one file per page, with sentence timings.

Run from the repo root:

    python3 mobile/tool/gen_story_narration.py layla_star --lang ar
    for l in ar en; do python3 mobile/tool/gen_story_narration.py --all --lang $l; done

Resumable: a story whose manifest is current (same model/voice, same page
texts, audio on disk) is skipped, and in a story whose text changed only the
changed pages are re-recorded — so re-running the same command after a text
fix, or after the daily quota ran out, records only what is missing. A 429
that outlives the retries stops the whole run (exit 3) instead of failing
story after story. `--force` re-records everything chosen.

Writes, per story:
    docs/stories/narration/<lang>/<id>.json      the manifest the reader reads
    docs/stories/narration/<lang>/<id>_p<N>.m4a  one AAC file per page

How the timings are exact without a forced aligner: every sentence is
synthesised on its own and the page file is the sentences joined with a short
silence, so each sentence's start and end are known by construction. The
manifest stores each page's text verbatim; the app plays a page only when the
text still matches (lib/features/stories/narration/story_narration.dart), so
correcting a story silences the corrected page instead of reading old words.

Engines (picked by --engine, default $TTS_ENGINE or gemini):
  gemini      Gemini TTS, key GEMINI_API_KEY from the project .env.
  elevenlabs  ElevenLabs TTS (pcm_24000), key ELEVENLABS_API_KEY from the
              environment or the project .env.elevenlabs. Default voice is
              George on eleven_v3 — Khaled's choice for the English library,
              2026-10-17. The engine follows the model: eleven_* is ElevenLabs.
Keys are never printed. edge-tts is not an option — tried and rejected. No
music, ever: the files are voice only.

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
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORIES = {"ar": ROOT / "mobile/assets/data/stories.json",
           "en": ROOT / "mobile/assets/data/stories_en.json"}
RATE = 24000
GAP_S = 0.45  # silence between sentences
DEFAULT_MODEL = "gemini-3.8-flash-tts"
ENGINES = {  # engine -> (default model, default voice)
    "gemini": (DEFAULT_MODEL, "Algieba"),  # Khaled's choice, 2026-10-15
    "elevenlabs": ("eleven_v3", "JBFqnCBsd6RMkjVDRZzb"),  # George; Khaled's choice for English, 2026-10-17
}
EL_SETTINGS = {  # the settings the chosen samples were recorded with
    "eleven_v3": {"stability": 0.5, "similarity_boost": 0.75},
    "eleven_multilingual_v2": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.15,
                               "use_speaker_boost": True, "speed": 0.92},
}

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


def engine_of(model: str) -> str:
    return "elevenlabs" if model.startswith("eleven_") else "gemini"


def api_key(engine: str = "gemini") -> str:
    var, name = (("ELEVENLABS_API_KEY", ".env.elevenlabs") if engine == "elevenlabs"
                 else ("GEMINI_API_KEY", ".env"))
    key = os.environ.get(var)
    # A worktree has no .env of its own; the main checkout's is the one.
    for env in (ROOT / name, Path.home() / "projects/tutor-guardian" / name):
        if key or not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(var + "="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        sys.exit(f"{var} is not set (project {name})")
    return key


class QuotaExhausted(Exception):
    """A 429 that outlived the retries: the day's quota is spent."""


QUOTA_MESSAGE = ("الحصة اليومية خلصت — كمّل بكرة بنفس الأمر.\n"
                 "Daily quota spent — run the same command again tomorrow; "
                 "finished stories are kept and skipped.")


def synth(text: str, lang: str, voice: str, model: str, key: str, usage: dict) -> bytes:
    """16-bit mono PCM at 24 kHz for one sentence."""
    if engine_of(model) == "elevenlabs":
        return synth_elevenlabs(text, lang, voice, model, key, usage)
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
            if e.code == 429:
                raise QuotaExhausted(e.read()[:200].decode("utf-8", "replace"))
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


def synth_elevenlabs(text: str, lang: str, voice: str, model: str, key: str, usage: dict) -> bytes:
    """ElevenLabs: the same 16-bit mono 24 kHz PCM. No style notes — the voice is the style."""
    body = {"text": text, "model_id": model}
    if model in EL_SETTINGS:
        body["voice_settings"] = EL_SETTINGS[model]
    if model != "eleven_multilingual_v2":  # v2 takes no language_code
        body["language_code"] = lang
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_24000"
    for attempt in range(5):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                pcm, cost = resp.read(), resp.headers.get("character-cost")
            break
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if "quota_exceeded" in detail or e.code == 402:
                raise QuotaExhausted(detail)
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            if e.code == 429:
                raise QuotaExhausted(detail)
            raise SystemExit(f"TTS failed: HTTP {e.code} {detail!r}")
        except urllib.error.URLError as e:  # DNS/connection blips
            if attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise SystemExit(f"TTS failed: {e.reason}")
    usage["characters"] = usage.get("characters", 0) + len(text)
    usage["credits"] = usage.get("credits", 0) + int(cost or 0)
    return pcm[: len(pcm) // 2 * 2]


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


# ── verification: every page is transcribed back and compared ─────────────
# A TTS model can read its own style notes aloud. Two of the first samples
# did exactly that («اقرأ النص التالي بصوت راوٍ دافئ… لا تقرأ هذه التعليمات»)
# when the notes were a plain prefix. The director-notes layout above stopped
# it, but nothing guaranteed it would stay stopped — so no page is written
# unless a transcript of it says the page and nothing else.
INSTRUCTION_WORDS = ["اقرأ", "اقرا", "تعليمات", "بصوت", "راوي", "راوٍ", "راويه", "راوية",
                     "فصحى", "audio profile", "director", "transcript", "storyteller",
                     "instructions", "style", "pace"]
MIN_SIMILARITY = {"ar": 0.72, "en": 0.80}
ATTEMPTS = 3
REPORT: list[dict] = []

_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0670\u0640]")


def normalize(text: str) -> str:
    t = _DIACRITICS.sub("", text.lower())
    t = re.sub("[إأآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^\w]+", "", t)


def transcribe(audio: Path, lang: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["whisper", str(audio), "--model", "small", "--language", lang,
                        "--output_format", "txt", "--output_dir", tmp, "--fp16", "False"],
                       check=True, capture_output=True)
        return (Path(tmp) / f"{audio.stem}.txt").read_text(encoding="utf-8")


# Normalised characters a transcript may carry beyond the page at either end
# before the page fails — about one short word, for whisper's own slack.
MAX_EDGE_EXTRA = 8


def edge_extras(text: str, heard: str) -> tuple[int, int]:
    """(leading, trailing) normalised characters heard outside the page text.

    A narrator that reads its notes says something *before* the story; one
    that runs on says something after it. Aligning the transcript to the page
    and measuring what hangs off each end catches both, even when the middle
    matches well enough to pass the similarity bar.
    """
    t, h = normalize(text), normalize(heard)
    blocks = [b for b in SequenceMatcher(None, t, h, autojunk=False).get_matching_blocks()
              if b.size >= 4]
    if not blocks:
        return len(h), len(h)
    first, last = blocks[0], blocks[-1]
    lead = max(0, first.b - first.a)
    trail = max(0, (len(h) - (last.b + last.size)) - (len(t) - (last.a + last.size)))
    return lead, trail


def verify_page(text: str, heard: str, lang: str) -> list[str]:
    """Problems with a page recording, judged from its transcript. Empty = pass."""
    problems = []
    low_heard, low_text = heard.lower(), text.lower()
    for word in INSTRUCTION_WORDS:
        if low_heard.count(word) > low_text.count(word):
            problems.append(f"instruction word heard: {word!r}")
    lead, trail = edge_extras(text, heard)
    if lead > MAX_EDGE_EXTRA:
        problems.append(f"{lead} extra characters heard before the page text")
    if trail > MAX_EDGE_EXTRA:
        problems.append(f"{trail} extra characters heard after the page text")
    ratio = SequenceMatcher(None, normalize(text), normalize(heard), autojunk=False).ratio()
    if ratio < MIN_SIMILARITY[lang]:
        problems.append(f"transcript similarity {ratio:.2f} < {MIN_SIMILARITY[lang]}")
    return problems


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


def reusable_pages(story: dict, out_dir: Path, voice_tag: str) -> dict[int, dict]:
    """Pages of [story] already recorded and still current, by 0-based index.

    A page is reused when the story's manifest exists, was recorded in the
    same model/voice, holds the page's text verbatim (the same test the app
    applies before playing it) and its audio file is on disk. A story with
    pages but no manifest — a run cut short inside it — reuses nothing.
    """
    path = out_dir / f"{story['id']}.json"
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    if manifest.get("voice") != voice_tag:
        return {}
    reuse = {}
    for i, page in enumerate(story["pages"]):
        old = manifest.get("pages", [])
        if i < len(old) and old[i].get("text") == page["text"] \
                and (out_dir / Path(old[i]["audio"]).name).exists():
            reuse[i] = old[i]
    return reuse


def record_story(story: dict, lang: str, voice: str, model: str, out_dir: Path,
                 server_prefix: str, key: str, verify: bool = True,
                 reuse: dict[int, dict] | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    usage: dict = {}
    pages = []
    reuse = reuse or {}
    for n, page in enumerate(story["pages"], start=1):
        text = page["text"]
        name = f"{story['id']}_p{n}.m4a"
        if n - 1 in reuse:
            pages.append(reuse[n - 1])
            print(f"  {story['id']} p{n}: unchanged, kept")
            continue
        for attempt in range(1, ATTEMPTS + 1):
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
            encode_m4a(pcm, out_dir / name)
            if not verify:
                break
            heard = transcribe(out_dir / name, lang)
            problems = verify_page(text, heard, lang)
            REPORT.append({"story": story["id"], "page": n, "lang": lang, "attempt": attempt,
                           "problems": problems, "heard": heard.strip()})
            if not problems:
                break
            print(f"  ✗ {story['id']} p{n} attempt {attempt}: {problems}")
            (out_dir / name).unlink()
        else:
            raise SystemExit(f"✗ {story['id']} p{n} failed verification {ATTEMPTS}× "
                             "— no manifest written for this story")
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
    ap.add_argument("--engine", choices=sorted(ENGINES), default=os.environ.get("TTS_ENGINE", "gemini"),
                    help="sets the default --model/--voice (default $TTS_ENGINE or gemini)")
    ap.add_argument("--voice", help="default: the engine's (Algieba · George)")
    ap.add_argument("--model", help="default: the engine's; eleven_* models go to ElevenLabs")
    ap.add_argument("--out", type=Path, help="default docs/stories/narration/<lang>")
    ap.add_argument("--force", action="store_true",
                    help="re-record every chosen page, even ones already up to date")
    ap.add_argument("--skip-verify", action="store_true",
                    help="do not transcribe pages back (only for a quick listen, never for the app)")
    args = ap.parse_args()
    args.model = args.model or ENGINES[args.engine][0]
    args.voice = args.voice or ENGINES[args.engine][1]
    library = json.loads(STORIES[args.lang].read_text(encoding="utf-8"))
    chosen = library if args.all else [s for s in library if s["id"] in args.ids]
    if not chosen:
        sys.exit("no stories chosen")
    out = args.out or ROOT / "docs/stories/narration" / args.lang
    prefix = f"docs/stories/narration/{args.lang}"
    if not args.skip_verify and subprocess.run(["which", "whisper"], capture_output=True).returncode:
        sys.exit("whisper is needed to verify every page (or pass --skip-verify for a draft)")
    key = api_key(engine_of(args.model))
    sys.exit(run(chosen, args.lang, args.voice, args.model, out, prefix, key,
                 verify=not args.skip_verify, force=args.force))


def run(chosen: list[dict], lang: str, voice: str, model: str, out: Path, prefix: str,
        key: str, verify: bool = True, force: bool = False) -> int:
    """Record [chosen]; 0 done · 3 the day's quota ran out (resume tomorrow)."""
    total = {"audio_tokens": 0, "text_tokens": 0, "characters": 0, "credits": 0}
    voice_tag = f"{model}/{voice}"
    code = 0
    done = skipped = 0
    try:
        for story in chosen:
            reuse = {} if force else reusable_pages(story, out, voice_tag)
            if len(reuse) == len(story["pages"]):
                skipped += 1
                print(f"  {story['id']}: up to date, skipped")
                continue
            u = record_story(story, lang, voice, model, out, prefix, key,
                             verify=verify, reuse=reuse)
            done += 1
            for k in total:
                total[k] += u.get(k, 0)
    except QuotaExhausted as e:
        print(f"\n⏸  {QUOTA_MESSAGE}\n   ({e})")
        code = 3
    finally:
        print(f"stories recorded: {done} · skipped (up to date): {skipped}")
        if engine_of(model) == "elevenlabs":
            print(f"usage: {total['characters']} characters, {total['credits']} credits")
        else:
            print(f"usage: {total['audio_tokens']} audio tokens, {total['text_tokens']} text tokens")
        if REPORT:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            rep = out / f"verify_{lang}_{stamp}.json"
            rep.write_text(json.dumps({"usage": total, "pages": REPORT}, ensure_ascii=False,
                                      indent=1), encoding="utf-8")
            failed = sum(1 for r in REPORT if r["problems"])
            print(f"verification: {len(REPORT)} transcripts, {failed} failed attempts → {rep}")
    return code


if __name__ == "__main__":
    main()
