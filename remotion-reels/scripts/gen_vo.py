#!/usr/bin/env python3
"""
gen_vo — the voice-over lines of the «المربّي» reels (teaser + five campaign reels).

Reads src/noor/campaign/vo_script.json (reel -> lines with a start frame and
a deadline frame) and, for every line:

  1. asks the TTS engine (model + voice from the JSON) to speak it in
     simple, neutral, warm Arabic ("اللغة العربية البيضاء"); the engine
     follows the model: eleven_* is ElevenLabs (voice = voice ID, pcm_24000,
     key ELEVENLABS_API_KEY or the project .env.elevenlabs), anything else is
     Gemini TTS (voice = prebuilt voice name, key GEMINI_API_KEY); raw takes
     are cached in out/vo_raw/ by a hash of (model, voice, style, text), so a
     re-run costs nothing unless a line changes or --retake is given;
     every new take is transcribed back with whisper and must say the line
     and nothing else (mobile/tool/gen_story_narration.py's verify_page),
     else it is retaken, up to 3 times;
  2. trims the silence around it, normalises it to -16 LUFS (true peak kept
     at or below -2 dBFS), 20 ms fade in / 60 ms fade out;
  3. writes public/noor/vo/<reel>_<n>.mp3 (mono, 44.1 kHz, 96 kb/s).

Then it plans the timing and writes src/noor/campaign/vo_lines.ts for the
VO compositions. The voice is never rushed: when a line would run past its
deadline, the stretch of the reel it is spoken over ([at, until] in source
frames) is played a little slower, by just enough frames for the line plus
a short breath (MARGIN). Everything after it moves later by as much; the
plan (stretches + where each line starts in the output) is in vo_lines.ts.

The MP3s are committed (with public/noor/vo/takes.json: the text, model and
voice of each take): TTS takes are not reproducible, so the repo keeps the
takes that were checked, and a re-run only calls TTS for a line whose text,
model or voice changed, or one named in --retake. Keys are read from the environment, else
from the main checkout's .env / .env.elevenlabs (never printed).

Exit codes: 0 done · 2 quota spent (lists the lines left) · 4 a line failed verification 3x
(vo_lines.ts is then left as it was).

Usage: python3 scripts/gen_vo.py [--only v1,teaser] [--retake v1:3,...] [--skip-verify]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "src" / "noor" / "campaign" / "vo_script.json"
LINES_TS = HERE / "src" / "noor" / "campaign" / "vo_lines.ts"
OUT = HERE / "public" / "noor" / "vo"
CACHE = HERE / "out" / "vo_raw"
FPS = 30
MARGIN = 5  # frames of air after a line before its scene moves on
GAP = 6  # frames between two lines when one follows the other directly
TARGET_LUFS = -16.0
PEAK_MAX = -2.0

STYLE = (
    "Read this Arabic line aloud as a warm, calm, friendly narrator talking to a parent. "
    "Use simple, neutral, everyday Arabic as heard in pan-Arab media (اللغة العربية البيضاء): "
    "not Egyptian or any dialect, not heavy classical recitation, no exaggerated case endings. "
    "Natural conversational pace; short, natural pauses at the dots. Smile in the voice. "
    "Say only the line, nothing else. Line:\n"
)


# ElevenLabs voice settings, as the chosen sample was recorded (Hakim, 2026-10-17)
EL_SETTINGS = {"stability": 0.55, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True, "speed": 0.92}
ATTEMPTS = 3


def is_elevenlabs(model: str) -> bool:
    return model.startswith("eleven_")


def api_key(var: str = "GEMINI_API_KEY", name: str = ".env") -> str:
    if os.environ.get(var):
        return os.environ[var]
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    for env in [HERE.parent / name, (HERE / common).resolve().parent / name]:
        if env.is_file():
            for line in env.read_text().splitlines():
                if line.startswith(var + "="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(f"{var} not found")


class QuotaHit(Exception):
    """TTS answered 429: the day's quota is spent. Retrying only burns time, so the run stops."""


def pcm_to_wav(pcm: bytes, out: Path) -> None:
    # 24 kHz, 16-bit, mono PCM -> WAV
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "-", str(out)],
                   input=pcm, check=True)


def tts_elevenlabs(text: str, model: str, voice: str, out: Path) -> None:
    body = {"text": text, "model_id": model, "voice_settings": EL_SETTINGS}
    if model != "eleven_multilingual_v2":  # v2 takes no language_code
        body["language_code"] = "ar"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_24000"
    for attempt in range(5):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"xi-api-key": api_key("ELEVENLABS_API_KEY", ".env.elevenlabs"),
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                pcm = resp.read()
            pcm_to_wav(pcm[: len(pcm) // 2 * 2], out)
            return
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            if "quota_exceeded" in detail or e.code == 402 or (e.code == 429 and attempt == 4):
                raise QuotaHit(model) from None
            if e.code not in (429, 500, 502, 503):
                sys.exit(f"TTS failed: HTTP {e.code} {detail}")
            print(f"  retry {attempt + 1}: HTTP {e.code}", file=sys.stderr)
        except (urllib.error.URLError, ConnectionError) as e:
            print(f"  retry {attempt + 1}: {type(e).__name__}", file=sys.stderr)
        time.sleep(4 * (attempt + 1))
    sys.exit(f"TTS failed for: {text}")


def tts(text: str, model: str, voice: str, out: Path) -> None:
    if is_elevenlabs(model):
        return tts_elevenlabs(text, model, voice, out)
    body = {
        "contents": [{"parts": [{"text": STYLE + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"x-goog-api-key": api_key(), "Content-Type": "application/json"})
            data = json.load(urllib.request.urlopen(req, timeout=180))
            pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            pcm_to_wav(pcm, out)
            return
        except (urllib.error.URLError, KeyError, IndexError, ConnectionError) as e:
            code = getattr(e, "code", "")
            if code == 429:
                raise QuotaHit(model) from None
            print(f"  retry {attempt + 1}: {type(e).__name__} {code}", file=sys.stderr)
            time.sleep(4 * (attempt + 1))
    sys.exit(f"TTS failed for: {text}")


def verifier():
    """whisper transcript check shared with the story narrator (mobile/tool/gen_story_narration.py)."""
    sys.path.insert(0, str(HERE.parent / "mobile" / "tool"))
    from gen_story_narration import transcribe, verify_page  # noqa: E402
    if subprocess.run(["which", "whisper"], capture_output=True).returncode:
        sys.exit("whisper is needed to verify every line (or pass --skip-verify for a draft)")
    return lambda text, wav: (lambda heard: (verify_page(text, heard, "ar"), heard.strip()))(transcribe(wav, "ar"))


def out_with(stretch: list[tuple[int, int, int]], f: float) -> float:
    """Source frame -> output frame when each window [a, b] is played over (b - a + add) frames."""
    o = f
    for a, b, add in stretch:
        o += add if f >= b else add * max(0.0, f - a) / (b - a)
    return o


def loudness(path: Path, filt: str = "") -> tuple[float, float]:
    chain = (filt + "," if filt else "") + "ebur128=peak=true:framelog=quiet"
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", chain, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    peak = float(re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", summary).group(1))
    return lufs, peak


TRIM = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,"
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse,aresample=44100,"
        # a gentle speech compressor, so the line can sit at -16 LUFS under a -2 dBFS ceiling
        "acompressor=threshold=0.1:ratio=3:attack=5:release=120")
LIMIT = "alimiter=limit=0.79:attack=3:release=60:level=disabled"


def process(raw: Path, mp3: Path) -> float:
    lufs, _ = loudness(raw, TRIM)
    gain = TARGET_LUFS - lufs
    # second pass: the limiter takes a little off, put it back once
    lufs2, _ = loudness(raw, f"{TRIM},volume={gain:.2f}dB,{LIMIT}")
    gain += TARGET_LUFS - lufs2
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "x.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"{TRIM},volume={gain:.2f}dB,{LIMIT}", str(wav)],
                       check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                                   capture_output=True, text=True).stdout)
        fade = f"afade=t=in:d=0.02,afade=t=out:st={max(0.0, dur - 0.06):.3f}:d=0.06"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", fade, "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k",
                        str(mp3)], check=True)
    return dur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--retake", default="")
    ap.add_argument("--skip-verify", action="store_true", help="do not transcribe new takes back (drafts only)")
    args = ap.parse_args()
    check = None if args.skip_verify else verifier()
    report: list[dict] = []
    failed: list[str] = []
    spec = json.loads(SCRIPT.read_text())
    voice = spec["voice"]["name"]
    only = set(filter(None, args.only.split(",")))
    retake = set(filter(None, args.retake.split(",")))
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    table: dict[str, dict] = {}
    manifest_path = OUT / "takes.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    recorded: set[str] = set()
    for reel, lines in spec["reels"].items():
        table[reel] = {"stretch": [], "lines": []}
        stretch: list[tuple[int, int, int]] = []
        prev_end = -GAP

        # a reel may use another model of the same voice (quota): all its lines then come from that model
        model = spec.get("model_by_reel", {}).get(reel, spec["voice"]["model"])
        for i, line in enumerate(lines, 1):
            mp3 = OUT / f"{reel}_{i}.mp3"
            if only and reel not in only and not mp3.exists():
                continue
            take = {"text": line["text"], "model": model, "voice": voice}
            current = mp3.exists() and manifest.get(f"{reel}_{i}") == take and f"{reel}:{i}" not in retake
            if (not only or reel in only) and not current:
                style = json.dumps(EL_SETTINGS, sort_keys=True) if is_elevenlabs(model) else STYLE
                key = hashlib.sha1(f"{model}|{voice}|{style}|{line['text']}".encode()).hexdigest()[:16]
                raw = CACHE / f"{reel}_{i}_{key}.wav"
                if f"{reel}:{i}" in retake and raw.exists():
                    raw.rename(raw.with_suffix(f".old{int(time.time())}.wav"))
                for attempt in range(1, ATTEMPTS + 1):
                    try:
                        if not raw.exists():
                            tts(line["text"], model, voice, raw)
                    except QuotaHit:
                        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                                 encoding="utf-8")
                        left = [f"{r}:{n}" for r, ls in spec["reels"].items() if not only or r in only
                                for n, ln in enumerate(ls, 1)
                                if manifest.get(f"{r}_{n}") != {"text": ln["text"], "voice": voice,
                                                                "model": spec.get("model_by_reel", {}).get(r, spec["voice"]["model"])}
                                or (f"{r}:{n}" in retake and f"{r}:{n}" not in recorded)]
                        print(f"\nTTS quota hit (429) on {model} at {reel}:{i} — stopping, no retry.", file=sys.stderr)
                        print(f"Lines still to record: {', '.join(left)}", file=sys.stderr)
                        print("Finish later with: python3 scripts/gen_vo.py" + (f" --only {args.only}" if args.only else "")
                              + (f" --retake {args.retake}" if args.retake else ""), file=sys.stderr)
                        return 2
                    if check is None:
                        break
                    problems, heard = check(line["text"], raw)
                    report.append({"line": f"{reel}:{i}", "attempt": attempt, "problems": problems, "heard": heard})
                    if not problems:
                        break
                    print(f"  ✗ {reel}:{i} attempt {attempt}: {problems} — heard: {heard}", file=sys.stderr)
                    raw.rename(raw.with_suffix(f".bad{attempt}.wav"))
                else:
                    failed.append(f"{reel}:{i}")
                    continue
                process(raw, mp3)
                manifest[f"{reel}_{i}"] = take
                recorded.add(f"{reel}:{i}")
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                                       capture_output=True, text=True).stdout)
            frames = math.ceil(dur * FPS)
            # A line starts at its cue, or a breath after the previous line if that one is still speaking.
            # If it would not end (plus MARGIN) by its deadline, the scene window [from, until] is slowed
            # by the fewest whole frames that make it fit (the window defaults to [at, until]).
            a, b = line.get("from", line["at"]), line["until"]
            add = 0
            while True:
                trial = stretch + ([(a, b, add)] if add else [])
                start = max(out_with(trial, line["at"]), prev_end + GAP)
                if start + frames + MARGIN <= out_with(trial, b):
                    break
                add += 1
            if add:
                stretch.append((a, b, add))
            prev_end = start + frames
            lufs, peak = loudness(mp3)
            note = f"  window {a}-{b} +{add} (speed {(b - a) / (b - a + add):.2f})" if add else ""
            print(f"{reel}:{i}  src {line['at']:>3}-{b:<3} out {round(start):>3}+{frames:<3} {dur:4.2f}s  "
                  f"{lufs:6.1f} LUFS  {peak:5.1f} dBFS{note}")
            table[reel]["lines"].append({"file": f"noor/vo/{reel}_{i}.mp3", "at": round(start), "frames": frames})
        table[reel]["stretch"] = [{"a": a, "b": b, "add": add} for a, b, add in stretch]

    if report:
        rep = HERE / "out" / f"vo_verify_{time.strftime('%Y%m%d-%H%M%S')}.json"
        rep.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"verification: {len(report)} transcripts, {sum(1 for r in report if r['problems'])} failed attempts -> {rep}")
    if failed:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\n✗ failed verification {ATTEMPTS}x: {', '.join(failed)} — vo_lines.ts left as it was;"
              f" retake with --retake {','.join(failed)}", file=sys.stderr)
        return 4
    ts = ["// Generated by scripts/gen_vo.py — do not edit by hand.",
          "// stretch: source frames [a, b] play over (b - a + add) output frames; lines: `at` is an OUTPUT frame.",
          "export type VoLine = {file: string; at: number; frames: number};",
          "export type VoPlan = {stretch: {a: number; b: number; add: number}[]; lines: VoLine[]};",
          "export const VO: Record<string, VoPlan> = " + json.dumps(table, ensure_ascii=False, indent="\t") + ";", ""]
    LINES_TS.write_text("\n".join(ts), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
