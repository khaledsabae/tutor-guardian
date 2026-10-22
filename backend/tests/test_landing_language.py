"""The landing in English: who gets it, and what it must keep.

English-speaking preachers (EN01…) and community groups (CM01…) were sending
their audience to an Arabic page. The English page is the same page — the same
art, the same attributed Play link, the same single beacon — with English copy
from the en-US store listing, laid out left to right, and a Play link that
opens the store in English.

Order of the rules (web.landing_language): an explicit ?lang=; then a campaign
code, which decides on its own (EN…, CM…, WA02 English, every other Arabic:
the visitor clicked a post in that language); only with no campaign code, an
Accept-Language whose preferred language is English; else Arabic.
"""
import html as _html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app
from app.services.attribution import PLAY_URL

_ROOT = Path(__file__).resolve().parents[2]
_APP_RE = re.compile(r"REF_([A-Z0-9]{4,16})")  # mobile referral_service.dart
_EN_HEADLINE = "A parenting guide that knows your child, step by step"
_AR_HEADLINE = "مربٍّ يعرف طفلك، خطوة بخطوة"
_NGINX_PEER = ("172.18.0.5", 50000)  # ClientIPMiddleware trusts CF-Connecting-IP from it


@pytest.fixture
def client():
    with TestClient(app, client=_NGINX_PEER) as c:
        yield c


def _lang(body: str) -> tuple[str, str]:
    m = re.search(r'<html lang="(\w+)" dir="(\w+)">', body)
    assert m, "no <html lang dir>"
    return m.group(1), m.group(2)


def _play_links(body: str) -> list[str]:
    return [_html.unescape(h) for h in re.findall(r'href="([^"]*)"', body)
            if "play.google.com" in h]


def _clicks() -> list[tuple[str, str]]:
    conn = get_conn()
    try:
        return [(r["ip"], r["code"]) for r in
                conn.execute("SELECT ip, code FROM referral_clicks ORDER BY id")]
    finally:
        conn.close()


# ── Which language ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("query, accept, expected", [
    # 1 · an explicit ?lang= wins over everything
    ({"lang": "en"}, None, "en"),
    ({"lang": "EN"}, None, "en"),
    ({"lang": "ar", "ref": "EN01"}, "en-US,en;q=0.9", "ar"),
    ({"lang": "en", "ref": "DA01"}, "ar-EG,ar;q=0.9", "en"),
    ({"lang": "fr"}, None, "ar"),                      # unknown: the next rules decide
    ({"lang": "fr", "ref": "EN02"}, None, "en"),
    # 2 · a campaign code decides, however it was typed or carried
    ({"ref": "EN01"}, None, "en"),
    ({"ref": "en-07"}, None, "en"),
    ({"c": "cm03"}, None, "en"),
    ({"ref": "CM01"}, "ar-EG,ar;q=0.9", "en"),         # the code beats the header
    ({"ref": "WA02"}, None, "en"),                     # the English WhatsApp channel
    ({"ref": "wa-02"}, "ar-EG,ar;q=0.9", "en"),
    ({"ref": "WA01"}, "en-US,en;q=0.9", "ar"),         # the Arabic one
    ({"ref": "WA03"}, "en-GB", "ar"),
    ({"ref": "DA01"}, "en-US,en;q=0.9", "ar"),         # an Arabic post, an English phone
    ({"ref": "DA01"}, "en-GB", "ar"),
    ({"c": "kt01"}, "en", "ar"),
    ({"ref": "OT99"}, "en-US,en;q=0.9", "ar"),
    ({"ref": "DA01"}, None, "ar"),
    ({"ref": "OT99"}, None, "ar"),
    ({"ref": "ENV9Z5"}, None, "ar"),                   # a personal code: random letters
    # 3 · no campaign code: the visitor's preferred language
    ({"ref": "ABC234"}, "en-US,en;q=0.9", "en"),       # a personal code + English
    ({"ref": "ENV9Z5"}, "ar-EG,ar;q=0.9", "ar"),
    ({"ref": "ZZ99"}, "en-GB", "en"),                  # not a channel: no campaign code
    ({}, "en-US,en;q=0.9,ar;q=0.8", "en"),
    ({}, "en-GB", "en"),
    ({}, "ar-EG,ar;q=0.9,en-US;q=0.8", "ar"),
    ({}, "ar;q=0.5, en;q=0.9", "en"),                  # by weight, not by position
    ({}, "fr-FR,fr;q=0.9,en;q=0.8", "ar"),             # only the preferred one counts
    ({}, "*", "ar"),
    ({}, "en;q=0", "ar"),
    ({}, "en;q=abc", "ar"),
    # 4 · default
    ({}, None, "ar"),
])
def test_language_selection(client, query, accept, expected):
    headers = {"accept-language": accept} if accept is not None else {}
    body = client.get("/go", params=query, headers=headers).text
    assert _lang(body) == (expected, "ltr" if expected == "en" else "rtl"), (query, accept)
    assert (_EN_HEADLINE if expected == "en" else _AR_HEADLINE) in body


def test_every_landing_route_speaks_english(client):
    for url in ("/", "/go", "/ui/", "/ui/index.html", "/ui/cinematic.html"):
        assert _lang(client.get(url, params={"lang": "en"}).text)[0] == "en", url
        assert _lang(client.get(url, params={"ref": "EN01"}).text)[0] == "en", url
    assert _lang(client.get("/ui/cinematic.en.html").text)[0] == "en"


def test_the_response_varies_by_accept_language(client):
    for query in ({}, {"ref": "EN01"}, {"lang": "ar"}):
        assert "accept-language" in client.get("/go", params=query).headers["vary"].lower()


# ── The English page ────────────────────────────────────────────────────────

def test_an_en_code_gets_the_english_page(client):
    body = client.get("/go", params={"ref": "EN01"}).text
    assert _lang(body) == ("en", "ltr")
    assert f"<h1>{_EN_HEADLINE}</h1>" in body
    assert re.search(r'<meta property="og:title" content="Al-Morabbi — [^"]+">', body)
    assert re.search(r'<meta property="og:description" content="[^"]*no ads, no subscriptions', body)
    assert '<meta property="og:locale" content="en_US">' in body
    assert re.search(r'<meta property="og:image" content="http://testserver/ui/assets/og_noor\.png">', body)
    assert '<link rel="canonical" href="http://testserver/go?lang=en">' in body
    # The two languages name each other; /go is the Arabic page and the default.
    for lang, href in (("ar", "/go"), ("en", "/go?lang=en"), ("x-default", "/go")):
        assert f'<link rel="alternate" hreflang="{lang}" href="http://testserver{href}">' in body
    text = re.sub(r"<[^>]+>", " ", body.split("<body>", 1)[1])
    # Arabic on the page is the switch back to it, and nothing else.
    assert re.findall(r"[؀-ۿ]+", text) == ["العربية"]


def test_the_arabic_page_names_the_english_one(client):
    body = client.get("/go", params={"ref": "DA01"}).text
    assert _lang(body) == ("ar", "rtl")
    assert '<link rel="canonical" href="http://testserver/go">' in body
    for lang, href in (("ar", "/go"), ("en", "/go?lang=en"), ("x-default", "/go")):
        assert f'<link rel="alternate" hreflang="{lang}" href="http://testserver{href}">' in body
    assert "Al-Morabbi" not in body and _EN_HEADLINE not in body


@pytest.mark.parametrize("query, toggle_lang", [
    ({"ref": "EN01"}, "ar"),
    ({"ref": "da-01"}, "en"),
    ({"c": "CM02", "utm_content": "bio link"}, "ar"),
    ({}, "en"),
])
def test_the_language_switch_keeps_the_code(client, query, toggle_lang):
    body = client.get("/go", params=query).text
    m = re.search(r'<a class="lang" href="([^"]*)" hreflang="(\w+)"', body)
    assert m and m.group(2) == toggle_lang
    href = _html.unescape(m.group(1))
    parts = urlsplit(href)
    assert parts.path == "/go" and not parts.netloc
    got = {k: v[0] for k, v in parse_qs(parts.query).items()}
    code = (query.get("ref") or query.get("c") or "").replace("-", "").upper()
    expected = {"lang": toggle_lang, **({"ref": code} if code else {})}
    expected.update({k: v for k, v in query.items() if k.startswith("utm_")})
    assert got == expected
    # …and lands on the other language with the same attributed Play link.
    other = client.get(href).text
    assert _lang(other)[0] == toggle_lang
    if code:
        assert all(_APP_RE.search(link.upper()).group(1) == code for link in _play_links(other))


def test_the_english_play_link_keeps_the_referrer_and_opens_play_in_english(client):
    for query in ({"ref": "EN01"}, {"ref": "OT99", "lang": "en"},
                  {"c": "cm04", "utm_source": "src_t", "utm_campaign": "camp_t"}):
        links = _play_links(client.get("/go", params=query).text)
        assert len(links) >= 4 and len(set(links)) == 1, query
        link = links[0]
        assert link.startswith(PLAY_URL + "&referrer=ref_"), link
        assert link.endswith("&hl=en"), link
        qs = parse_qs(urlsplit(link).query)
        assert qs["hl"] == ["en"] and qs["id"] == ["com.alsaba.almorabbi"]
        referrer = qs["referrer"][0]
        code = (query.get("ref") or query.get("c")).upper()
        assert _APP_RE.search(referrer.upper()).group(1) == code  # what the app claims
        utm = {k: v[0] for k, v in parse_qs(referrer).items() if k.startswith("utm_")}
        assert utm["utm_campaign"] == query.get("utm_campaign", code)  # what Firebase reads
        assert "hl" not in parse_qs(referrer)  # hl never leaks into the referrer


def test_an_organic_english_visit_gets_the_bare_link_in_english(client):
    links = _play_links(client.get("/go", params={"lang": "en"}).text)
    assert set(links) == {PLAY_URL + "&hl=en"}


def test_the_arabic_play_link_is_unchanged(client):
    links = _play_links(client.get("/go", params={"ref": "DA01"}).text)
    assert links and all("hl=" not in link for link in links)
    assert set(_play_links(client.get("/go").text)) == {PLAY_URL}


def test_english_copy_rules(client):
    body = client.get("/go", params={"lang": "en"}).text
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.split("<body>", 1)[1]))
    # Factual: free, no ads, no subscriptions, Android only — free before any feature.
    assert body.index("100% free") < body.index('class="feature"')
    for fact in ("no ads, no subscriptions", "Android only", "from pregnancy to age 18"):
        assert fact.lower() in text.lower(), fact
    # No rewards promised; no game (the corner leaves games out in English:
    # cornerGamesSpeak in mobile/lib/features/child_corner/corner_picks.dart);
    # no founder's name; the Qur'an is never presented in translation.
    for word in ("reward", "prize", "earn ", "win ", "game", "Khaled", "Egypt",
                 "translation of the Qur", "English Qur"):
        assert word.lower() not in text.lower(), word
    assert "never translated" in text  # what it does say about the Qur'an


def test_the_english_page_draws_the_same_art():
    ar = (_ROOT / "frontend" / "cinematic.html").read_text(encoding="utf-8")
    en = (_ROOT / "frontend" / "cinematic.en.html").read_text(encoding="utf-8")

    def art(page: str) -> list[str]:
        # Every picture, without its spoken label.
        return [re.sub(r' aria-label="[^"]*"', "", svg)
                for svg in re.findall(r"<svg\b.*?</svg>", page, flags=re.S)]

    assert art(en) == art(ar) and len(art(ar)) >= 8
    # Same fonts (Cairo carries Latin), icons, image and beacon.
    for shared in re.findall(r'(?:src|href)="(/ui/[^"]+)"', ar):
        assert shared in en, shared
    beacon = re.search(r"<script defer src=\"https://static\.cloudflareinsights[^\n]*</script>", ar)
    assert beacon and en.count(beacon.group(0)) == 1


# ── Clicks ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code, lang", [("EN01", "en"), ("DA01", "ar"), ("OT99", "en")])
def test_a_click_is_recorded_once_in_either_language(client, code, lang):
    ip = {"EN01": "203.0.113.91", "DA01": "203.0.113.92", "OT99": "203.0.113.93"}[code]
    query = {"ref": code, **({"lang": "en"} if code == "OT99" else {})}
    body = client.get("/go", params=query, headers={"cf-connecting-ip": ip}).text
    assert _lang(body)[0] == lang
    assert _clicks() == [(ip, code)]
    # Switching language is the same visitor following the same code: no second row.
    toggle = _html.unescape(re.search(r'<a class="lang" href="([^"]*)"', body).group(1))
    assert _lang(client.get(toggle, headers={"cf-connecting-ip": ip}).text)[0] != lang
    assert _clicks() == [(ip, code)]
