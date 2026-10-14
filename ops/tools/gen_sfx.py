#!/usr/bin/env python3
"""
gen_sfx — synthesise the app's five interface sounds from code.

The owner's decision is «أصوات ناعمة بلا موسيقى»: soft sounds, no music. So
there are no instruments here, no melody, no bells or chimes — those are
debated in fiqh for this audience, and a sound effect is not worth the
debate. What is allowed is what a room already makes: filtered noise, a soft
click, a breath of air, one water drop, a page turning.

Every sound is computed below from a fixed seed, so the files under
mobile/assets/audio/sfx/ are an *output* of this script — never downloaded,
never edited by hand. Change a sound by changing its recipe and re-running.

  tap      soft click               (Haptics has no tap helper yet; kept ready)
  select   tiny tick                (Haptics.selection)
  success  one water drop           (Haptics.success)
  lantern  soft air swell           (a light being lit — wired later)
  page     paper rustle             (a page turned — wired later)

Format: WAV, PCM 16-bit, mono, 22 050 Hz. At ≤ 400 ms that is ≤ 17.7 KB, well
under the 30 KB budget, and Android's SoundPool (audioplayers' low-latency
mode) decodes it with no codec in the way.

Usage:
  .venv/bin/python ops/tools/gen_sfx.py           # write the five files
  .venv/bin/python ops/tools/gen_sfx.py --check   # verify the committed files

--check fails if a file breaks a limit (size, length, peak, mono/rate, a
click at either end) or no longer matches what the recipe produces (±1 LSB,
which absorbs last-ulp float differences between machines).
"""
from __future__ import annotations

import argparse
import io
import math
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "mobile" / "assets" / "audio" / "sfx"

SR = 22_050
MAX_MS = 400
MAX_BYTES = 30 * 1024
MAX_PEAK_DBFS = -12.0
FULL_SCALE = 32_767


# ── primitives ────────────────────────────────────────────────────────────


def _t(ms: float) -> np.ndarray:
    return np.arange(int(round(SR * ms / 1000.0))) / SR


def _noise(n: int, seed: int) -> np.ndarray:
    """Uniform white noise in [-1, 1) from the *raw* PCG64 bit stream.

    NumPy promises the bit generator's stream is stable across versions; the
    distribution helpers on top of it are not promised. Drawing from the raw
    stream keeps the committed files reproducible on a newer NumPy.
    """
    raw = np.random.PCG64(seed).random_raw(n)
    return (raw >> np.uint64(11)).astype(np.float64) * (2.0 / 2**53) - 1.0


def _lowpass(x: np.ndarray, cutoff_hz) -> np.ndarray:
    """One-pole low-pass; `cutoff_hz` may be a per-sample array (a sweep)."""
    fc = np.broadcast_to(np.asarray(cutoff_hz, dtype=np.float64), x.shape)
    a = np.exp(-2.0 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):
        acc = (1.0 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def _highpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    return x - _lowpass(x, cutoff_hz)


def _bandpass(x: np.ndarray, f0: float, q: float) -> np.ndarray:
    """RBJ biquad band-pass (0 dB peak gain)."""
    w0 = 2.0 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2.0 * q)
    b0, b2 = alpha, -alpha
    a0, a1, a2 = 1.0 + alpha, -2.0 * math.cos(w0), 1.0 - alpha
    b0, b2, a1, a2 = b0 / a0, b2 / a0, a1 / a0, a2 / a0
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(x.size):
        xi = x[i]
        yi = b0 * xi + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, xi
        y2, y1 = y1, yi
        y[i] = yi
    return y


def _swell(n: int, peak_at: float) -> np.ndarray:
    """A smooth 0 → 1 → 0 hump peaking at fraction `peak_at` of the length."""
    u = np.linspace(0.0, 1.0, n)
    p = math.log(0.5) / math.log(peak_at)
    return np.sin(math.pi * u**p) ** 2


def _finish(x: np.ndarray, peak_dbfs: float, fade_in_ms: float,
            fade_out_ms: float) -> np.ndarray:
    """DC-block, normalise to the target peak, then raised-cosine fades.

    The fades pin the first and last samples to exactly zero, so no sound
    starts or ends on a step — the click the brief rules out.
    """
    x = x - x.mean()
    x = _highpass(x, 40.0)
    x = x / max(1e-12, float(np.max(np.abs(x)))) * 10 ** (peak_dbfs / 20.0)
    n_in = max(2, int(SR * fade_in_ms / 1000.0))
    n_out = max(2, int(SR * fade_out_ms / 1000.0))
    x[:n_in] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, n_in))
    x[-n_out:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, math.pi, n_out))
    return x


# ── recipes ───────────────────────────────────────────────────────────────


def tap() -> np.ndarray:
    """Soft click: a short breath of band-limited noise, no tuned body."""
    t = _t(70)
    n = t.size
    body = _lowpass(_bandpass(_noise(n, 101), 1_100.0, 0.8), 2_200.0)
    thud = _lowpass(_lowpass(_noise(n, 102), 500.0), 500.0)
    x = body * np.exp(-t / 0.006) + 2.5 * thud * np.exp(-t / 0.010)
    return _finish(x, -15.0, 1.0, 25.0)


def select() -> np.ndarray:
    """Tiny tick: a few milliseconds of high, narrow noise."""
    t = _t(35)
    x = _bandpass(_noise(t.size, 201), 3_600.0, 1.2) * np.exp(-t / 0.0025)
    return _finish(x, -18.0, 0.6, 12.0)


def success() -> np.ndarray:
    """One water drop: a sine whose pitch rises as the bubble closes.

    That rising glide is what makes a drop read as water rather than a note:
    it is one event, not a tone you could hum.
    """
    t = _t(220)
    f0, f1 = 650.0, 1_500.0
    freq = f0 + (f1 - f0) * (1.0 - np.exp(-t / 0.022))
    phase = 2.0 * math.pi * np.cumsum(freq) / SR
    drop = np.sin(phase) * np.exp(-t / 0.042)
    plip = _highpass(_noise(t.size, 301), 2_500.0) * np.exp(-t / 0.0015)
    return _finish(drop + 0.12 * plip, -14.0, 2.0, 30.0)


def lantern() -> np.ndarray:
    """Soft air swell: breath-like noise that opens and closes."""
    t = _t(380)
    n = t.size
    env = _swell(n, 0.42)
    cutoff = 300.0 + 1_600.0 * env
    # Two one-pole stages (12 dB/oct): one alone leaves a hiss on top of the
    # breath, which reads as static rather than air.
    air = _highpass(_lowpass(_lowpass(_noise(n, 401), cutoff), cutoff), 140.0)
    flutter = 1.0 + 0.15 * _lowpass(_noise(n, 402), 25.0) * 40.0
    return _finish(air * env * np.clip(flutter, 0.7, 1.3), -16.0, 5.0, 40.0)


def page() -> np.ndarray:
    """Paper rustle: a sweep of bright noise with crinkle grains on it."""
    t = _t(300)
    n = t.size
    env = _swell(n, 0.35)
    hiss = _highpass(_bandpass(_noise(n, 501), 3_000.0, 0.6), 1_200.0)

    # Crinkle: sparse 1–2 ms grains, denser in the middle of the turn.
    grains = np.zeros(n)
    picks = _noise(n, 502) * 0.5 + 0.5
    amps = _noise(n, 503) * 0.5 + 0.5
    grain_noise = _highpass(_noise(n, 504), 2_000.0)
    rate = 140.0 * env / SR
    width = int(SR * 0.0015)
    for i in np.nonzero(picks < rate)[0]:
        j = min(n, i + width)
        shape = np.exp(-np.arange(j - i) / (width / 4.0))
        grains[i:j] += (0.4 + 0.6 * amps[i]) * shape * grain_noise[i:j]

    unevenness = np.clip(1.0 + 30.0 * _lowpass(_noise(n, 505), 40.0), 0.6, 1.4)
    x = _lowpass((hiss * 0.8 + grains * 1.6) * env * unevenness, 6_500.0)
    return _finish(x, -16.0, 4.0, 35.0)


SOUNDS = {
    "tap": tap,
    "select": select,
    "success": success,
    "lantern": lantern,
    "page": page,
}


# ── I/O and checks ────────────────────────────────────────────────────────


def _to_pcm(x: np.ndarray) -> np.ndarray:
    return np.round(np.clip(x, -1.0, 1.0) * FULL_SCALE).astype("<i2")


def _wav_bytes(pcm: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _read(path: Path) -> tuple[np.ndarray, int, int, int]:
    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
        return (np.frombuffer(frames, dtype="<i2"), w.getnchannels(),
                w.getframerate(), w.getsampwidth())


def _describe(name: str, pcm: np.ndarray, size: int) -> str:
    ms = 1000.0 * pcm.size / SR
    peak = float(np.max(np.abs(pcm.astype(np.int32)))) / FULL_SCALE
    dbfs = 20.0 * math.log10(max(peak, 1e-9))
    return f"{name:8s} {size:6d} B  {ms:5.0f} ms  peak {dbfs:6.1f} dBFS"


def generate() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, recipe in SOUNDS.items():
        pcm = _to_pcm(recipe())
        data = _wav_bytes(pcm)
        (OUT_DIR / f"{name}.wav").write_bytes(data)
        print(_describe(name, pcm, len(data)))
    return 0


def check() -> int:
    problems: list[str] = []
    for name, recipe in SOUNDS.items():
        path = OUT_DIR / f"{name}.wav"
        if not path.exists():
            problems.append(f"{name}: missing ({path})")
            continue
        size = path.stat().st_size
        pcm, channels, rate, width = _read(path)
        print(_describe(name, pcm, size))
        if (channels, rate, width) != (1, SR, 2):
            problems.append(f"{name}: want mono/{SR} Hz/16-bit, got "
                            f"{channels} ch/{rate} Hz/{8 * width}-bit")
        if size > MAX_BYTES:
            problems.append(f"{name}: {size} B > {MAX_BYTES} B")
        if 1000.0 * pcm.size / SR > MAX_MS:
            problems.append(f"{name}: longer than {MAX_MS} ms")
        peak = float(np.max(np.abs(pcm.astype(np.int32)))) / FULL_SCALE
        if 20.0 * math.log10(max(peak, 1e-9)) > MAX_PEAK_DBFS:
            problems.append(f"{name}: peak above {MAX_PEAK_DBFS} dBFS")
        if pcm.size and (abs(int(pcm[0])) > 0 or abs(int(pcm[-1])) > 0):
            problems.append(f"{name}: does not start and end on silence")
        fresh = _to_pcm(recipe())
        if fresh.size != pcm.size or np.max(
                np.abs(fresh.astype(np.int32) - pcm.astype(np.int32))) > 1:
            problems.append(f"{name}: differs from its recipe — re-run "
                            "gen_sfx.py and commit the output")
    for p in problems:
        print(f"FAIL {p}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the committed files instead of writing")
    args = ap.parse_args()
    return check() if args.check else generate()


if __name__ == "__main__":
    sys.exit(main())
