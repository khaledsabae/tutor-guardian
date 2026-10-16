"""The campaign code registry, and the QR codes printed on the videos.

docs/marketing/campaign_codes.md is where every code handed out is written
down. Until 16 Oct 2026 the videos' QR codes went straight to Play with utm
only, so ops/scripts/campaign_report.py never saw a scan, and the Arabic
teaser's carried no utm_campaign at all. Now each one is
https://tg-api.alsaba.cloud/go?ref=<CODE>; these tests fail if a QR drifts from
that shape, carries a code the server would not accept, or disagrees with the
registry about which video holds which code.
"""
import re
from pathlib import Path

import pytest

from app.services import attribution as at

_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "docs" / "marketing" / "campaign_codes.md"
_QR_FILES = [
    _ROOT / "remotion-reels" / "src" / "noor" / "campaign" / "qr.ts",
    _ROOT / "remotion-reels" / "src" / "noor" / "qr.ts",
]
_GO = re.compile(r"^https://tg-api\.alsaba\.cloud/go\?ref=([A-Z0-9]+)$")
# A registry row: | `CODE` | origin | … — the first cell is one code in backticks.
_ROW = re.compile(r"^\|\s*`([A-Z]{2}[0-9]{2})`\s*\|(.*)$", re.M)


def _registry() -> dict[str, str]:
    rows: dict[str, str] = {}
    for code, rest in _ROW.findall(_REGISTRY.read_text(encoding="utf-8")):
        assert code not in rows, f"{code} is assigned twice in {_REGISTRY.name}"
        rows[code] = rest
    return rows


def _qr_urls() -> dict[str, str]:
    out: dict[str, str] = {}
    for ts in _QR_FILES:
        for key, url in re.findall(r'^\t(\w+): \{url: "([^"]+)"', ts.read_text(), re.M):
            assert key not in out, key
            out[key] = url
    return out


def test_every_registered_code_is_one_the_server_accepts():
    rows = _registry()
    assert len(rows) >= 40, "the registry table did not parse"
    bad = [code for code in rows if not at.is_campaign_code(code)]
    assert not bad, f"not a campaign code (attribution.CAMPAIGN_CHANNELS): {bad}"


def test_every_prefix_the_server_accepts_is_documented():
    text = _REGISTRY.read_text(encoding="utf-8")
    missing = [p for p in at.CAMPAIGN_CHANNELS if f"| `{p}` |" not in text]
    assert not missing, missing


def test_every_video_qr_goes_to_the_landing_page_with_a_code():
    urls = _qr_urls()
    # six campaign reels + four teaser cuts (ar, world, en, wide)
    assert len(urls) == 10, sorted(urls)
    for key, url in urls.items():
        m = _GO.match(url)
        assert m, f"{key}: {url} does not go through /go?ref=<CODE>"
        assert at.is_campaign_code(m.group(1)), f"{key}: {m.group(1)}"
        assert at.campaign_channel(m.group(1)) == "campaign_video", key


def test_every_video_qr_carries_its_own_registered_code():
    rows = _registry()
    codes = {}
    for key, url in _qr_urls().items():
        code = _GO.match(url).group(1)
        assert code in rows, f"{key}: {code} is not in {_REGISTRY.name}"
        assert f"`{key}`" in rows[code], f"{code} is registered to another video: {rows[code]}"
        codes.setdefault(code, []).append(key)
    shared = {c: k for c, k in codes.items() if len(k) > 1}
    assert not shared, f"two videos share a code, so their scans cannot be told apart: {shared}"


@pytest.mark.parametrize("cut", ["ar", "en", "wide", "world"])
def test_no_teaser_cut_reaches_play_without_a_campaign(cut):
    # The Arabic cut used to carry utm_source and utm_medium but no utm_campaign.
    code = _GO.match(_qr_urls()[cut]).group(1)
    play = at.play_install_url(code, at.attribution_utm(code, {}))
    assert f"referrer=ref_{code}%26" in play
    assert f"utm_campaign%3D{code}" in play
