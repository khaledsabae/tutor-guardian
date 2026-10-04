"""Every public page that sends a visitor to Google Play carries attribution.

`e35bcdc2` rewrote /ui/ for the cinematic landing and silently dropped both
the utm passthrough (`30bc1d5f`) and every Play link on the page — no test
noticed, and the August ad campaign's destination became a dead end. So this
file does not list pages to check: it walks the app's routes and renders every
public GET page, so a page added tomorrow is covered without anyone
remembering to add it here.
"""
import html as _html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.db.init_db import get_conn
from app.main import app
from app.routers.seo import SEO_PAGES
from app.services.attribution import PLAY_URL

_ROOT = Path(__file__).resolve().parents[2]
_APP_RE = re.compile(r"REF_([A-Z0-9]{4,16})")  # mobile referral_service.dart
_HREF_RE = re.compile(r'href="([^"]*)"')

# The pages that must link to Play. Losing every Play link is a failure too —
# that was the /ui/ bug — so the walk below must find at least these.
_MUST_LINK_TO_PLAY = {
    "/", "/go", "/ui/", "/ui/index.html", "/l/{lesson_id}", "/p/{path_id}",
    "/seo/", "/seo/{slug}", "/methodology",
}
_UTM = {"utm_source": "src_t", "utm_medium": "med_t", "utm_campaign": "camp_t"}

# Production traffic arrives Cloudflare → nginx → app; ClientIPMiddleware
# only believes CF-Connecting-IP from such a trusted peer.
_NGINX_PEER = ("172.18.0.5", 50000)


@pytest.fixture
def client():
    with TestClient(app, client=_NGINX_PEER) as c:
        yield c


def _path_params() -> dict[str, str]:
    path = cl.get_paths()[0]
    lesson = cl.get_lessons_for_path(path["id"])[0]
    return {"lesson_id": lesson["id"], "path_id": path["id"],
            "slug": next(iter(SEO_PAGES))}


def _public_pages() -> list[str]:
    pages = []
    for route in app.routes:
        if (isinstance(route, APIRoute) and "GET" in route.methods
                and not route.path.startswith("/api")):
            pages.append(route.path)
    return pages


def _play_links(body: str) -> list[str]:
    return [_html.unescape(h) for h in _HREF_RE.findall(body)
            if "play.google.com" in h]


def _what_the_readers_see(play_link: str) -> tuple[str | None, dict]:
    """(code the app claims, utm Firebase reads) from one Play link."""
    assert play_link.startswith(PLAY_URL), play_link
    referrer = (parse_qs(urlsplit(play_link).query).get("referrer") or [""])[0]
    m = _APP_RE.search(referrer.upper())
    utm = {k: v[0] for k, v in parse_qs(referrer).items() if k.startswith("utm_")}
    return (m.group(1) if m else None), utm


def test_every_play_link_on_every_public_page_carries_ref_and_utm(client):
    params = _path_params()
    linked = set()
    for route_path in _public_pages():
        url = route_path.format(**params)
        r = client.get(url, params={"ref": "da-01", **_UTM})
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        links = _play_links(r.text)
        if links:
            linked.add(route_path)
        for link in links:
            code, utm = _what_the_readers_see(link)
            assert code == "DA01", f"{url}: the app would claim {code!r} from {link}"
            assert utm == _UTM, f"{url}: Firebase would read {utm}"
    missing = _MUST_LINK_TO_PLAY - linked
    assert not missing, f"no Play link at all on: {sorted(missing)}"


def test_utm_alone_reaches_play_from_the_ad_landing(client):
    # Meta can only send traffic to a web page; the August campaign used /ui/.
    for url in ("/ui/", "/go", "/"):
        links = _play_links(client.get(url, params={"utm_source": "facebook",
                                                    "utm_campaign": "boost 1",
                                                    "fbclid": "x"}).text)
        assert len(links) >= 4, url
        for link in links:
            assert _what_the_readers_see(link) == (
                None, {"utm_source": "facebook", "utm_campaign": "boost 1"})


def test_an_organic_visit_gets_the_bare_store_link(client):
    for url in ("/ui/", "/go", "/"):
        links = _play_links(client.get(url).text)
        assert links and set(links) == {PLAY_URL}, url


def test_the_ui_page_has_no_dead_end_buttons(client):
    body = client.get("/ui/").text
    assert 'href="#cta"' not in body
    assert "{{" not in body  # every template placeholder was filled
    assert "hero-canvas-section" in body  # same cinematic page, same design


def test_ui_without_a_slash_keeps_the_query(client):
    r = client.get("/ui", params={"utm_source": "facebook"}, follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"].endswith("/ui/?utm_source=facebook")


def test_the_canonical_never_echoes_tracking_params(client):
    for url in ("/go", "/ui/", "/"):
        body = client.get(url, params={"ref": "DA01", **_UTM}).text
        canonical = re.search(r'<link rel="canonical" href="([^"]*)"', body).group(1)
        assert canonical.endswith("/go"), canonical
    params = _path_params()
    for url in (f"/l/{params['lesson_id']}", f"/p/{params['path_id']}"):
        body = client.get(url, params={"ref": "DA01", **_UTM}).text
        canonical = re.search(r'<link rel="canonical" href="([^"]*)"', body).group(1)
        assert "?" not in canonical and canonical.endswith(url), canonical


# No \b: Arabic letters are word characters, so \biOS\b misses «أندرويد وiOS» —
# the very claim this replaced. Case-sensitive, so BIOS and -apple-system pass.
_IOS_CLAIM = re.compile(r"iOS|iPhone|iPad|آيفون|أيفون|App Store|apps\.apple\.com")

# A solo project: no scholar, sheikh, doctor or reviewer stands behind the
# content, so supervision, review, accreditation or expert authorship is a false
# claim. What the system does guarantee is said plainly instead: automated
# matching against the Mushaf and the two Sahihs, and rulings deferred to
# «أهل العلم» (not matched here). Bare «مراجع» is left out on purpose: it also
# means "references", which the pages state truthfully («مراجعها»).
_AUTHORITY_CLAIM = re.compile(
    r"إشراف|مراجعة (?:شرعية|تربوية|طبية|علمية)|مُراجَع|مراجَع|تُراجَع|تُراجع|يُراجَع|"
    r"موث[ّ]?ق|مُوثّق|موثوق|معتمد|مُعتمد|علماء|مشايخ|شيوخ|أطباء|خبراء|خبير|"
    r"الطب النفسي|\b(?:experts?|scholars?|certified|accredited|approved by|reviewed by)\b",
    re.IGNORECASE,
)
_FALSE_CLAIMS = {
    "iOS — the app is Android-only (master plan, phase 4)": _IOS_CLAIM,
    "authority — no human sharia, medical or educational reviewer exists": _AUTHORITY_CLAIM,
}


def _public_html(client) -> list[tuple[str, str]]:
    """(where, html) for every public page as served, plus the frontend sources."""
    params = _path_params()
    urls = [route_path.format(**params) for route_path in _public_pages()]
    urls += [f"/seo/{slug}" for slug in SEO_PAGES]  # every article, not one sample
    pages = []
    for url in urls:
        r = client.get(url)
        if "text/html" in r.headers.get("content-type", ""):
            pages.append((url, r.text))
    for page in sorted((_ROOT / "frontend").rglob("*.html")):
        pages.append((str(page.relative_to(_ROOT)), page.read_text(encoding="utf-8")))
    return pages


@pytest.mark.parametrize("claim", list(_FALSE_CLAIMS))
def test_no_page_makes_a_claim_the_project_cannot_back(client, claim):
    pattern = _FALSE_CLAIMS[claim]
    found = [(where, m.group(0)) for where, html in _public_html(client)
             for m in [pattern.search(html)] if m]
    assert not found, f"{claim}: {found}"


@pytest.mark.parametrize("text", [
    "إشراف ومراجعة شرعية وتربوية موثقة", "الطب النفسي للأطفال واليافعين",
    "برامج تربوية معتمدة", "مقالات من خبراء التربية الإسلامية", "أقوال العلماء",
    "الوحدات تُراجع دورياً", "Reviewed by scholars", "متوافق مع أندرويد وiOS",
])
def test_the_claims_this_replaced_would_be_caught(text):
    assert any(p.search(text) for p in _FALSE_CLAIMS.values()), text


def test_methodology_numbers_are_counted_not_typed(client):
    # Typed in, they drifted: «١٬١١٩ وحدة» when there were 1,673.
    from app.services.knowledge_loader import load_default_knowledge_units

    total = len(load_default_knowledge_units())
    arabic = f"{total:,}".replace(",", "٬").translate(
        str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    assert f'<div class="stat-num">{arabic}</div>' in client.get("/methodology").text


@pytest.mark.parametrize("text", [
    "لا فتوى — الأحكام تُحال إلى أهل العلم", "ويذكر مراجعها في سطر 📚",
    "متى أستشير الطبيب؟", "لا مراجعة من أهل العلم", "font-family: -apple-system",
])
def test_truthful_wording_is_not_flagged(text):
    assert not any(p.search(text) for p in _FALSE_CLAIMS.values()), text


def test_no_static_page_links_to_play_directly():
    # A static file cannot carry ref/utm through — Play links belong in a route.
    offenders = []
    for base in (_ROOT / "frontend", _ROOT / "docs"):
        for page in base.rglob("*.html"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            if "play.google.com/store/apps" in text or 'href="#cta"' in text:
                offenders.append(str(page.relative_to(_ROOT)))
    assert not offenders, offenders


# ── Clicks: the AUTO fallback needs one from every landing page ─────────────

def _clicks() -> list[tuple[str, str]]:
    conn = get_conn()
    try:
        return [(r["ip"], r["code"]) for r in
                conn.execute("SELECT ip, code FROM referral_clicks ORDER BY id")]
    finally:
        conn.close()


def test_a_campaign_click_is_recorded_on_every_landing_page(client):
    params = _path_params()
    pages = ["/go", "/", "/ui/", f"/l/{params['lesson_id']}", f"/p/{params['path_id']}",
             f"/seo/{params['slug']}", "/seo/", "/methodology"]
    for i, url in enumerate(pages):
        ip = f"203.0.113.{10 + i}"
        assert client.get(url, params={"ref": "wa-01"},
                          headers={"cf-connecting-ip": ip}).status_code == 200
        assert (ip, "WA01") in _clicks(), url


@pytest.mark.parametrize("fetcher", [
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "WhatsApp/2.23.20.0 A",
    "TelegramBot (like TwitterBot)",
])
def test_a_link_preview_fetch_is_not_a_click(client, fetcher):
    # 15% of production clicks were these: every share fetched the preview.
    r = client.get("/go?ref=DA01", headers={"cf-connecting-ip": "203.0.113.90",
                                           "user-agent": fetcher})
    assert r.status_code == 200 and "og:image" in r.text   # the preview still works
    assert _clicks() == []


def test_a_phone_whose_name_ends_in_bot_still_counts(client):
    ua = ("Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
    client.get("/go?ref=DA01", headers={"cf-connecting-ip": "203.0.113.91",
                                        "user-agent": ua})
    assert _clicks() == [("203.0.113.91", "DA01")]


def test_an_unknown_personal_code_is_still_not_recorded(client):
    client.get("/ui/?ref=NOPE99", headers={"cf-connecting-ip": "203.0.113.7"})
    client.get("/l/x?ref=ZZZZ22", headers={"cf-connecting-ip": "203.0.113.7"})
    assert _clicks() == []


# ── Click writes are bounded: 8 public routes share the app-wide SQLite ──────

def _trace_writes(monkeypatch) -> list[str]:
    """Every INSERT/UPDATE/DELETE record_click sends to SQLite."""
    from app.services import attribution

    real, writes = attribution.get_conn, []

    def traced():
        conn = real()
        conn.set_trace_callback(
            lambda sql: writes.append(sql)
            if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) else None)
        return conn

    monkeypatch.setattr(attribution, "get_conn", traced)
    return writes


def test_a_repeat_visit_within_a_minute_writes_nothing(client, monkeypatch):
    writes = _trace_writes(monkeypatch)
    ip = {"cf-connecting-ip": "203.0.113.70"}
    client.get("/go?ref=DA01", headers=ip)
    assert len(writes) == 1                      # the first visit inserts
    writes.clear()
    for _ in range(5):
        client.get("/go?ref=DA01", headers=ip)
    assert writes == []                          # no UPDATE + COMMIT per hit
    conn = get_conn()
    conn.execute("UPDATE referral_clicks SET clicked_at = datetime('now', '-2 minutes')")
    conn.commit()
    conn.close()
    client.get("/go?ref=DA01", headers=ip)
    assert len(writes) == 1 and writes[0].lstrip().upper().startswith("UPDATE")


def test_ipv6_visitors_are_counted_per_64(client):
    for host in ("2001:db8:9:9::1", "2001:db8:9:9:abcd::2"):
        client.get("/go?ref=DA01", headers={"cf-connecting-ip": host})
    assert _clicks() == [("2001:db8:9:9::/64", "DA01")]


def test_new_clicks_have_a_global_per_minute_cap(client, monkeypatch):
    from app.services import attribution

    monkeypatch.setattr(attribution, "MAX_NEW_CLICKS_PER_MINUTE", 3)
    for i in range(5):
        client.get("/go?ref=DA01", headers={"cf-connecting-ip": f"198.51.100.{i}"})
    assert len(_clicks()) == 3


@pytest.mark.parametrize("header", [
    {"Sec-Purpose": "prefetch"}, {"Sec-Purpose": "prefetch;prerender"},
    {"Purpose": "prefetch"}, {"X-Purpose": "preview"}, {"X-Moz": "prefetch"},
])
def test_a_prefetch_or_preview_load_is_not_a_click(client, header):
    r = client.get("/go?ref=DA01", headers={"cf-connecting-ip": "203.0.113.80", **header})
    assert r.status_code == 200 and "referrer=ref_DA01" in _html.unescape(r.text)
    assert _clicks() == []


def test_a_database_that_will_not_open_never_fails_the_page(client, monkeypatch):
    import sqlite3

    from app.services import attribution

    def broken():
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(attribution, "get_conn", broken)
    r = client.get("/go?ref=DA01", headers={"cf-connecting-ip": "203.0.113.81"})
    assert r.status_code == 200 and "referrer=ref_DA01" in _html.unescape(r.text)


@pytest.mark.parametrize("path", ["/seo/", "/seo/pray-child", "/methodology"])
def test_a_tagged_page_is_never_kept_by_a_shared_cache(client, path):
    # The Play link inside carries this visitor's ?ref= / utm_*.
    for query in ({"ref": "DA01"}, {"utm_source": "facebook"}):
        cache = client.get(path, params=query).headers["cache-control"]
        assert "private" in cache and "public" not in cache, (path, query, cache)
    assert client.get(path).headers["cache-control"] == "public, max-age=3600"


def test_methodology_numbers_return_after_a_failed_count(client, monkeypatch):
    from app.routers import methodology
    from app.services import knowledge_loader

    real = knowledge_loader.load_default_knowledge_units
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("knowledge base not mounted yet")
        return real()

    monkeypatch.setattr(methodology, "_STATS", None)
    monkeypatch.setattr(knowledge_loader, "load_default_knowledge_units", flaky)
    assert 'class="stat-num"' not in client.get("/methodology").text  # renders anyway
    assert 'class="stat-num"' in client.get("/methodology").text      # not cached as None


# ── Documented campaign links keep their query on the way in ────────────────

_DOC_CAMPAIGN_URL = re.compile(r"https?://[^\s)`'\"<>»]+[?&](?:ref|utm_[a-z]+)=")
_KEEPS_QUERY = re.compile(r"^https://tg-api\.alsaba\.cloud/(?:go|l/[^?]+|seo/[^?]*)\?")


def test_campaign_links_only_use_routes_that_keep_the_query():
    # The alsaba.cloud proxy for /methodology drops the query string — the code
    # and utm_* never reach the page — and its config lives in another
    # project's repo on a shared host. So campaign traffic goes to tg-api's
    # /go, /l/ and /seo/ only.
    docs = [_ROOT / "docs" / "OPS_RUNBOOK.md",
            *sorted((_ROOT / "docs" / "marketing" / "2026-10-ramadan").glob("*.md"))]
    bad = [(doc.name, m.group(0)) for doc in docs
           for m in _DOC_CAMPAIGN_URL.finditer(doc.read_text(encoding="utf-8"))
           if not _KEEPS_QUERY.match(m.group(0))]
    assert not bad, bad
    runbook = (_ROOT / "docs" / "OPS_RUNBOOK.md").read_text(encoding="utf-8")
    section = runbook.split("### 6.5", 1)[1].split("\n### ", 1)[0]
    routes = set(re.findall(r"`(/[a-z]+)[^`]*`", section))
    assert routes <= {"/go", "/l", "/seo"}, routes
    assert "alsaba.cloud/methodology" in section  # and it says why not
