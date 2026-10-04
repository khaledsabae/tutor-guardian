"""MOBILE_API.md §11 documents every family-program endpoint.

The mobile build is written from that document alone, so an endpoint missing
from it is an endpoint the app will not call. MOBILE_API.md lives at the repo
root, which the backend-only deploy image does not ship: this skips there and
runs in PR CI (the pattern of 18da165c).
"""
import re
from pathlib import Path

import pytest

from app.routers.family_programs import router

DOC = Path(__file__).resolve().parents[2] / "MOBILE_API.md"
pytestmark = pytest.mark.skipif(not DOC.exists(),
                                reason="MOBILE_API.md not present (backend-only image)")


def _routes():
    for route in router.routes:
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield method, "/api" + route.path


@pytest.mark.parametrize("method,path", list(_routes()))
def test_every_endpoint_is_in_the_contract(method, path):
    text = DOC.read_text(encoding="utf-8")
    pattern = re.escape(f"{method} {path}") + r"(?![\w/{-])"
    assert re.search(pattern, text), f"{method} {path} is not documented in MOBILE_API.md §11"


def test_the_deep_link_and_the_server_settings_are_documented():
    text = DOC.read_text(encoding="utf-8")
    for needle in ("/milestones/{child_id}/{milestone_key}", "MILESTONES_MIN_BUILD",
                   "RAMADAN_START_", "RAMADAN_DAYS_", "PROGRAMS_AS_OF_ENABLED",
                   "family_only", "requires_feature"):
        assert needle in text, needle
