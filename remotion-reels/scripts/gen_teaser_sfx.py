#!/usr/bin/env python3
"""
gen_teaser_sfx — the four soft sounds of the «نور» teaser, computed from code.

The owner's rule is «أصوات ناعمة بلا موسيقى»: no music, no instruments, no
bells, no melody. These are the same room sounds as the app's interface set
(ops/tools/gen_sfx.py on noor/p2-sound) — filtered noise, a breath of air, one
water drop, paper — re-voiced for video: 44.1 kHz, a little longer, and a
quiet night bed underneath.

  rustle      paper rustle         a hill sheet / bubble / card slides in
  rustle_long longer paper unfold  the paper path drawing itself
  air         soft air swell       a lantern being lit
  drop        one water drop       Noor turns happy
  night       night ambience       filtered-noise bed, seamless 8 s loop; file peak
                                   -20.5 dBFS, about -24 dBFS in the stereo mix

Added for the campaign reels (src/noor/campaign/), same rules:

  tick        soft paper tap       a fingertip on a card: a chip, a PIN dot, typing
  swish       paper door swing     the two paper doors of the hand-over gate open

Levels: files peak near full scale (the mix volumes in src/noor/sound.tsx
are all < 1); the whole mix lands near -23 LUFS with peaks around -6 dBFS.

Every file is an output of this script (fixed seeds) — never edited by hand.

Usage: python3 scripts/gen_teaser_sfx.py      (writes public/noor/sfx/*.wav)
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

OUT_DIR = Path(__file__).resolve().parents[1] / "public" / "noor" / "sfx"
SR = 44_100
FULL_SCALE = 32_767


def _t(ms: float) -> np.ndarray:
    return np.arange(int(round(SR * ms / 1000.0))) / SR


def _noise(n: int, seed: int) -> np.ndarray:
    """White noise in [-1, 1) from the raw PCG64 stream (stable across NumPy)."""
    raw = np.random.PCG64(seed).random_raw(n)
    return (raw >> np.uint64(11)).astype(np.float64) * (2.0 / 2**53) - 1.0


def _lp(x: np.ndarray, fc: float) -> np.ndarray:
    a = math.exp(-2.0 * math.pi * fc / SR)
    return lfilter([1.0 - a], [1.0, -a], x)


def _lp_sweep(x: np.ndarray, fc: np.ndarray) -> np.ndarray:
    a = np.exp(-2.0 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):
        acc = (1.0 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def _hp(x: np.ndarray, fc: float) -> np.ndarray:
    return x - _lp(x, fc)


def _bp(x: np.ndarray, f0: float, q: float) -> np.ndarray:
    w0 = 2.0 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2.0 * q)
    a0 = 1.0 + alpha
    return lfilter([alpha / a0, 0.0, -alpha / a0],
                   [1.0, -2.0 * math.cos(w0) / a0, (1.0 - alpha) / a0], x)


def _swell(n: int, peak_at: float) -> np.ndarray:
    u = np.linspace(0.0, 1.0, n)
    p = math.log(0.5) / math.log(peak_at)
    return np.sin(math.pi * u**p) ** 2


def _finish(x: np.ndarray, peak_dbfs: float, fade_in_ms: float,
            fade_out_ms: float) -> np.ndarray:
    x = x - x.mean()
    x = _hp(x, 40.0)
    x = x / max(1e-12, float(np.max(np.abs(x)))) * 10 ** (peak_dbfs / 20.0)
    n_in = max(2, int(SR * fade_in_ms / 1000.0))
    n_out = max(2, int(SR * fade_out_ms / 1000.0))
    x[:n_in] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, n_in))
    x[-n_out:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, math.pi, n_out))
    return x


def _paper(ms: float, peak_at: float, grain_rate: float, seed: int,
           peak_dbfs: float) -> np.ndarray:
    """A sweep of bright noise with sparse crinkle grains on it."""
    t = _t(ms)
    n = t.size
    env = _swell(n, peak_at)
    hiss = _hp(_bp(_noise(n, seed), 2_600.0, 0.6), 900.0)
    grains = np.zeros(n)
    picks = _noise(n, seed + 1) * 0.5 + 0.5
    amps = _noise(n, seed + 2) * 0.5 + 0.5
    grain_noise = _hp(_noise(n, seed + 3), 1_800.0)
    rate = grain_rate * env / SR
    width = int(SR * 0.0016)
    for i in np.nonzero(picks < rate)[0]:
        j = min(n, i + width)
        shape = np.exp(-np.arange(j - i) / (width / 4.0))
        grains[i:j] += (0.4 + 0.6 * amps[i]) * shape * grain_noise[i:j]
    uneven = np.clip(1.0 + 30.0 * _lp(_noise(n, seed + 4), 30.0), 0.6, 1.4)
    x = _lp((hiss * 0.7 + grains * 1.6) * env * uneven, 6_000.0)
    return _finish(x, peak_dbfs, 6.0, 60.0)


def rustle() -> np.ndarray:
    return _paper(420, 0.35, 150.0, 501, -1.0)


def rustle_long() -> np.ndarray:
    return _paper(1_400, 0.45, 90.0, 511, -2.0)


def air() -> np.ndarray:
    t = _t(560)
    n = t.size
    env = _swell(n, 0.40)
    cutoff = 280.0 + 1_500.0 * env
    air_ = _hp(_lp_sweep(_lp_sweep(_noise(n, 401), cutoff), cutoff), 130.0)
    flutter = np.clip(1.0 + 6.0 * _lp(_noise(n, 402), 25.0), 0.7, 1.3)
    return _finish(air_ * env * flutter, -1.0, 8.0, 80.0)


def drop() -> np.ndarray:
    """One water drop: a sine whose pitch rises as the bubble closes."""
    t = _t(240)
    f0, f1 = 650.0, 1_500.0
    freq = f0 + (f1 - f0) * (1.0 - np.exp(-t / 0.022))
    phase = 2.0 * math.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t / 0.042)
    plip = _hp(_noise(t.size, 301), 2_500.0) * np.exp(-t / 0.0015)
    return _finish(body + 0.12 * plip, -0.5, 2.0, 40.0)


def tick() -> np.ndarray:
    """A soft paper tap: a short bright touch over a low, damped knock."""
    t = _t(90)
    tap = _lp(_hp(_noise(t.size, 601), 1_200.0), 5_000.0) * np.exp(-t / 0.006)
    knock = np.sin(2.0 * math.pi * 210.0 * t) * np.exp(-t / 0.018) * 0.5
    return _finish(tap + knock, -1.0, 0.5, 30.0)


def swish() -> np.ndarray:
    """A paper door swinging open: a slow airy sweep with a little paper grain."""
    t = _t(700)
    n = t.size
    env = _swell(n, 0.45)
    cutoff = 400.0 + 2_600.0 * env
    sweep = _hp(_lp_sweep(_lp_sweep(_noise(n, 611), cutoff), cutoff), 200.0) * env
    sweep = sweep / max(1e-12, float(np.max(np.abs(sweep))))
    grain = _paper(700, 0.45, 60.0, 621, 0.0)
    return _finish(sweep + 0.35 * grain, -1.0, 10.0, 90.0)


NIGHT_SR = 22_050
NIGHT_LOOP_S = 8.0


def night() -> np.ndarray:
    """A low, still night bed: brown-ish noise with a slow breath in level.

    Written as a seamless 8 s loop at 22.05 kHz (its content sits below
    5 kHz), so the file stays small; the video loops it and fades it in and
    out with a volume curve, so the file itself carries no fades.
    """
    sr = NIGHT_SR
    n_loop = int(sr * NIGHT_LOOP_S)
    n_xf = sr  # 1 s crossfade
    n = n_loop + n_xf
    t = np.arange(n) / sr

    def lp(x, fc):
        a = math.exp(-2.0 * math.pi * fc / sr)
        return lfilter([1.0 - a], [1.0, -a], x)

    bed = lp(lp(_noise(n, 701), 380.0), 380.0)
    bed = bed - lp(bed, 70.0)
    bed = bed / np.max(np.abs(bed))
    sheen = lp(_noise(n, 702) - lp(_noise(n, 702), 2_500.0), 5_000.0) * 0.05
    x = bed + sheen
    # Equal-power crossfade of the tail into the head -> seamless loop.
    k = np.linspace(0.0, 1.0, n_xf)
    head = x[:n_xf] * np.sin(0.5 * math.pi * k) + x[n_loop:] * np.cos(0.5 * math.pi * k)
    loop = np.concatenate([head, x[n_xf:n_loop]])
    tl = np.arange(n_loop) / sr
    # Slow level wander whose periods divide the loop length (8 s, 4 s).
    wander = 0.84 + 0.10 * np.sin(2 * math.pi * tl / 8.0) + 0.06 * np.sin(2 * math.pi * tl / 4.0 + 1.1)
    loop = (loop - loop.mean()) * wander
    return loop / np.max(np.abs(loop)) * 10 ** (-20.5 / 20.0)


SOUNDS = {
    "rustle": rustle,
    "rustle_long": rustle_long,
    "air": air,
    "drop": drop,
    "night": night,
    "tick": tick,
    "swish": swish,
}


def _write(path: Path, x: np.ndarray, sr: int) -> np.ndarray:
    pcm = np.round(np.clip(x, -1.0, 1.0) * FULL_SCALE).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return pcm


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, recipe in SOUNDS.items():
        sr = NIGHT_SR if name == "night" else SR
        pcm = _write(OUT_DIR / f"{name}.wav", recipe(), sr)
        f = pcm.astype(np.float64) / FULL_SCALE
        peak = 20 * math.log10(max(1e-9, float(np.max(np.abs(f)))))
        rms = 20 * math.log10(max(1e-9, float(np.sqrt(np.mean(f**2)))))
        size = (OUT_DIR / f"{name}.wav").stat().st_size
        print(f"{name:12s} {1000 * pcm.size / sr:7.0f} ms  peak {peak:6.1f} dBFS"
              f"  rms {rms:6.1f} dBFS  {size / 1024:7.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
