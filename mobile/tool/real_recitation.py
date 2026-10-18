"""Real recitation for a ﴿verse﴾ quoted in a story — no TTS voice ever recites the Qur'an.

Khaled, 2026-10-18: «تلاوة حقيقية». A verse on a story page is cut from the
recitation the app's own Qur'an reader plays (lib/features/quran/models/reciters.dart,
kDefaultReciter): Mahmoud Khalil al-Husary, everyayah.com `Husary_128kbps`.

  1. locate — the quote must equal a run of whole words of one ayah in the
     mushaf the guards use (mobile/assets/data/quran.json), letter for letter
     after folding Uthmani vs. imla'i spelling (ٱ/ا, the dagger alif, hamza
     seats, آ = ءا) and dropping the marks. A phrase found in more than one
     ayah needs its place in recitation_refs.json; nothing is guessed.
  2. cut — at word boundaries, from the Quran Foundation word segments of
     recitation 6 (al-Husary), which are timed on the 64 kbps file of the same
     recording; the 128 kbps file runs OFFSET_MS later (measured by
     cross-correlation on six ayahs, r ≥ 0.997, 2026-10-18). Inside a real
     pause the cut sits in the silence; inside connected speech it sits on the
     quietest 5 ms next to the boundary, with a 12-15 ms fade. Never mid-word.
  3. loudness — the clip is brought to the integrated loudness of the page's
     own narration, peak kept under -1.5 dBFS.

Network: api.quran.com (segments) and everyayah.com (audio), cached under
~/.cache/tg-recitation. Usage terms: EveryAyah states none for the audio (its
timing files ask for a link back to versebyversequran.com); credit the source.
"""
from __future__ import annotations

import array
import json
import math
import re
import subprocess
import tempfile
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MUSHAF = ROOT / "mobile/assets/data/quran.json"
REFS = Path(__file__).with_name("recitation_refs.json")
CACHE = Path.home() / ".cache/tg-recitation"
RECITER = "Husary_128kbps"
AUDIO_URL = "https://everyayah.com/data/Husary_128kbps/{sura:03d}{ayah:03d}.mp3"
SEGMENTS_URL = "https://api.quran.com/api/v4/recitations/6/by_ayah/{sura}:{ayah}?fields=segments"
OFFSET_MS = 26.1
RATE = 24000
PAUSE_MS = 300            # a gap this long between two words is a real pause
PEAK_DBFS = -1.5

_MARKS = re.compile("[\u0610-\u061a\u064b-\u065f\u06d6-\u06ed\u08f0-\u08f3\u0640]")


class RecitationError(SystemExit):
    """The verse cannot be given its real recitation — stop rather than guess."""


def fold(word: str) -> str:
    w = word.replace("ىٰ", "ى").replace("\u0670", "ا").replace("\u0654", "ء").replace("آ", "ءا")
    w = _MARKS.sub("", w)
    return re.sub("[أإؤئ]", "ء", w).replace("ٱ", "ا")


def _mushaf() -> dict:
    return json.loads(MUSHAF.read_text(encoding="utf-8"))


def locate(quote: str, place: str | None = None) -> tuple[int, int, int, int]:
    """(sura, ayah, first word, last word) — 1-based word positions in the ayah."""
    target = "".join(fold(w) for w in quote.split())
    hits = []
    for sura, ayahs in _mushaf().items():
        for a in ayahs:
            words = a["text"].split()
            cat, bounds = "", []
            for w in words:
                bounds.append(len(cat))
                cat += fold(w)
            bounds.append(len(cat))
            i = cat.find(target)
            while i >= 0:
                if i in bounds and i + len(target) in bounds:
                    hits.append((int(sura), a["verse"], bounds.index(i) + 1, bounds.index(i + len(target))))
                i = cat.find(target, i + 1)
    if place:
        s, a = map(int, place.split(":"))
        hits = [h for h in hits if (h[0], h[1]) == (s, a)]
    if not hits:
        raise RecitationError(f"﴿{quote}﴾ is not a run of whole words of "
                              + (f"ayah {place}" if place else "any ayah") + " in the mushaf — fix the text, never the audio")
    if len(hits) > 1:
        raise RecitationError(f"﴿{quote}﴾ is in {len(hits)} ayahs ("
                              + ", ".join(f"{s}:{a}" for s, a, _, _ in hits)
                              + f") — name the one in {REFS.name}")
    return hits[0]


def place_for(story_id: str, page: int) -> str | None:
    refs = json.loads(REFS.read_text(encoding="utf-8")) if REFS.exists() else {}
    return refs.get(f"{story_id}/{page}")


def _fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "tutor-guardian-narration"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.rename(dest)
    return dest


def segments(sura: int, ayah: int) -> dict[int, tuple[int, int]]:
    """word position -> (start ms, end ms) on the 64 kbps file."""
    p = _fetch(SEGMENTS_URL.format(sura=sura, ayah=ayah), CACHE / "segments" / f"{sura:03d}{ayah:03d}.json")
    segs = json.loads(p.read_text())["audio_files"][0].get("segments") or []
    if not segs:
        raise RecitationError(f"no word segments for {sura}:{ayah} — cannot cut at word boundaries")
    return {int(s[1]): (int(s[2]), int(s[3])) for s in segs}


def decode(path: Path) -> array.array:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return array.array("h", raw[: len(raw) // 2 * 2])


def lufs(pcm: bytes) -> float:
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        with wave.open(f.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)
        err = subprocess.run(["ffmpeg", "-nostats", "-i", f.name, "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", err[err.rfind("Summary:"):]).group(1))


def _quietest(a: array.array, lo_ms: float, hi_ms: float) -> float:
    half = int(0.0025 * RATE)
    best = None
    for t in range(int(lo_ms), int(hi_ms) + 1, 2):
        i = int(t * RATE / 1000)
        seg = a[max(0, i - half):max(0, i + half)]
        e = sum(x * x for x in seg) / max(1, len(seg))
        if best is None or e < best[0]:
            best = (e, t)
    return best[1]


def cut(pcm: array.array, seg: dict[int, tuple[int, int]], w0: int, w1: int) -> tuple[array.array, dict]:
    """Words w0..w1 of an ayah's PCM, cut at word boundaries."""
    start, end = seg[w0][0] + OFFSET_MS, seg[w1][1] + OFFSET_MS
    before = seg[w0][0] - seg[w0 - 1][1] if w0 - 1 in seg else None
    after = seg[w1 + 1][0] - seg[w1][1] if w1 + 1 in seg else None
    total = len(pcm) * 1000 / RATE
    if before is None or before >= PAUSE_MS:
        a, fade_in = max(0.0, start - min(150, (before or 400) / 2)), 0.0
    else:
        a, fade_in = _quietest(pcm, start - 50, start + 30), 0.012
    if after is None or after >= PAUSE_MS:
        b, fade_out = min(total, end + min(350, (after or 700) / 2)), 0.0
    else:
        b, fade_out = _quietest(pcm, end - 30, end + 50), 0.015
    clip = pcm[int(a * RATE / 1000):int(b * RATE / 1000)]
    for n in range(int(fade_in * RATE)):
        clip[n] = int(clip[n] * n / (fade_in * RATE))
    for n in range(int(fade_out * RATE)):
        clip[-1 - n] = int(clip[-1 - n] * n / (fade_out * RATE))
    return clip, {"cut_ms": [round(a), round(b)], "pause_before_ms": before, "pause_after_ms": after}


def match_loudness(pcm: bytes, target: float) -> bytes:
    a = array.array("h", pcm)
    lin = 10 ** ((target - lufs(pcm)) / 20)
    limit = 32767 * 10 ** (PEAK_DBFS / 20)
    peak = max((abs(x) for x in a), default=0) * lin
    if peak > limit:
        lin *= limit / peak
    return array.array("h", (max(-32767, min(32767, int(x * lin))) for x in a)).tobytes()


def recitation(quote: str, place: str | None, target_lufs: float, trim) -> tuple[bytes, dict]:
    """The real recitation of [quote], as 16-bit mono PCM at 24 kHz, loudness-matched."""
    sura, ayah, w0, w1 = locate(quote, place)
    mp3 = _fetch(AUDIO_URL.format(sura=sura, ayah=ayah), CACHE / RECITER / f"{sura:03d}{ayah:03d}.mp3")
    clip, info = cut(decode(mp3), segments(sura, ayah), w0, w1)
    words = _mushaf()[str(sura)][ayah - 1]["text"].split()[w0 - 1:w1]
    info.update({"ref": f"{sura}:{ayah}", "words": [w0, w1], "source": f"everyayah.com/{RECITER}",
                 "mushaf": " ".join(words)})
    return match_loudness(trim(clip.tobytes()), target_lufs), info
