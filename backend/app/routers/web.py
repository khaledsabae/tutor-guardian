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
import logging
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app import curriculum_loader as cl
from app.db.init_db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])


def _get_client_ip(request: Request) -> str:
    # Resolved once, from trusted proxies only, by ClientIPMiddleware. Reading
    # CF-Connecting-IP / X-Forwarded-For here trusted whatever the caller sent.
    return request.client.host if request.client else "unknown"

_PLAY = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
_TEAL = "#01696F"
# Branded hero (JPG for reliable WhatsApp/social preview), served via /docs.
_OG_IMAGE = "/docs/marketing/launch_graphics/landing_hero.jpg"
_CODE_RE = re.compile(r"^[A-Z0-9]{4,16}$")


def _install_url(ref: str | None) -> str:
    return f"{_PLAY}&referrer=ref_{ref}" if ref and _CODE_RE.match(ref) else _PLAY


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


def _page(*, title: str, desc: str, body: str, ref: str | None,
          canonical: str) -> HTMLResponse:
    """Modern branded RTL landing shell with OG tags + install CTA."""
    t, d = _esc(title), _esc(desc)
    install = _install_url(ref)
    # Escaped *after* _abs uses the raw value: request.url carries the
    # caller's query string verbatim, and it lands inside href="…" below.
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<meta property="og:type" content="website">
<meta property="og:site_name" content="المربّي">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{og_image}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<style>
  :root {{
    --teal: {_TEAL};
    --teal-light: rgba(1,105,111,.08);
    --teal-glow: rgba(1,105,111,.15);
    --cream: #FAF7F2;
    --charcoal: #1c1c1c;
    --muted: #6b6b6b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Cairo', 'Inter', -apple-system, system-ui, sans-serif;
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
    border-bottom: 1px solid rgba(1,105,111,.08);
  }}
  .nav-inner {{
    max-width: 780px; margin: 0 auto; padding: 14px 18px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .brand {{
    display: flex; align-items: center; gap: 8px;
    font-weight: 800; font-size: 20px; color: var(--teal);
  }}
  .brand img {{ width: 32px; height: 32px; border-radius: 50%; }}
  .nav-tag {{
    font-size: 12px; color: var(--muted);
    display: none;
  }}
  @media (min-width: 520px) {{ .nav-tag {{ display: block; }} }}
  .hero {{
    width: 100%; height: auto; border-radius: 20px;
    margin: 22px 0 18px;
    box-shadow: 0 18px 48px rgba(1,105,111,.18);
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
    background: #fff; border: 1px solid rgba(1,105,111,.08);
    border-radius: 18px; padding: 22px;
    box-shadow: 0 4px 20px rgba(0,0,0,.04);
    margin-bottom: 22px;
  }}
  .content p + p {{ margin-top: 14px; }}
  .lessons a {{
    display: block; padding: 14px 16px; margin: 10px 0;
    background: #fff; border: 1px solid rgba(1,105,111,.10);
    border-radius: 14px; color: var(--charcoal);
    text-decoration: none; font-weight: 600;
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .lessons a:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(1,105,111,.10);
  }}
  .feature-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin: 24px 0;
  }}
  .feature-card {{
    background: #fff; border: 1px solid rgba(1,105,111,.08);
    border-radius: 14px; padding: 16px; text-align: center;
  }}
  .feature-card .icon {{ font-size: 28px; margin-bottom: 8px; }}
  .feature-card .label {{ font-size: 14px; font-weight: 700; color: var(--teal); }}
  .cta {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(255,255,255,.96);
    backdrop-filter: blur(12px);
    border-top: 1px solid rgba(1,105,111,.10);
    padding: 14px 18px 18px; text-align: center; z-index: 100;
  }}
  .cta a {{
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--teal); color: #fff;
    text-decoration: none; padding: 15px 32px;
    border-radius: 999px; font-weight: 800; font-size: 17px;
    box-shadow: 0 8px 24px rgba(1,105,111,.25);
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .cta a:hover {{ transform: translateY(-2px); box-shadow: 0 10px 28px rgba(1,105,111,.32); }}
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
      <img src="/assets/images/logo.png" alt="المربّي">
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
    حمّل «المربّي» مجانًا
  </a>
  <div class="free">بلا إعلانات · بلا اشتراكات · لوجه الله</div>
</div>
</body>
</html>"""
    return HTMLResponse(doc)


# Audit M8: `/` and `/go` sit outside /api, so the rate limiter never sees
# them, and every hit used to insert a row — any code, any number of times.
_CLICK_REFRESH_WINDOW = "-10 minutes"
_MAX_CLICKS_PER_IP_PER_HOUR = 20
_MAX_UA_CHARS = 256


def _record_click(ip: str, user_agent: str, code: str) -> None:
    """Remember that this IP followed this referral code, within bounds.

    * Only codes that exist are recorded — random codes cannot fill the table.
    * The same IP and code again within 10 minutes refreshes the existing row
      instead of adding one. The AUTO claim takes the *latest* click for an IP,
      so refreshing keeps "last link followed wins" without the duplicates.
    * At most 20 new rows per IP per hour; beyond that the page still renders,
      the click is just not recorded.
    """
    conn = get_conn()
    try:
        if not conn.execute(
            "SELECT 1 FROM referral_codes WHERE code = ?", (code,)
        ).fetchone():
            return
        recent = conn.execute(
            "SELECT id FROM referral_clicks WHERE ip = ? AND code = ? "
            "AND clicked_at > datetime('now', ?) ORDER BY id DESC LIMIT 1",
            (ip, code, _CLICK_REFRESH_WINDOW),
        ).fetchone()
        if recent:
            conn.execute(
                "UPDATE referral_clicks SET clicked_at = datetime('now') WHERE id = ?",
                (recent["id"],),
            )
        else:
            (count,) = conn.execute(
                "SELECT COUNT(*) FROM referral_clicks "
                "WHERE ip = ? AND clicked_at > datetime('now', '-1 hour')",
                (ip,),
            ).fetchone()
            if count >= _MAX_CLICKS_PER_IP_PER_HOUR:
                return
            conn.execute(
                "INSERT INTO referral_clicks (ip, user_agent, code) VALUES (?, ?, ?)",
                (ip, user_agent[:_MAX_UA_CHARS], code),
            )
        conn.commit()
    except Exception:  # noqa: BLE001 — a click log must never break the landing page
        logger.warning("referral click not recorded", exc_info=True)
    finally:
        conn.close()


@router.get("/", response_class=HTMLResponse)
@router.get("/go", response_class=HTMLResponse)
def landing(request: Request, ref: str | None = Query(None)) -> HTMLResponse:
    """Share/install landing — where shared cards & referral links arrive."""
    from pathlib import Path
    
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    cinematic_file = project_root / "frontend" / "cinematic.html"
    
    if not cinematic_file.is_file():
        return HTMLResponse("<h1>المربّي — صفحة الهبوط تحت الصيانة</h1>", status_code=503)
        
    with open(cinematic_file, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    install_url = _install_url(ref)
    if ref and _CODE_RE.match(ref):
        _record_click(
            _get_client_ip(request), request.headers.get("user-agent", ""), ref.upper()
        )

    og_image = _abs(str(request.url), "/ui/assets/banner.png")
    canonical = str(request.url)
    
    # The canonical URL echoes the caller's query string — escape all three
    # before they are spliced into attribute values in the template.
    html_content = html_content.replace("{{DOWNLOAD_URL}}", html.escape(install_url))
    html_content = html_content.replace("{{OG_IMAGE}}", html.escape(og_image))
    html_content = html_content.replace("{{CANONICAL_URL}}", html.escape(canonical))
    
    return HTMLResponse(content=html_content, status_code=200)


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
