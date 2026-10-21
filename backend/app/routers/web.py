"""
Public web router — Phase 2 growth loop (SEO + deferred deep-link landing).

Serves human-viewable, Google-indexable HTML pages for the curriculum plus a
share/install landing page — all PUBLIC (no /api prefix, no auth). Every page
carries Open Graph tags so WhatsApp/social link previews look good, and a
prominent install CTA that forwards the referral code to the Play Install
Referrer (free attribution). This turns shared links into a content + install
surface and a slow-but-durable organic-search channel.

Routes (mounted at root):
  GET /, /go, /ui/     → install / landing page (?ref=<code>, utm_* attribution),
                         Arabic or English (?lang=, a campaign code, Accept-Language)
  GET /l/{lesson_id}   → a single lesson, indexable
  GET /p/{path_id}     → a path overview + its lessons, indexable
  GET /sitemap.xml     → all lesson + path URLs for crawlers
  GET /robots.txt      → allow all + point to the sitemap

Every Play link here comes from app.services.attribution, which carries `ref`
and `utm_*` through to the install referrer; a page that reaches Play any
other way fails tests/test_landing_attribution.py.
"""
from __future__ import annotations

import html
import logging
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app import curriculum_loader as cl
from app.services.attribution import (
    attribute_visit,
    clean_utm,
    is_campaign_code,
    normalize_code,
    query_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])

_CINEMATIC = Path(__file__).resolve().parents[3] / "frontend" / "cinematic.html"
# The English landing: the same page, the same art, laid out left to right.
_CINEMATIC_EN = _CINEMATIC.with_name("cinematic.en.html")
_LANDING_LANGS = ("ar", "en")
# A campaign code decides the language: its visitor clicked a post written in
# that code's language. English: EN01… preachers and educators in English,
# CM01… English community groups (attribution.CAMPAIGN_CHANNELS); every other
# campaign code is Arabic.
_EN_CAMPAIGN_PREFIXES = ("EN", "CM")
# Single English codes under an Arabic prefix — docs/marketing/campaign_codes.md:
# WA02 is the English WhatsApp channel (WA01 the Arabic one, WA03+ groups).
_EN_CAMPAIGN_CODES = frozenset({"WA02"})
_EMERALD = "#0F6B5C"  # «نور والقناديل» sky (docs/brand, mobile/assets/svg/STYLE.md)
# The share image of every public page: 1200x630, cut from the Play feature
# graphic by `docs/brand/tools/brand_build.py web`. PNG — flat paper-cut art is
# smaller as PNG than as JPG, and WhatsApp previews both.
_OG_IMAGE = "/ui/assets/og_noor.png"
# Self-hosted, subset Cairo (frontend/assets/fonts/): no third-party font request.
_FONT_FACES = "".join(
    f'@font-face{{font-family:Cairo;font-weight:{w};font-display:swap;'
    f'src:url(/ui/assets/fonts/cairo-{n}.woff2) format("woff2")}}'
    for w, n in ((400, "regular"), (600, "semibold"), (800, "extrabold"))
)


def _abs(canonical: str, path: str) -> str:
    """Absolute URL for [path] using the host of [canonical] — WhatsApp needs an
    absolute og:image. Force https on real hosts (the backend sees plain http
    behind the Cloudflare/TLS proxy, but the site is served over https)."""
    try:
        host = canonical.split("//", 1)[1].split("/", 1)[0]
        scheme = "http" if host.startswith(("localhost", "127.0.0.1", "testserver")) else "https"
        return f"{scheme}://{host}{path}"
    except Exception:  # noqa: BLE001
        return path


def _esc(s: str | None) -> str:
    return html.escape((s or "").strip())


def _page(*, title: str, desc: str, body: str, install_url: str,
          canonical: str) -> HTMLResponse:
    """Modern branded RTL landing shell with OG tags + install CTA."""
    t, d = _esc(title), _esc(desc)
    install = html.escape(install_url)
    # Escaped *after* _abs uses the raw value: request.url carries the
    # caller's path verbatim, and it lands inside href="…" below.
    og_image = html.escape(_abs(canonical, _OG_IMAGE))
    canonical = html.escape(canonical)
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — المربّي</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/png" sizes="32x32" href="/ui/icons/favicon-32.png">
<meta name="theme-color" content="{_EMERALD}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="المربّي">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og_image}">
<style>
  {_FONT_FACES}
  :root {{
    --teal: {_EMERALD};
    --teal-light: rgba(15,107,92,.08);
    --teal-glow: rgba(15,107,92,.15);
    --cream: #FAF7F2;
    --charcoal: #1c1c1c;
    --muted: #6b6b6b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Cairo', Tahoma, system-ui, sans-serif;
    background: var(--cream);
    color: var(--charcoal);
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 0 18px 130px; }}
  .nav {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(250,247,242,.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(15,107,92,.08);
  }}
  .nav-inner {{
    max-width: 780px; margin: 0 auto; padding: 14px 18px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .brand {{
    display: flex; align-items: center; gap: 8px;
    font-weight: 800; font-size: 20px; color: var(--teal);
  }}
  .brand img {{ width: 34px; height: 34px; border-radius: 10px; }}
  .nav-tag {{
    font-size: 12px; color: var(--muted);
    display: none;
  }}
  @media (min-width: 520px) {{ .nav-tag {{ display: block; }} }}
  .hero {{
    width: 100%; height: auto; border-radius: 20px;
    margin: 22px 0 18px;
    box-shadow: 0 18px 48px rgba(15,107,92,.18);
  }}
  .eyebrow {{
    display: inline-block;
    background: var(--teal-light); color: var(--teal);
    border-radius: 999px; padding: 6px 16px;
    font-size: 13px; font-weight: 700;
    margin-bottom: 14px;
  }}
  h1 {{
    color: var(--teal); font-size: clamp(28px, 5.5vw, 42px);
    line-height: 1.2; font-weight: 800; margin-bottom: 14px;
    letter-spacing: -0.5px;
  }}
  .subtitle {{
    font-size: clamp(17px, 3vw, 20px);
    color: var(--muted); max-width: 560px; margin-bottom: 28px;
  }}
  .content {{
    font-size: 17px; color: var(--charcoal);
    background: #fff; border: 1px solid rgba(15,107,92,.08);
    border-radius: 18px; padding: 22px;
    box-shadow: 0 4px 20px rgba(0,0,0,.04);
    margin-bottom: 22px;
  }}
  .content p + p {{ margin-top: 14px; }}
  .lessons a {{
    display: block; padding: 14px 16px; margin: 10px 0;
    background: #fff; border: 1px solid rgba(15,107,92,.10);
    border-radius: 14px; color: var(--charcoal);
    text-decoration: none; font-weight: 600;
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .lessons a:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(15,107,92,.10);
  }}
  .feature-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin: 24px 0;
  }}
  .feature-card {{
    background: #fff; border: 1px solid rgba(15,107,92,.08);
    border-radius: 14px; padding: 16px; text-align: center;
  }}
  .feature-card .icon {{ font-size: 28px; margin-bottom: 8px; }}
  .feature-card .label {{ font-size: 14px; font-weight: 700; color: var(--teal); }}
  .cta {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(255,255,255,.96);
    backdrop-filter: blur(12px);
    border-top: 1px solid rgba(15,107,92,.10);
    padding: 14px 18px 18px; text-align: center; z-index: 100;
  }}
  .cta a {{
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--teal); color: #fff;
    text-decoration: none; padding: 15px 32px;
    border-radius: 999px; font-weight: 800; font-size: 17px;
    box-shadow: 0 8px 24px rgba(15,107,92,.25);
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .cta a:hover {{ transform: translateY(-2px); box-shadow: 0 10px 28px rgba(15,107,92,.32); }}
  .free {{
    color: var(--muted); font-size: 13px; margin-top: 8px;
  }}
  footer {{
    text-align: center; padding: 30px 0 100px;
    color: var(--muted); font-size: 13px;
  }}
</style>
</head>
<body>
<div class="nav">
  <div class="nav-inner">
    <div class="brand">
      <img src="/ui/icons/icon-192.png" width="34" height="34" alt="">
      المربّي
    </div>
    <div class="nav-tag">مساعد تربية إسلامية ذكي</div>
  </div>
</div>
<div class="wrap">
  {body}
</div>
<div class="cta">
  <a href="{install}">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    حمّله من Google Play
  </a>
  <div class="free">مجاني بالكامل — بلا إعلانات ولا اشتراكات</div>
</div>
</body>
</html>"""
    return HTMLResponse(doc)


# `/ui/` is the same page. It was a static copy of cinematic.html whose
# buttons pointed at `#cta` — never at Play — and it is where the August ad
# campaign sent its traffic (Meta cannot link to Play under the Traffic
# objective). Rendering it here is what lets its buttons carry the ad's utm_*
# to Play. frontend/index.html now only forwards to /go, for the minute of a
# deploy between the new checkout and the new container.
@router.get("/", response_class=HTMLResponse)
@router.get("/go", response_class=HTMLResponse)
@router.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/ui/index.html", response_class=HTMLResponse, include_in_schema=False)
# The template itself sits in the static mount too; served raw, its buttons
# were literal {{DOWNLOAD_URL}} links — dead, and carrying no attribution.
@router.get("/ui/cinematic.html", response_class=HTMLResponse, include_in_schema=False)
@router.get("/ui/cinematic.en.html", response_class=HTMLResponse, include_in_schema=False)
def landing(request: Request) -> HTMLResponse:
    """Share/install landing — where shared cards, referral and campaign links arrive."""
    lang = landing_language(request)
    template = _CINEMATIC_EN if lang == "en" else _CINEMATIC
    if not template.is_file():
        return HTMLResponse("<h1>المربّي — صفحة الهبوط تحت الصيانة</h1>", status_code=503)
    html_content = template.read_text(encoding="utf-8")

    # The English page opens the store in English; the referrer is unchanged.
    install_url = attribute_visit(request, hl="en" if lang == "en" else None)
    url = str(request.url)
    og_image = _abs(url, _OG_IMAGE)
    # One canonical per language, and never the tracking query: each shared
    # ?ref= / utm_* variant would otherwise index as its own page. /go is the
    # Arabic page (Googlebot sends no Accept-Language) and the x-default.
    alternates = {"ar": _abs(url, "/go"), "en": _abs(url, "/go?lang=en")}
    canonical = alternates[lang]

    for key, value in (
        ("{{DOWNLOAD_URL}}", install_url),
        ("{{OG_IMAGE}}", og_image),
        ("{{CANONICAL_URL}}", canonical),
        ("{{ALT_AR_URL}}", alternates["ar"]),
        ("{{ALT_EN_URL}}", alternates["en"]),
        ("{{LANG_TOGGLE_URL}}", _toggle_url(request, "ar" if lang == "en" else "en")),
    ):
        html_content = html_content.replace(key, html.escape(value))

    # The language can follow Accept-Language: no cache may hand one
    # visitor's language to the next.
    return HTMLResponse(content=html_content, status_code=200,
                        headers={"Vary": "Accept-Language"})


def landing_language(request: Request) -> str:
    """`en` or `ar`, in this order:

    1. an explicit ?lang=;
    2. a campaign code: EN…, CM… and WA02 are English, every other one Arabic —
       the visitor clicked a post in that code's language, whatever the phone's;
    3. with no campaign code (none, or a six-character personal code, whose
       random letters say nothing about its reader): Accept-Language, when its
       preferred language is English;
    4. else Arabic.
    """
    lang = (request.query_params.get("lang") or "").strip().lower()
    if lang in _LANDING_LANGS:
        return lang
    if request.url.path == "/ui/cinematic.en.html":
        return "en"
    code = normalize_code(query_code(request.query_params))
    if is_campaign_code(code):
        english = code[:2] in _EN_CAMPAIGN_PREFIXES or code in _EN_CAMPAIGN_CODES
        return "en" if english else "ar"
    if _preferred_language(request.headers.get("accept-language", "")) == "en":
        return "en"
    return "ar"


def _preferred_language(header: str) -> str | None:
    """The primary subtag of the highest-q range: `en-GB,ar;q=0.8` → `en`.

    Equal weights keep the header's order. `*` and malformed weights are skipped.
    """
    best: tuple[float, int, str] | None = None
    for i, part in enumerate(header.split(",")[:20]):
        tag, _, params = part.strip().partition(";")
        primary = tag.strip().split("-", 1)[0].lower()
        if not primary or primary == "*":
            continue
        q = 1.0
        params = params.strip().lower()
        if params.startswith("q="):
            try:
                q = float(params[2:])
            except ValueError:
                continue
        if q > 0 and (best is None or (-q, i) < (-best[0], best[1])):
            best = (q, i, primary)
    return best[2] if best else None


def _toggle_url(request: Request, lang: str) -> str:
    """/go in the other language, keeping the visit's code and utm_*.

    Following it is the same visitor and code again: record_click writes
    nothing within a minute and only refreshes the row within ten, so the
    switch is never a second click.
    """
    params = [("lang", lang)]
    code = normalize_code(query_code(request.query_params))
    if code:
        params.append(("ref", code))
    params += list(clean_utm(request.query_params).items())
    return "/go?" + urlencode(params)


def _canonical(request: Request) -> str:
    """This page's URL without the query string (?ref=, utm_*)."""
    return _abs(str(request.url), request.url.path)


@router.get("/l/{lesson_id}", response_class=HTMLResponse)
def lesson_page(lesson_id: str, request: Request):
    install_url = attribute_visit(request)
    lesson = cl.get_lesson(lesson_id)
    if not lesson:
        return _page(title="الدرس غير متاح", desc="حمّل المربّي للمزيد.",
                     body="<h1>الدرس غير متاح</h1>", install_url=install_url,
                     canonical=_canonical(request))
    title = lesson.get("title", "درس")
    summary = lesson.get("summary", "")
    body = (f'<span class="eyebrow">درس من المربّي</span><h1>{_esc(title)}</h1>'
            f'<div class="content">{_esc(summary)}</div>')
    return _page(title=title, desc=summary or title, body=body,
                 install_url=install_url, canonical=_canonical(request))


@router.get("/p/{path_id}", response_class=HTMLResponse)
def path_page(path_id: str, request: Request):
    install_url = attribute_visit(request)
    path = cl.get_path(path_id)
    if not path:
        return _page(title="المسار غير متاح", desc="حمّل المربّي للمزيد.",
                     body="<h1>المسار غير متاح</h1>", install_url=install_url,
                     canonical=_canonical(request))
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
    return _page(title=title, desc=desc or title, body=body,
                 install_url=install_url, canonical=_canonical(request))


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
