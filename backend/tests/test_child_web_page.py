"""The teen QR page (backend/static/child_mode/index.html) against the API it
calls and the app it belongs to (UX_UI_ROADMAP §4.3, AUDIT H8).

It is plain HTML/JS with no build step, so nothing else checks that its
strings still match the server — which is how "partial" (the API says
"partially") shipped and failed on every tap.
"""
import re
from pathlib import Path

from app.models.value_tracking import CATEGORIES as SERVER_CATEGORIES, STATUSES

PAGE = (Path(__file__).resolve().parents[1] / "static" / "child_mode" / "index.html").read_text(
    encoding="utf-8"
)


def test_every_status_button_sends_a_status_the_api_accepts():
    sent = set(re.findall(r'data-status="([a-z_]+)"', PAGE))
    assert sent == STATUSES


def test_every_server_category_has_an_icon_and_a_label():
    for fn in ("categoryIcon", "categoryLabel"):
        body = PAGE.split(f"function {fn}(cat)", 1)[1].split("}", 2)[0]
        keys = set(re.findall(r"(\w+):", body))
        assert SERVER_CATEGORIES <= keys, (fn, keys)


def test_parent_typed_names_never_reach_markup_unescaped():
    # H8: habit names include parent-typed custom templates. Every interpolation
    # inside the card's innerHTML goes through esc(); the child's name is only
    # ever set with textContent.
    template = PAGE.split("el.innerHTML = `", 1)[1].split("`;", 1)[0]
    for expr in re.findall(r"\$\{([^}]*)\}", template):
        assert expr.strip().startswith("esc("), expr
    assert "innerHTML" not in PAGE.split("child_name", 1)[0].rsplit("\n", 1)[-1]
    assert re.search(r"textContent\s*=\s*`[^`]*\$\{data\.child_name", PAGE)


def test_missed_is_neutral_and_the_palette_is_the_apps():
    missed = re.search(r'data-status="missed" class="([^"]+)"', PAGE).group(1)
    assert "rose" not in missed and "red" not in missed
    assert "--tg-primary: #10B981" in PAGE  # AppPalette.dark.primary
    assert "family=Cairo" in PAGE
