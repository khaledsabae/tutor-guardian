"""Daily tip cards: card tip_N.png must show tip N.

The autoposter (PCC agent tutor_post) posts tip N's text from «## أ) بنك كروت
النصائح» of docs/marketing/02_content_arsenal.md together with
docs/marketing/daily_tips_cards/tip_N.png. The card generator used to parse
EVERY numbered line of that file, so the reel scripts of section ب (items 1-12)
overwrote cards tip_1…tip_12: tip_11.png showed «ليه التطبيق ده مجاني؟…» (an
internal marketing note) next to a post about ten minutes of play.

Pinned here: the generator reads section أ only, ids are 1..30 exactly once,
the generator and the autoposter agree on id -> (category, text), a repeated id
is an error, and the rendered cards keep the «نصيحة اليوم» chip visible and the
text inside the frame of the background art.
"""
import importlib.util
import os
import re
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "ops" / "tools"
ARSENAL = ROOT / "docs" / "marketing" / "02_content_arsenal.md"

# Outside backend/: skip where the image does not ship it (pattern of 18da165c).
pytestmark = pytest.mark.skipif(
    not (TOOLS / "generate_tip_cards.py").exists() or not ARSENAL.exists(),
    reason="ops/tools or docs/marketing not present (backend-only image)",
)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load("generate_tip_cards")


@pytest.fixture(scope="module")
def autoposter():
    # Importing the autoposter runs its load_dotenv(), which copies the repo's .env
    # into os.environ; undo that so this module cannot change what later tests see.
    with mock.patch.dict(os.environ):
        return _load("social_media_autoposter")


def _numbered_items(heading_prefix: str) -> dict[int, str]:
    """{n: text} of the numbered lines under the `## <heading_prefix>` section.

    A plain re-read of the markdown, independent of both parsers, so that the
    parsers are checked against something other than each other.
    """
    items, inside = {}, False
    for raw in ARSENAL.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            inside = line.startswith(heading_prefix)
            continue
        m = re.match(r"^(\d+)\.\s*(.*)", line) if inside else None
        if m:
            assert int(m.group(1)) not in items, f"{heading_prefix}: item {m.group(1)} repeated in the doc"
            items[int(m.group(1))] = m.group(2).strip()
    return items


# ── the parsers ────────────────────────────────────────────────────────────

def test_generator_reads_exactly_the_tips_bank(generator):
    tips = generator.parse_tips()
    ids = [t["id"] for t in tips]
    assert len(ids) == len(set(ids)), "a tip id appears twice"
    assert sorted(ids) == list(range(1, 31)), ids
    # ...and they are section أ's own lines, word for word
    assert {t["id"]: t["text"] for t in tips} == _numbered_items("## أ)")


def test_no_reel_script_leaks_into_a_card(generator):
    reels = _numbered_items("## ب)")
    tips = {t["id"]: t["text"] for t in generator.parse_tips()}
    # the bug needs ids shared by both lists; if section ب ever stops colliding, say so
    assert reels and set(reels) & set(tips), "section ب no longer shares ids with section أ"
    for n, reel in reels.items():
        assert tips.get(n) != reel, f"card tip_{n} would carry reel script {n}"


def test_generator_and_autoposter_agree_on_every_tip(generator, autoposter):
    posts = autoposter.parse_tips()
    assert len({t["id"] for t in posts}) == len(posts), "the autoposter parsed a tip id twice"
    cards = {t["id"]: (t["category"], t["text"]) for t in generator.parse_tips()}
    assert cards == {t["id"]: (t["category"], t["text"]) for t in posts}


def test_a_repeated_tip_id_is_an_error(generator, tmp_path):
    md = tmp_path / "arsenal.md"
    md.write_text("## أ) بنك\n**دارج (2-3):**\n1. نصيحة\n2. نصيحة ثانية\n1. مكررة\n", encoding="utf-8")
    with pytest.raises(ValueError, match="مكرر"):
        generator.parse_tips(md)


def test_other_sections_are_ignored(generator, tmp_path):
    md = tmp_path / "arsenal.md"
    md.write_text(
        "## أ) بنك\n**دارج (2-3):**\n1. نصيحة\n2. نصيحة ثانية\n\n---\n\n"
        "## ب) سكربتات\n1. **ريل**\n2. **ريل آخر**\n3. **ريل ثالث**\n\n"
        "## ج) تقويم\n1. شيء\n",
        encoding="utf-8",
    )
    tips = generator.parse_tips(md)
    assert [(t["id"], t["text"], t["category"]) for t in tips] == [
        (1, "نصيحة", "دارج (2-3)"),
        (2, "نصيحة ثانية", "دارج (2-3)"),
    ]


def test_a_doc_without_the_tips_section_is_an_error(generator, tmp_path):
    md = tmp_path / "arsenal.md"
    md.write_text("## ب) سكربتات\n1. ريل\n", encoding="utf-8")
    with pytest.raises(ValueError, match="## أ\\)"):
        generator.parse_tips(md)


# ── the rendering ──────────────────────────────────────────────────────────

def test_translucent_shapes_are_blended_not_replaced(generator):
    """The «نصيحة اليوم» chip was drawn with a (r, g, b, 30) fill straight onto an RGBA
    image, which REPLACES the pixel (alpha 30). Platforms that drop alpha showed a
    solid teal pill with teal text on it. Blending keeps every pixel opaque."""
    Image = pytest.importorskip("PIL.Image")
    img = Image.new("RGBA", (200, 100), (200, 200, 200, 255))
    generator.blend_rounded_rect(img, [20, 20, 180, 80], radius=20, fill=(13, 148, 136, 30))
    assert img.getchannel("A").getextrema() == (255, 255)
    r, g, b, _ = img.getpixel((100, 50))
    assert (r, g, b) != (13, 148, 136) and 150 < r < 200, (r, g, b)


def _luminance(px):
    return 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]


def chip_stats(img):
    """(light, teal) pixel counts inside the eyebrow chip: a readable chip has a light
    pill (`light`) AND teal letters on it (`teal`); a solid teal pill has no light."""
    box = img.crop((450, 234, 630, 270)).convert("RGB")
    px = list(box.getdata())
    light = sum(1 for p in px if min(p) >= 200)
    teal = sum(1 for p in px if sum((a - b) ** 2 for a, b in zip(p, (13, 148, 136))) < 40 ** 2)
    return light, teal


def dark_pixels_outside_frame(img):
    """Dark (text-coloured) pixels in the headline + body band, left of x=125 or right of
    x=955: the background art's inner frame lines are at x≈108 and ≈970."""
    band = img.crop((0, 300, 1080, 670)).convert("RGB")
    w, h = band.size
    px = band.load()
    return sum(1 for y in range(h) for x in list(range(0, 125)) + list(range(955, w)) if _luminance(px[x, y]) < 90)


@pytest.mark.parametrize("tip_id", [11, 21, 27])  # the one that was wrong; widest headline; longest body
def test_rendered_card_has_a_visible_chip_and_text_inside_the_frame(generator, tmp_path, tip_id):
    pil_features = pytest.importorskip("PIL.features")
    if generator.qrcode is None or not pil_features.check("raqm"):
        pytest.skip("rendering needs the qrcode package and Pillow with Raqm")
    tip = next(t for t in generator.parse_tips() if t["id"] == tip_id)
    out = tmp_path / f"tip_{tip_id}.png"
    generator.generate_card(tip, out)

    from PIL import Image

    img = Image.open(out)
    assert img.size == (1080, 1080)
    assert img.mode == "RGB", "cards are saved opaque; translucent pixels get flattened differently per platform"
    light, teal = chip_stats(img)
    assert light > 1500 and teal > 150, f"eyebrow chip unreadable (light={light}, teal={teal})"
    assert dark_pixels_outside_frame(img) == 0
