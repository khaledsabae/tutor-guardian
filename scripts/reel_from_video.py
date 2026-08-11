#!/usr/bin/env python3
"""
مصنع الريلز — v2: يقصّ من فيديوهات المنهج بدل توليد صورة ثابتة
================================================================

الفرق عن `podcast_to_reel.py`:

  القديم: صورة ثابتة واحدة (`-loop 1`) مهبّبة 18px + صوت بودكاست + ترجمة
          تعتمد على ملفات .srt غير موجودة أصلًا — فالناتج ٣٠ ثانية من صورة
          مجمّدة بلا نص، والدعوة للتحميل تظهر في آخر ثانيتين.

  الجديد: مقطع حقيقي من فيديوهات المسارات/الدروس — فيها حركة وسرد عربي
          أصلي — مؤطَّر رأسيًا 9:16، بترجمة محروقة (أغلب المشاهدين يشاهدون
          بلا صوت)، وخطّاف في أول ثانيتين.

الاستخدام:
  python3 scripts/reel_from_video.py --list
  python3 scripts/reel_from_video.py --source docs/path_videos/path_4-6_islamic_parenting_adab_ar_eg.mp4
  python3 scripts/reel_from_video.py --source <file> --start 95 --duration 30

المتطلبات: ffmpeg + ffprobe، و(اختياري) whisper للترجمة التلقائية.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "marketing" / "reels_v2"
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"

W, H = 1080, 1920
BRAND = "المربّي الذكي"
CTA_LINES = ["حمّل «المربّي الذكي» مجانًا", "بلا إعلانات ولا اشتراكات"]


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe_duration(path) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "csv=p=0", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def sources() -> list[Path]:
    """Narrated curriculum videos, longest first — more segments to choose from."""
    found = list((ROOT / "docs" / "path_videos").glob("*.mp4"))
    found += list((ROOT / "docs").glob("*_video.mp4"))
    return sorted((p for p in found if probe_duration(p) > 60), key=probe_duration, reverse=True)


def _escape(text: str) -> str:
    """drawtext eats these; '%' has no working escape so it goes.

    Parentheses render as tofu in NotoSansArabic at these sizes, and every path
    title ends with an age band in them — "(10-12 سنة)" came out as a box on
    screen. Arabic-script brackets have glyphs, so swap rather than drop.
    """
    return (text.replace("\\", "").replace("%", "").replace(":", "\\:")
                .replace("'", "’").replace(",", "\\,")
                .replace("(", "﴿").replace(")", "﴾"))


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def transcribe(video: Path, start: float, duration: float, workdir: Path, model: str = "small") -> list[dict]:
    """Arabic captions for the chosen window. Silent no-op without whisper."""
    whisper = shutil.which("whisper")
    if not whisper:
        print("  (whisper غير مثبّت — بلا ترجمة محروقة)")
        return []
    clip = workdir / "seg.wav"
    _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", str(start),
          "-t", str(duration), "-i", str(video), "-ar", "16000", "-ac", "1", str(clip)])
    _run([whisper, str(clip), "--model", model, "--language", "ar",
          "--task", "transcribe", "--output_format", "srt",
          "--output_dir", str(workdir), "--fp16", "False"])
    srt = workdir / "seg.srt"
    if not srt.exists():
        return []
    out, block = [], srt.read_text(encoding="utf-8").strip().split("\n\n")
    for b in block:
        lines = b.strip().split("\n")
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):([\d.,]+)\s*-->\s*(\d+):(\d+):([\d.,]+)", lines[1])
        if not m:
            continue
        def secs(h, mi, s):
            return int(h) * 3600 + int(mi) * 60 + float(s.replace(",", "."))
        out.append({
            "start": secs(*m.groups()[:3]),
            "end": secs(*m.groups()[3:]),
            "text": " ".join(lines[2:]).strip(),
        })
    return out


def curriculum_copy(video: Path) -> tuple[str, list[str]]:
    """The path title and its lesson titles, as already written by a human.

    The frame is 9:16 and the footage is 16:9, so roughly 40% of the screen is
    letterbox. Filling it with machine transcription was worse than silence —
    whisper produced "لو المفتاح ضداء كل حاجة" — but this text already exists
    in the curriculum, written properly, and describes exactly what is on
    screen.
    """
    stem = video.stem.replace("_ar_eg", "")
    base = ROOT / "knowledge_base" / "curriculum"
    title, lessons = "", []

    path_file = base / "paths" / f"{stem}.json"
    if path_file.exists():
        data = json.loads(path_file.read_text(encoding="utf-8"))
        title = data.get("title", "")
        for lid in data.get("lesson_ids", []):
            lf = base / "lessons" / f"{lid}.json"
            if not lf.exists():
                continue
            ld = json.loads(lf.read_text(encoding="utf-8"))
            t = (ld.get("title_ar") or ld.get("title") or "").strip()
            if t:
                lessons.append(t)
    return title, lessons


def pick_segment(video: Path, duration: float) -> float:
    """Start offset that skips the title card and lands mid-explanation."""
    total = probe_duration(video)
    # The opening ~15s is branding//title on these videos; the tail trails off.
    lo, hi = 20.0, max(25.0, total - duration - 15.0)
    # A third of the way in is reliably mid-topic rather than intro or outro.
    return min(hi, max(lo, total * 0.33))


def build_filter(caps: list[dict], hook: str, duration: float) -> str:
    chains = []
    # The source is 16:9. Fill the vertical frame with a blurred, darkened copy
    # of itself, and lay the real footage across the middle — so the motion the
    # video already has is what the viewer sees, not a frozen still.
    chains.append(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},boxblur=26:26,eq=brightness=-0.42:contrast=1.06[bg]")
    chains.append(f"[0:v]scale={W}:-2[fg]")
    chains.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    last = "[base]"

    chains.append(f"{last}drawbox=y=0:x=0:width={W}:height=10:color=0xF59E0B:t=fill[bar]")
    last = "[bar]"
    chains.append(f"{last}drawtext=text='{_escape(BRAND)}':fontfile={FONT_BOLD}:"
                  f"fontsize=48:fontcolor=white:borderw=3:bordercolor=black:"
                  f"x=w-tw-48:y=42[brand]")
    last = "[brand]"

    # Hook — the first two seconds decide whether anyone stays.
    for i, line in enumerate(_wrap(hook, 24)):
        y = 250 + i * 96
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                      f"fontsize=76:fontcolor=0xFDE68A:borderw=6:bordercolor=0x111111:"
                      f"x=(w-tw)/2:y={y}:enable='between(t\\,0\\,3.2)'[hook{i}]")
        last = f"[hook{i}]"

    # Captions, low in the frame so the footage stays visible.
    n = 0
    cta_from = max(0.0, duration - 4.0)
    for cap in caps:
        # Captions stop before the CTA so the two never share the frame.
        if cap["start"] >= min(duration, cta_from):
            break
        for idx, line in enumerate(_wrap(cap["text"], 26)):
            y = int(H * 0.66) + idx * 88
            chains.append(
                f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                f"fontsize=64:fontcolor=white:borderw=6:bordercolor=0x111111:"
                f"box=1:boxcolor=0x000000@0.35:boxborderw=18:"
                f"x=(w-tw)/2:y={y}:"
                f"enable='between(t\\,{cap['start']:.2f}\\,{min(cap['end'], cta_from):.2f})'[c{n}]")
            last = f"[c{n}]"
            n += 1

    # CTA over the final seconds.
    for i, line in enumerate(CTA_LINES):
        y = int(H * 0.40) + i * 84
        size = 66 if i == 0 else 52
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD if i == 0 else FONT_REG}:"
                      f"fontsize={size}:fontcolor=white:borderw=5:bordercolor=0x111111:"
                      f"x=(w-tw)/2:y={y}:enable='gte(t\\,{cta_from:.2f})'[cta{i}]")
        last = f"[cta{i}]"

    chains.append(f"{last}null[v]")
    return ";".join(chains)


def render(video: Path, start: float, duration: float, hook: str, out: Path, captions: str = "off") -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        caps = transcribe(video, start, duration, work, captions) if captions != "off" else []
        print(f"  ترجمة: {len(caps)} سطر" if caps else "  ترجمة: مطفية")
        fc = build_filter(caps, hook, duration)
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
               "-ss", str(start), "-t", str(duration), "-i", str(video),
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-r", "30",
               "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)]
        r = _run(cmd)
        if r.returncode != 0:
            print("  ✗ ffmpeg:", r.stderr[-700:])
            return False
    return True



def montage_filter(cuts: list[tuple[float, float]], hook: str, duration: float,
                   title: str = "", points: list[str] | None = None) -> str:
    """Cross-cut several moments so the frame changes every few seconds.

    A single 30s window lands on one slide: these videos hold each slide for
    a minute or more, so cutting once gives a still image with narration over
    it — which is the problem the old generator had. Sampling across the whole
    video means a new illustration every few seconds instead.
    """
    chains, segs = [], []
    for i, (st, dur) in enumerate(cuts):
        chains.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H},boxblur=26:26,eq=brightness=-0.42:contrast=1.06[bg{i}]")
        chains.append(f"[{i}:v]scale={W}:-2[fg{i}]")
        chains.append(f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[s{i}]")
        segs.append(f"[s{i}]")
    chains.append("".join(segs) + f"concat=n={len(cuts)}:v=1:a=0[joined]")
    last = "[joined]"

    chains.append(f"{last}drawbox=y=0:x=0:width={W}:height=10:color=0xF59E0B:t=fill[bar]")
    last = "[bar]"
    chains.append(f"{last}drawtext=text='{_escape(BRAND)}':fontfile={FONT_BOLD}:"
                  f"fontsize=48:fontcolor=white:borderw=3:bordercolor=black:x=w-tw-48:y=42[brand]")
    last = "[brand]"

    for i, line in enumerate(_wrap(hook, 24)):
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                      f"fontsize=76:fontcolor=0xFDE68A:borderw=6:bordercolor=0x111111:"
                      f"x=(w-tw)/2:y={250 + i * 96}:enable='between(t\\,0\\,3.0)'[hk{i}]")
        last = f"[hk{i}]"

    # Upper letterbox: the path title, once the hook has cleared.
    for i, line in enumerate(_wrap(title, 26)):
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                      f"fontsize=58:fontcolor=white:borderw=5:bordercolor=0x111111:"
                      f"x=(w-tw)/2:y={300 + i * 74}:enable='gt(t\\,3.2)'[ttl{i}]")
        last = f"[ttl{i}]"

    # Lower letterbox: one lesson title at a time, so the empty band carries
    # the actual curriculum instead of blurred grey.
    pts = points or []
    if pts:
        window = max(3.0, (duration - 4.0) / len(pts))
        for i, pt in enumerate(pts):
            st, en = 3.2 + i * window, min(duration - 4.0, 3.2 + (i + 1) * window)
            if st >= en:
                break
            for idx, line in enumerate(_wrap(pt, 24)):
                chains.append(
                    f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                    f"fontsize=60:fontcolor=0xFDE68A:borderw=5:bordercolor=0x111111:"
                    f"x=(w-tw)/2:y={int(H * 0.755) + idx * 78}:"
                    f"enable='between(t\\,{st:.2f}\\,{en:.2f})'[pt{i}_{idx}]")
                last = f"[pt{i}_{idx}]"

    cta_from = max(0.0, duration - 4.0)
    for i, line in enumerate(CTA_LINES):
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD if i == 0 else FONT_REG}:"
                      f"fontsize={66 if i == 0 else 52}:fontcolor=white:borderw=5:bordercolor=0x111111:"
                      f"x=(w-tw)/2:y={int(H * 0.40) + i * 84}:enable='gte(t\\,{cta_from:.2f})'[ct{i}]")
        last = f"[ct{i}]"

    chains.append(f"{last}null[v]")
    return ";".join(chains)


def render_montage(video: Path, duration: float, hook: str, out: Path, n_cuts: int = 6) -> bool:
    """Build the reel from evenly spread moments, keeping the original audio bed."""
    total = probe_duration(video)
    per = duration / n_cuts
    # Spread across the body of the video, skipping the title card and the outro.
    lo, hi = total * 0.12, total * 0.88
    cuts = [(lo + i * (hi - lo) / n_cuts, per) for i in range(n_cuts)]
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y"]
    for st, dur in cuts:
        cmd += ["-ss", f"{st:.2f}", "-t", f"{dur:.2f}", "-i", str(video)]
    # Narration from one continuous stretch — chopped audio would be unlistenable.
    cmd += ["-ss", f"{lo:.2f}", "-t", f"{duration:.2f}", "-i", str(video)]
    title, points = curriculum_copy(video)
    cmd += ["-filter_complex", montage_filter(cuts, hook, duration, title, points),
            "-map", "[v]", "-map", f"{len(cuts)}:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(out)]
    r = _run(cmd)
    if r.returncode != 0:
        print("  \u2717 ffmpeg:", r.stderr[-700:])
        return False
    print(f"  مونتاج: {n_cuts} قصّات، تغيّر كل {per:.1f}s"
          + (f" · نص المنهج: {len(points)} نقطة" if points else " · بلا نص منهج"))
    return True

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="اعرض المصادر المتاحة")
    ap.add_argument("--source", help="مسار فيديو المصدر")
    ap.add_argument("--start", type=float, help="بداية المقطع بالثواني")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--hook", default="", help="نص الخطّاف في أول ثانيتين")
    ap.add_argument("--captions", choices=["off","base","small","medium"], default="off",
                    help="ترجمة محروقة. base رديء جدًا مع العربي — small فما فوق أو off")
    ap.add_argument("--out", help="مسار الناتج")
    ap.add_argument("--montage", type=int, default=0,
                    help="عدد القصّات — يمنع وقوع الريل على شريحة واحدة ثابتة")
    args = ap.parse_args()

    srcs = sources()
    if args.list or not args.source:
        print(f"مصادر مسرودة متاحة: {len(srcs)}\n")
        for p in srcs[:15]:
            print(f"  {probe_duration(p):6.0f}s  {p.relative_to(ROOT)}")
        if not args.source:
            return 0
        return 0

    video = Path(args.source)
    if not video.is_absolute():
        video = ROOT / video
    if not video.exists():
        print(f"غير موجود: {video}")
        return 1

    start = args.start if args.start is not None else pick_segment(video, args.duration)
    hook = args.hook or "دقيقة واحدة تفرق في تربية ابنك"
    out = Path(args.out) if args.out else OUT_DIR / f"reel_{video.stem}_{int(start)}.mp4"

    print(f"المصدر : {video.name}")
    print(f"المقطع : {start:.0f}s → {start + args.duration:.0f}s  (من {probe_duration(video):.0f}s)")
    ok = (render_montage(video, args.duration, hook, out, args.montage)
          if args.montage else render(video, start, args.duration, hook, out, args.captions))
    if not ok:
        return 1
    print(f"✅ {out}  ({out.stat().st_size / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
