"""
The landing page in the «نور والقناديل» identity (Oct 2026 launch).

Attribution — every Play link carrying ref/utm_* — is tests/test_landing_attribution.py;
this file holds the page to what the launch plan asked of it: Noor and the paper
hills, the approved headline, «مجاني بالكامل» before any feature, one call to
action, the new share image and icons, and nothing loaded from a third party
but the Cloudflare Web Analytics beacon.
"""
import json
import re
import struct

import pytest
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.main import app

_PAGES = ["/", "/go", "/ui/", "/ui/cinematic.html"]
_HEADLINE = "مربٍّ يعرف طفلك، خطوة بخطوة"
_FREE = "مجاني بالكامل"
_CTA = "حمّله من Google Play"
_OG_PATH = "/ui/assets/og_noor.png"
_CF_BEACON = (r'<script defer src="https://static\.cloudflareinsights\.com/beacon\.min\.js/[^"]+"'
              r'[^>]*data-cf-beacon=\'\{[^\']*"token":"7a8db528beef4fe1be0eadf9d6490d25"[^>]*></script>')


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _png_size(body: bytes) -> tuple[int, int]:
    assert body[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", body[16:24])


def _meta(html: str, key: str) -> str:
    m = re.search(rf'<meta (?:property|name)="{re.escape(key)}" content="([^"]*)"', html)
    assert m, key
    return m.group(1)


def test_the_hero_says_what_the_plan_approved(client):
    for path in _PAGES:
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.text
        assert 'id="hero"' in html and 'href="#noor-happy"' in html, path
        assert f"<h1>{_HEADLINE}</h1>" in html, path
        # Free comes first: under the headline, before the first feature block.
        assert html.index(_FREE) < html.index('class="feature"'), path
        assert "بلا إعلانات ولا اشتراكات" in html, path


def test_one_call_to_action(client):
    html = client.get("/go").text
    play = [a for a in re.findall(r'<a [^>]*href="([^"]*)"', html) if "play.google.com" in a]
    assert len(set(play)) == 1  # every button is the same attributed link
    assert html.count(_CTA) >= 2  # one wording, in the hero and at the close
    assert "حمّل التطبيق مجاناً" not in html and "ابدأ رحلتك" not in html


def test_the_child_corner_is_a_story_then_a_task_not_a_game(client):
    html = client.get("/go").text
    assert "ركن الطفل" in html and "بعيدًا عن الشاشة" in html
    assert "لعبة" not in html and "ألعاب" not in html


def test_copy_rules(client):
    text = re.sub(r"<[^>]+>", " ", client.get("/go").text)
    # Easy MSA, not Egyptian; no founder's name; no prizes or rewards promised.
    for word in ("عشان", "ازاي", "إزاي", "دلوقتي", "بتاع", "خالد", "Khaled",
                 "مكافأة", "مكافآت", "جوائز", "جائزة"):
        assert word not in text, word


def test_share_image_is_the_new_1200x630(client):
    for path in _PAGES:
        html = client.get(path).text
        for key in ("og:image", "twitter:image"):
            url = _meta(html, key)
            assert url.endswith(_OG_PATH), (path, key, url)
        assert "banner.png" not in html, path
    r = client.get(_OG_PATH)
    assert r.status_code == 200
    assert _png_size(r.content) == (1200, 630)
    assert len(r.content) < 300_000  # large previews get dropped by WhatsApp


def test_lesson_and_path_pages_share_the_new_image(client):
    path = cl.get_paths()[0]
    lesson = cl.get_lessons_for_path(path["id"])[0]
    for url in (f"/l/{lesson['id']}", f"/p/{path['id']}"):
        html = client.get(url).text
        assert _meta(html, "og:image").endswith(_OG_PATH), url
        assert _meta(html, "twitter:image").endswith(_OG_PATH), url
        assert "landing_hero" not in html and "fonts.googleapis" not in html, url
        assert "/ui/icons/icon-192.png" in html, url


def test_nothing_loads_from_a_third_party(client):
    for path in _PAGES:
        html = client.get(path).text
        # The canonical names this page; it loads nothing.
        loads = re.sub(r'<link rel="canonical"[^>]*>', "", html)
        # The one exception Khaled approved (2026-10-17): the Cloudflare Web
        # Analytics beacon — cookieless, deferred, on the zone we already run.
        beacons = re.findall(_CF_BEACON, loads)
        assert len(beacons) == 1, (path, len(beacons))
        loads = re.sub(_CF_BEACON, "", loads)
        assert not re.search(
            r'<(?:link|script|img|iframe)[^>]+(?:src|href)="(?:https?:)?//', loads), path
        for host in ("fonts.googleapis", "cdn.tailwindcss", "cdnjs", "jsdelivr"):
            assert host not in html, (path, host)
    for weight in ("regular", "semibold", "extrabold"):
        r = client.get(f"/ui/assets/fonts/cairo-{weight}.woff2")
        assert r.status_code == 200 and r.content[:4] == b"wOF2", weight


def test_pwa_icons_are_icon_c_at_their_sizes(client):
    manifest = json.loads(client.get("/ui/manifest.json").text)
    assert manifest["theme_color"] == "#0F6B5C"
    for icon in manifest["icons"]:
        r = client.get(icon["src"])
        assert r.status_code == 200, icon["src"]
        w, h = _png_size(r.content)
        assert f"{w}x{h}" == icon["sizes"], icon
    assert {i["sizes"] for i in manifest["icons"]} >= {"192x192", "512x512"}
    assert any(i.get("purpose") == "maskable" for i in manifest["icons"])
    for src, px in (("/ui/icons/apple-touch-icon.png", 180), ("/ui/icons/favicon-32.png", 32)):
        assert _png_size(client.get(src).content) == (px, px), src
    html = client.get("/go").text
    assert 'href="/ui/icons/favicon-32.png"' in html and 'href="/ui/manifest.json"' in html


def test_the_3d_shield_section_stays_removed(client):
    # Khaled, 2026-10-04: «٠٢ — مجسم درع الأمان التفاعلي» was useless,
    # incomplete and wrong — removed with its model-viewer script and asset.
    for path in _PAGES:
        html = client.get(path).text
        for gone in ("model-3d-section", "model-viewer", "guardian_shield", "مجسم"):
            assert gone not in html, f"{path}: {gone}"
    assert client.get("/ui/assets/3d/guardian_shield.glb").status_code == 404


def test_every_in_page_link_has_a_target(client):
    for path in _PAGES:
        html = client.get(path).text
        ids = set(re.findall(r'\bid="([^"]+)"', html))
        anchors = set(re.findall(r'href="#([^"]+)"', html))
        assert anchors, path
        assert anchors <= ids, f"{path}: dangling {sorted(anchors - ids)}"
