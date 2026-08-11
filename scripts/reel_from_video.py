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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "marketing" / "reels_v2"
HOOKS_FILE = ROOT / "docs" / "marketing" / "reel_hooks.json"
LOGO = ROOT / "mobile" / "assets" / "images" / "logo.png"
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"

W, H = 1080, 1920
BRAND = "المربّي الذكي"
CTA_LINES = ["حمّل التطبيق مجانًا", "بلا إعلانات ولا اشتراكات"]
# بالعربية عمدًا: خط نوتو العربي بلا محارف لاتينية، و"Google Play" تخرج مربّعات.
CTA_STORE = "متاح على جوجل بلاي"
END_CARD = 4.6  # آخر ثوانٍ يحجبها كارت الهوية

# مصادر المنهج مولَّدة بـNotebookLM وتحمل علامته أسفل اليسار — قصّ الشريط
# السفلي يمنع نشر إعلان لمنتج آخر مع كل ريل.
SRC_KEEP = 0.90

# ألوان الهوية — منقولة من mobile/lib/theme/design_tokens.dart لتطابق ما يراه
# الأب داخل التطبيق. كارت النهاية يبقى بلون العلامة دائمًا مهما كان المجال.
BRAND_TEAL, BRAND_DEEP = "0x0D9488", "0x0F766E"
GOLD = "0xFBBF24"

# (لون التمييز، درجة اللون للخلفية، تشبّعها) — الدرجة محسوبة من نفس اللون.
DOMAIN_LOOK = {
    "aqeedah":           ("0x01696F", 183, 0.80),
    "islamic_parenting": ("0x10B981", 160, 0.78),
    "islamic":           ("0x10B981", 160, 0.78),
    "development":       ("0x8B5CF6", 263, 0.70),
    "medical":           ("0xFBBF24", 43, 0.80),
    "cyber":             ("0x3B82F6", 224, 0.76),
}
FALLBACK_LOOK = (BRAND_TEAL, 175, 0.78)


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


def hook_for(video: Path) -> str:
    """The written hook for this path, if there is one.

    The first two seconds decide whether a parent keeps watching, and that is
    marketing copy — not something to derive from a title. They live in
    reel_hooks.json so they can be rewritten without touching code.
    """
    if not HOOKS_FILE.exists():
        return ""
    hooks = json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    return hooks.get(video.stem.replace("_ar_eg", ""), "")


PLAY_URL = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
HASHTAGS = "#تربية_الأبناء #المربي_الذكي #تربية_إسلامية #الأمومة_والطفولة"


def caption_for(video: Path, hook: str, title: str, age: str) -> str:
    """The post text that travels with the reel.

    Built here rather than left to the publisher's generic fallback: every reel
    posted so far carried the same "نصيحة تربوية" boilerplate, which told a
    reader nothing about the reel they had just watched.
    """
    lines = [hook, ""]
    lines.append(f"{title} — {age}" if age else title)
    lines += [
        "من مسارات «المربّي الذكي»: منهج تربية متدرّج حسب سن طفلك،",
        "من الولادة إلى 18 سنة.",
        "",
        "حمّله مجانًا — بلا إعلانات ولا اشتراكات:",
        PLAY_URL,
        "",
        HASHTAGS,
    ]
    return "\n".join(lines)


def record(video: Path, out: Path, hook: str, title: str, age: str) -> None:
    """Append this reel to the manifest the publisher reads.

    Status starts at "new" and nothing publishes it: the publisher is a separate
    command, deliberately, so no run both makes a reel and posts it before a
    human has seen it.
    """
    manifest = OUT_DIR / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {"rendered": []}
    rendered = data.setdefault("rendered", [])
    entry = {
        "path_id": video.stem.replace("_ar_eg", ""),
        "title": title,
        "age": age,
        "hook": hook,
        "file": out.name,
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "status": "new",
        "caption": caption_for(video, hook, title, age),
    }
    for i, e in enumerate(rendered):
        if e.get("file") == out.name:
            entry["status"] = e.get("status", "new")
            rendered[i] = entry
            break
    else:
        rendered.append(entry)
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def domain_look(video: Path) -> tuple[str, int, float]:
    """The app's colour for this path's domain.

    Every path name carries its domain — `path_7-9_islamic_parenting_akhlaq`.
    Tinting the frame with the same colour the app uses for that domain means a
    parent who has seen the app recognises it, and it gives a feed of reels
    variety without anyone picking colours per video.
    """
    rest = re.sub(r"^path_[\d\-]+_", "", video.stem.replace("_ar_eg", ""))
    for key in ("aqeedah", "islamic_parenting", "islamic", "development", "medical", "cyber"):
        if rest.startswith(key):
            return DOMAIN_LOOK[key]
    return FALLBACK_LOOK


def frame_band(video: Path) -> tuple[int, int]:
    """Where the footage sits once scaled to the frame width.

    Needed to draw the accent rules exactly on its edges: a hairline that misses
    by a few pixels reads as a rendering fault, not a border.
    """
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)])
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except ValueError:
        w, h = 16, 9
    scaled = int(round(W * (h * SRC_KEEP) / w)) // 2 * 2
    top = max(0, (H - scaled) // 2)
    return top, min(H, top + scaled)


def _circle(idx: str, size: int, label: str) -> str:
    """The square app icon as a round badge — a hard-edged square over footage
    reads as a pasted-on screenshot."""
    r = size / 2
    return (f"[{idx}]scale={size}:{size},format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
            f"a='if(lte(hypot(X-{r:.1f}\\,Y-{r:.1f})\\,{r - 1:.1f})\\,255\\,0)'[{label}]")


def _chrome(last: str, accent: str, band: tuple[int, int]) -> tuple[list[str], str]:
    """Accent bar, rules on the footage edges, and the brand name."""
    top, bot = band
    chains = [
        f"{last}drawbox=x=0:y=0:w={W}:h=14:color={accent}:t=fill,"
        f"drawbox=x=0:y={max(0, top - 4)}:w={W}:h=4:color={accent}@0.85:t=fill,"
        f"drawbox=x=0:y={bot}:w={W}:h=4:color={accent}@0.85:t=fill[chrome]",
        f"[chrome]drawtext=text='{_escape(BRAND)}':fontfile={FONT_BOLD}:"
        f"fontsize=46:fontcolor=white:borderw=3:bordercolor=black@0.6:"
        f"x=w-tw-196:y=62[brand]",
    ]
    return chains, "[brand]"


def split_age(title: str) -> tuple[str, str]:
    """Lift the age band out of the title and onto its own line.

    Every curriculum title ends in one — "تزكية الأخلاق… (7-9 سنوات)". Left
    inline it wrapped mid-bracket, so a line came out reading "﴾سنوات". It also
    deserves its own line: a parent scanning the feed decides on the age first.
    """
    m = re.search(r"[(﴿]([^)﴾]*)[)﴾]\s*$", title)
    if not m:
        return title.strip(), ""
    return title[:m.start()].strip(), m.group(1).strip()


def _hook_layers(last: str, hook: str) -> tuple[list[str], str]:
    chains = []
    for i, line in enumerate(_wrap(hook, 24)):
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                      f"fontsize=76:fontcolor={GOLD}:borderw=6:bordercolor=0x0B1220:"
                      f"box=1:boxcolor=0x0B1220@0.34:boxborderw=20:"
                      f"x=(w-tw)/2:y={266 + i * 100}:enable='between(t\\,0\\,3.0)'[hk{i}]")
        last = f"[hk{i}]"
    return chains, last


def _end_card(last: str, duration: float, big_logo: str | None) -> tuple[list[str], str]:
    """The last seconds belong to the brand, not to a caption over footage.

    A wash in the brand colour, the app mark, and where to get it — so the frame
    someone screenshots or pauses on says what the app is called and where it is.
    """
    at = max(0.0, duration - END_CARD)
    on = f"enable='gte(t\\,{at:.2f})'"
    # Opaque, not a wash: at 95% the source slide's page number showed through
    # the card as a large ghosted numeral.
    chains = [f"{last}drawbox=x=0:y=0:w={W}:h={H}:color={BRAND_DEEP}:t=fill:{on},"
              f"drawbox=x=0:y=0:w={W}:h=14:color={BRAND_TEAL}:t=fill:{on}[wash]"]
    last = "[wash]"
    if big_logo:
        chains.append(f"{last}[{big_logo}]overlay=x=(W-w)/2:y=520:{on}[mark]")
        last = "[mark]"
    rows = [(BRAND, FONT_BOLD, 86, "white", 900),
            (CTA_LINES[0], FONT_BOLD, 62, GOLD, 1046),
            (CTA_LINES[1], FONT_REG, 50, "white", 1140),
            (CTA_STORE, FONT_BOLD, 46, "white", 1268)]
    for i, (text, font, size, colour, y) in enumerate(rows):
        chains.append(f"{last}drawtext=text='{_escape(text)}':fontfile={font}:"
                      f"fontsize={size}:fontcolor={colour}:x=(w-tw)/2:y={y}:{on}[ct{i}]")
        last = f"[ct{i}]"
    return chains, last


def pick_segment(video: Path, duration: float) -> float:
    """Start offset that skips the title card and lands mid-explanation."""
    total = probe_duration(video)
    # The opening ~15s is branding//title on these videos; the tail trails off.
    lo, hi = 20.0, max(25.0, total - duration - 15.0)
    # A third of the way in is reliably mid-topic rather than intro or outro.
    return min(hi, max(lo, total * 0.33))


def build_filter(caps: list[dict], hook: str, duration: float,
                 look: tuple[str, int, float] = FALLBACK_LOOK,
                 band: tuple[int, int] = (656, 1264),
                 logo_idx: int | None = None) -> str:
    """The single-window renderer, kept for burnt-in captions.

    It shares every branding layer with the montage so this path cannot quietly
    publish an off-brand reel; only the middle differs — captions here, rotating
    curriculum text there.
    """
    accent, hue, sat = look
    chains = []
    # The source is 16:9. Fill the vertical frame with a blurred, tinted copy of
    # itself, and lay the real footage across the middle — so the motion the
    # video already has is what the viewer sees, not a frozen still.
    keep = f"crop=iw:ih*{SRC_KEEP}:0:0"
    chains.append(f"[0:v]{keep},scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},boxblur=34:34,"
                  f"colorize=hue={hue}:saturation={sat}:lightness=0.30,"
                  f"eq=contrast=1.12,vignette=PI/4[bg]")
    chains.append(f"[0:v]{keep},scale={W}:-2[fg]")
    chains.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    last = "[base]"

    badge = big = None
    if logo_idx is not None:
        chains.append(f"[{logo_idx}:v]split=2[lgA][lgB]")
        chains.append(_circle("lgA", 116, "badge"))
        chains.append(_circle("lgB", 300, "bigmark"))
        badge, big = "badge", "bigmark"

    add, last = _chrome(last, accent, band)
    chains += add
    if badge:
        chains.append(f"{last}[{badge}]overlay=x={W - 116 - 52}:y=44[hdr]")
        last = "[hdr]"

    add, last = _hook_layers(last, hook)
    chains += add

    # Captions, low in the frame so the footage stays visible.
    n = 0
    until = max(0.0, duration - END_CARD)
    for cap in caps:
        # Captions stop before the end card so the two never share the frame.
        if cap["start"] >= min(duration, until):
            break
        for idx, line in enumerate(_wrap(cap["text"], 26)):
            y = int(H * 0.66) + idx * 88
            chains.append(
                f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                f"fontsize=64:fontcolor=white:borderw=6:bordercolor=0x0B1220:"
                f"box=1:boxcolor=0x000000@0.35:boxborderw=18:"
                f"x=(w-tw)/2:y={y}:"
                f"enable='between(t\\,{cap['start']:.2f}\\,{min(cap['end'], until):.2f})'[c{n}]")
            last = f"[c{n}]"
            n += 1

    add, last = _end_card(last, duration, big)
    chains += add

    chains.append(f"{last}null[v]")
    return ";".join(chains)


def render(video: Path, start: float, duration: float, hook: str, out: Path, captions: str = "off") -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        caps = transcribe(video, start, duration, work, captions) if captions != "off" else []
        print(f"  ترجمة: {len(caps)} سطر" if caps else "  ترجمة: مطفية")
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
               "-ss", str(start), "-t", str(duration), "-i", str(video)]
        logo_idx = None
        if LOGO.exists():
            logo_idx = 1
            cmd += ["-i", str(LOGO)]
        fc = build_filter(caps, hook, duration, domain_look(video), frame_band(video), logo_idx)
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
               "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)]
        r = _run(cmd)
        if r.returncode != 0:
            print("  ✗ ffmpeg:", r.stderr[-700:])
            return False
    record(video, out, hook, *split_age(curriculum_copy(video)[0]))
    return True



def montage_filter(cuts: list[tuple[float, float]], hook: str, duration: float,
                   title: str = "", points: list[str] | None = None,
                   look: tuple[str, int, float] = FALLBACK_LOOK,
                   band: tuple[int, int] = (656, 1264),
                   logo_idx: int | None = None) -> str:
    """Cross-cut several moments so the frame changes every few seconds.

    A single 30s window lands on one slide: these videos hold each slide for
    a minute or more, so cutting once gives a still image with narration over
    it — which is the problem the old generator had. Sampling across the whole
    video means a new illustration every few seconds instead.
    """
    accent, hue, sat = look
    chains, segs = [], []
    for i, (st, dur) in enumerate(cuts):
        # The footage is 16:9 inside a 9:16 frame, so two thirds of the screen
        # is filler. Blurring the footage into it left that filler a muddy
        # grey; tinting the blur to the domain's own colour makes it read as a
        # deliberate backdrop, and it still moves with the video.
        keep = f"crop=iw:ih*{SRC_KEEP}:0:0"
        chains.append(f"[{i}:v]{keep},scale={W}:{H}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H},boxblur=34:34,"
                      f"colorize=hue={hue}:saturation={sat}:lightness=0.30,"
                      f"eq=contrast=1.12,vignette=PI/4[bg{i}]")
        chains.append(f"[{i}:v]{keep},scale={W}:-2[fg{i}]")
        chains.append(f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[s{i}]")
        segs.append(f"[s{i}]")
    chains.append("".join(segs) + f"concat=n={len(cuts)}:v=1:a=0[joined]")
    last = "[joined]"

    badge = big = None
    if logo_idx is not None:
        chains.append(f"[{logo_idx}:v]split=2[lgA][lgB]")
        chains.append(_circle("lgA", 116, "badge"))
        chains.append(_circle("lgB", 300, "bigmark"))
        badge, big = "badge", "bigmark"

    add, last = _chrome(last, accent, band)
    chains += add
    if badge:
        chains.append(f"{last}[{badge}]overlay=x={W - 116 - 52}:y=44[hdr]")
        last = "[hdr]"

    add, last = _hook_layers(last, hook)
    chains += add

    # The bands carry curriculum text, so neither may run under the end card.
    until = max(0.0, duration - END_CARD)

    # Upper band: the age first — a parent scanning the feed decides on that
    # before anything else — then the path title.
    headline, age = split_age(title)
    if age:
        chains.append(f"{last}drawtext=text='{_escape(age)}':fontfile={FONT_BOLD}:"
                      f"fontsize=46:fontcolor=white:borderw=4:bordercolor=0x0B1220:"
                      f"box=1:boxcolor={accent}@0.75:boxborderw=16:"
                      f"x=(w-tw)/2:y=232:enable='between(t\\,3.2\\,{until:.2f})'[age]")
        last = "[age]"
    for i, line in enumerate(_wrap(headline, 26)):
        chains.append(f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                      f"fontsize=58:fontcolor=white:borderw=5:bordercolor=0x0B1220:"
                      f"x=(w-tw)/2:y={324 + i * 74}:"
                      f"enable='between(t\\,3.2\\,{until:.2f})'[ttl{i}]")
        last = f"[ttl{i}]"

    # Lower band: one lesson title at a time, so the filler carries the actual
    # curriculum instead of nothing.
    pts = points or []
    if pts:
        window = max(3.0, (until - 3.2) / len(pts))
        for i, pt in enumerate(pts):
            st, en = 3.2 + i * window, min(until, 3.2 + (i + 1) * window)
            if st >= en:
                break
            # 27, not 24: at 24 "ضبط الغضب على هدي النبي ﷺ" dropped the ﷺ onto
            # a line of its own.
            for idx, line in enumerate(_wrap(pt, 27)):
                chains.append(
                    f"{last}drawtext=text='{_escape(line)}':fontfile={FONT_BOLD}:"
                    f"fontsize=60:fontcolor={GOLD}:borderw=5:bordercolor=0x0B1220:"
                    f"x=(w-tw)/2:y={int(H * 0.755) + idx * 78}:"
                    f"enable='between(t\\,{st:.2f}\\,{en:.2f})'[pt{i}_{idx}]")
                last = f"[pt{i}_{idx}]"

    add, last = _end_card(last, duration, big)
    chains += add

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
    logo_idx = None
    if LOGO.exists():
        logo_idx = len(cuts) + 1
        cmd += ["-i", str(LOGO)]

    title, points = curriculum_copy(video)
    look, band = domain_look(video), frame_band(video)
    cmd += ["-filter_complex",
            montage_filter(cuts, hook, duration, title, points, look, band, logo_idx),
            "-map", "[v]", "-map", f"{len(cuts)}:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k",
            # Without this the moov atom lands after mdat, so anything reading
            # the file over HTTP has to fetch all of it before it knows what it
            # is. Buffer gives up and reports "Video could not be read from its
            # URL" — a message that points at the URL, which is fine.
            "-movflags", "+faststart",
            "-shortest", str(out)]
    r = _run(cmd)
    if r.returncode != 0:
        print("  \u2717 ffmpeg:", r.stderr[-700:])
        return False
    print(f"  مونتاج: {n_cuts} قصّات، تغيّر كل {per:.1f}s · لون {look[0]}"
          + (f" · نص المنهج: {len(points)} نقطة" if points else " · بلا نص منهج")
          + ("" if logo_idx is not None else " · بلا شعار"))
    record(video, out, hook, *split_age(title))
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
    ap.add_argument("--batch", type=int, default=0,
                    help="ولّد هذا العدد من الريلز — يتخطّى ما وُلّد سابقًا")
    ap.add_argument("--montage", type=int, default=0,
                    help="عدد القصّات — يمنع وقوع الريل على شريحة واحدة ثابتة")
    args = ap.parse_args()

    srcs = sources()
    if args.list or (not args.source and not args.batch):
        print(f"مصادر مسرودة متاحة: {len(srcs)}\n")
        for p in srcs[:15]:
            print(f"  {probe_duration(p):6.0f}s  {p.relative_to(ROOT)}")
        if not args.source:
            return 0
        return 0

    if args.batch:
        made, skipped = 0, 0
        for src in srcs:
            if made >= args.batch:
                break
            out = OUT_DIR / f"reel_{src.stem}.mp4"
            if out.exists():
                skipped += 1
                continue
            hk = hook_for(src)
            if not hk:
                print(f"  ⊘ {src.stem}: لا خطّاف مكتوب — تخطّي")
                continue
            print(f"\n[{made + 1}/{args.batch}] {src.stem}")
            print(f"  خطّاف: {hk}")
            if render_montage(src, args.duration, hk, out, args.montage or 6):
                print(f"  ✅ {out.name}  ({out.stat().st_size / 1048576:.1f} MB)")
                made += 1
        print(f"\nتم: {made} ريل جديد · {skipped} موجود مسبقًا")
        return 0

    video = Path(args.source)
    if not video.is_absolute():
        video = ROOT / video
    if not video.exists():
        print(f"غير موجود: {video}")
        return 1

    start = args.start if args.start is not None else pick_segment(video, args.duration)
    hook = args.hook or hook_for(video) or "دقيقة واحدة تفرق في تربية ابنك"
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
