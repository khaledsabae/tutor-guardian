#!/usr/bin/env python3
"""
verify_videos — check rendered reels by their effect, not by the render's exit code.

For every MP4 given (or every MP4 in the directories given):
  * duration (ffprobe);
  * integrated loudness and true peak (ffmpeg ebur128, peak=true -> dBTP);
  * the end card's QR code, decoded with OpenCV from the last seconds of the
    video, must equal the URL in src/noor/campaign/qr.ts (campaign reels, by
    slug) or src/noor/qr.ts (teaser cuts: ar / world / en / wide);
  * a strip of frames (every few seconds) written next to --frames DIR, to
    look at by eye.

Needs opencv-python-headless (e.g. a venv: python3 -m venv /tmp/qrvenv &&
/tmp/qrvenv/bin/pip install opencv-python-headless numpy), run with that python.

Usage: /tmp/qrvenv/bin/python scripts/verify_videos.py [--frames DIR] PATH...
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parents[1]


def urls() -> dict[str, str]:
    out: dict[str, str] = {}
    for ts in [HERE / "src/noor/campaign/qr.ts", HERE / "src/noor/qr.ts"]:
        for key, url in re.findall(r'^\t(\w+): \{url: "([^"]+)"', ts.read_text(), re.M):
            out[key] = url
    return out


def expected(name: str, table: dict[str, str]) -> str | None:
    for slug in sorted(table, key=len, reverse=True):
        if name.startswith(slug):
            return table[slug]
    if name.startswith("noor_teaser_"):
        cut = name.removeprefix("noor_teaser_")
        # ar_world and ar_vo are both TeaserWorld, which carries the `world` code
        cut = ("wide" if cut.startswith("ar_wide") else "en" if cut.startswith("en")
               else "world" if cut.startswith(("ar_world", "ar_vo")) else "ar")
        return table.get(cut)
    return None


def probe(mp4: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                                capture_output=True, text=True, check=True).stdout)


def loudness(mp4: Path) -> tuple[float, float]:
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4), "-filter_complex", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    s = err[err.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)), float(re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", s).group(1))


def qr(mp4: Path, dur: float) -> str | None:
    det = cv2.QRCodeDetector()
    with tempfile.TemporaryDirectory() as tmp:
        for back in (0.4, 1.0, 2.0, 3.0):
            png = Path(tmp) / f"q{back}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, dur - back):.2f}", "-i", str(mp4), "-frames:v", "1", str(png)],
                           check=True)
            text, _, _ = det.detectAndDecode(cv2.imread(str(png)))
            if text:
                return text
    return None


def strip(mp4: Path, dur: float, out: Path) -> None:
    n = max(6, min(10, int(dur // 3)))
    ts = [dur * (i + 0.5) / n for i in range(n)]
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for i, t in enumerate(ts):
            f = Path(tmp) / f"{i:02d}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=-2:640", str(f)],
                           check=True)
            files.append(f)
        args = sum([["-i", str(f)] for f in files], [])
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", f"hstack=inputs={len(files)}", str(out)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=Path)
    ap.add_argument("paths", nargs="+", type=Path)
    a = ap.parse_args()
    files = sorted({f for p in a.paths for f in ([p] if p.is_file() else p.glob("*.mp4"))})
    table = urls()
    bad = 0
    if a.frames:
        a.frames.mkdir(parents=True, exist_ok=True)
    for f in files:
        dur = probe(f)
        lufs, peak = loudness(f)
        want = expected(f.stem, table)
        got = qr(f, dur)
        ok = want is not None and got == want
        bad += not ok
        print(f"{f.name:28s} {dur:6.2f} s  {lufs:6.1f} LUFS  {peak:5.1f} dBTP  QR {'OK' if ok else 'FAIL'}"
              + ("" if ok else f"  (got {got!r}, want {want!r})"))
        if a.frames:
            strip(f, dur, a.frames / f"{f.stem}.png")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
