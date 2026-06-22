"""
Public web router — Phase 2 growth loop (SEO + deferred deep-link landing).

Serves human-viewable, Google-indexable HTML pages for the curriculum plus a
share/install landing page — all PUBLIC (no /api prefix, no auth). Every page
carries Open Graph tags so WhatsApp/social link previews look good, and a
prominent install CTA that forwards the referral code to the Play Install
Referrer (free attribution). This turns shared links into a content + install
surface and a slow-but-durable organic-search channel.

Routes (mounted at root):
  GET /go              → install / landing page (?ref=<code> attribution)
  GET /l/{lesson_id}   → a single lesson, indexable
  GET /p/{path_id}     → a path overview + its lessons, indexable
  GET /sitemap.xml     → all lesson + path URLs for crawlers
  GET /robots.txt      → allow all + point to the sitemap
"""
from __future__ import annotations

import html
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app import curriculum_loader as cl

router = APIRouter(tags=["web"])

_PLAY = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
_TEAL = "#01696F"
# Branded hero (JPG for reliable WhatsApp/social preview), served via /docs.
_OG_IMAGE = "/docs/marketing/launch_graphics/landing_hero.jpg"
_CODE_RE = re.compile(r"^[A-Z0-9]{4,16}$")


def _install_url(ref: str | None) -> str:
    return f"{_PLAY}&referrer=ref_{ref}" if ref and _CODE_RE.match(ref) else _PLAY


def _abs(canonical: str, path: str) -> str:
    """Absolute URL for [path] using the scheme+host of [canonical] — WhatsApp
    needs an absolute og:image."""
    try:
        scheme, rest = canonical.split("//", 1)
        host = rest.split("/", 1)[0]
        return f"{scheme}//{host}{path}"
    except Exception:  # noqa: BLE001
        return path


def _esc(s: str | None) -> str:
    return html.escape((s or "").strip())


def _page(*, title: str, desc: str, body: str, ref: str | None,
          canonical: str) -> HTMLResponse:
    """Wrap content in the branded RTL shell with OG tags + install CTA."""
    t, d = _esc(title), _esc(desc)
    install = _install_url(ref)
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — المربّي</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="المربّي">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{_abs(canonical, _OG_IMAGE)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<style>
  :root {{ --teal: {_TEAL}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: 'Segoe UI', Tahoma, sans-serif;
    background:#FAF7F2; color:#1c1c1c; line-height:1.8; }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 24px 18px 96px; }}
  .hero {{ width:100%; height:auto; border-radius:16px; margin:8px 0 4px;
    box-shadow:0 6px 24px rgba(1,105,111,.18); }}
  header {{ text-align:center; padding: 28px 0 8px; }}
  header .brand {{ color: var(--teal); font-weight:800; font-size: 26px; }}
  header .tag {{ color:#6b6b6b; font-size: 14px; }}
  h1 {{ color: var(--teal); font-size: 26px; margin: 18px 0 10px; }}
  .eyebrow {{ display:inline-block; background: rgba(1,105,111,.1);
    color: var(--teal); border-radius: 20px; padding: 4px 14px;
    font-size: 13px; font-weight:700; }}
  .content {{ font-size: 18px; }}
  .lessons a {{ display:block; padding:12px 14px; margin:8px 0;
    background:#fff; border:1px solid #eadfce; border-radius:12px;
    color:#1c1c1c; text-decoration:none; }}
  .cta {{ position: fixed; bottom:0; left:0; right:0; background:#fff;
    border-top:1px solid #eadfce; padding:14px; text-align:center; }}
  .cta a {{ display:inline-block; background: var(--teal); color:#fff;
    text-decoration:none; padding:14px 28px; border-radius:14px;
    font-weight:800; font-size:17px; }}
  .free {{ color:#6b6b6b; font-size:13px; margin-top:6px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">🌙 المربّي</div>
    <div class="tag">مساعد تربية إسلامية ذكي — مجاني لوجه الله</div>
  </header>
  {body}
</div>
<div class="cta">
  <a href="{install}">📲 حمّل «المربّي» مجانًا</a>
  <div class="free">بلا إعلانات · بلا اشتراكات · لوجه الله</div>
</div>
</body>
</html>"""
    return HTMLResponse(doc)


@router.get("/go", response_class=HTMLResponse)
def landing(request: Request, ref: str | None = Query(None)) -> HTMLResponse:
    """Share/install landing — where shared cards & referral links arrive."""
    body = (
        f'<img class="hero" src="{_OG_IMAGE}" alt="المربّي" '
        'loading="lazy" width="1820" height="1024">'
        '<span class="eyebrow">دعوة لوجه الله</span>'
        '<h1>ربِّ طفلك بثقة — بالعربي وبالأدلة</h1>'
        '<div class="content">«المربّي» تطبيق تربية إسلامي ذكي يجاوبك فورًا '
        'عن تحدّيات طفلك اليومية، ومنهج متكامل من الحمل حتى ١٨ سنة، ورحلة '
        'لطفلك، وقرآن وأذكار — مجاني تمامًا بلا إعلانات.</div>'
    )
    return _page(title="ربِّ طفلك بثقة مع المربّي",
                 desc="تطبيق تربية إسلامي ذكي، مجاني بلا إعلانات.",
                 body=body, ref=ref,
                 canonical=str(request.url))


@router.get("/l/{lesson_id}", response_class=HTMLResponse)
def lesson_page(lesson_id: str, request: Request,
                ref: str | None = Query(None)):
    lesson = cl.get_lesson(lesson_id)
    if not lesson:
        return _page(title="الدرس غير متاح", desc="حمّل المربّي للمزيد.",
                     body="<h1>الدرس غير متاح</h1>", ref=ref,
                     canonical=str(request.url))
    title = lesson.get("title", "درس")
    summary = lesson.get("summary", "")
    body = (f'<span class="eyebrow">درس من المربّي</span><h1>{_esc(title)}</h1>'
            f'<div class="content">{_esc(summary)}</div>')
    return _page(title=title, desc=summary or title, body=body, ref=ref,
                 canonical=str(request.url))


@router.get("/p/{path_id}", response_class=HTMLResponse)
def path_page(path_id: str, request: Request, ref: str | None = Query(None)):
    path = cl.get_path(path_id)
    if not path:
        return _page(title="المسار غير متاح", desc="حمّل المربّي للمزيد.",
                     body="<h1>المسار غير متاح</h1>", ref=ref,
                     canonical=str(request.url))
    title = path.get("title", "مسار")
    desc = path.get("description", "")
    lessons = cl.get_lessons_for_path(path_id)
    items = "".join(
        f'<a href="/l/{_esc(ls.get("id"))}">{_esc(ls.get("title"))}</a>'
        for ls in lessons
    )
    body = (f'<span class="eyebrow">مسار تربوي</span><h1>{_esc(title)}</h1>'
            f'<div class="content">{_esc(desc)}</div>'
            f'<div class="lessons">{items}</div>')
    return _page(title=title, desc=desc or title, body=body, ref=ref,
                 canonical=str(request.url))


@router.get("/sitemap.xml")
def sitemap(request: Request) -> Response:
    base = f"{request.url.scheme}://{request.url.netloc}"
    urls = [f"{base}/go"]
    for p in cl.get_paths():
        urls.append(f"{base}/p/{p.get('id')}")
        for ls in cl.get_lessons_for_path(p.get("id")):
            urls.append(f"{base}/l/{ls.get('id')}")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(u)}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request) -> PlainTextResponse:
    base = f"{request.url.scheme}://{request.url.netloc}"
    return PlainTextResponse(
        f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    )
