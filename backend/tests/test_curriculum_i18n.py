"""English lessons must actually reach English users.

All 170 lessons, 39 paths and 210 daily tips have been translated and sit in
knowledge_base/curriculum/i18n/en/ — but `GET /api/program/lessons/{id}` took
no language argument at all, so every user got Arabic no matter what the app
was set to. Two users reported it from inside the app on 2026-08-02 and
2026-08-03 («أغير الإعدادات إلى اللغة الإنجليزية لكن الدروس باللغة العربية»),
and 27% of the active base is on English devices.

Arabic is the fallback everywhere: a missing translation must degrade to the
Arabic entry, never to a 404 or an empty field.
"""
import pytest
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.main import app


@pytest.fixture
def client():
    # Function-scoped on purpose: conftest sets CHILD_MODE_SECRET per test via
    # monkeypatch, and app startup fails closed without it. A module-scoped
    # client would build the app before that fixture runs.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sample_lesson_id():
    cl.load_curriculum()
    lessons = [lid for lid in cl._lessons_cache]
    assert lessons, "no lessons loaded — fixture cannot run"
    return sorted(lessons)[0]


def test_english_translations_are_present_on_disk():
    """Guard the premise: if the files vanish, the rest of this file lies."""
    assert cl.I18N_DIR.exists(), f"missing {cl.I18N_DIR}"
    assert list((cl.I18N_DIR / "en" / "lessons").glob("*.json")), \
        "no English lesson translations on disk"


def test_get_lesson_returns_english_when_asked(sample_lesson_id):
    cl.load_curriculum()
    ar = cl.get_lesson(sample_lesson_id)
    en = cl.get_lesson(sample_lesson_id, lang="en")
    assert ar and en
    assert en["id"] == ar["id"], "translation must keep the same id"
    assert en["title"] != ar["title"], "English title should differ from Arabic"


def test_get_lesson_falls_back_to_arabic_for_unknown_language(sample_lesson_id):
    cl.load_curriculum()
    ar = cl.get_lesson(sample_lesson_id)
    assert cl.get_lesson(sample_lesson_id, lang="de") == ar
    assert cl.get_lesson(sample_lesson_id, lang=None) == ar


def test_lesson_endpoint_honours_lang_query(client, sample_lesson_id):
    ar = client.get(f"/api/program/lessons/{sample_lesson_id}")
    en = client.get(f"/api/program/lessons/{sample_lesson_id}?lang=en")
    assert ar.status_code == en.status_code == 200
    assert en.json()["title"] != ar.json()["title"]


def test_lesson_endpoint_honours_accept_language(client, sample_lesson_id):
    """The app may not pass ?lang=; the header is the documented fallback and
    is already used by /lesson-assets."""
    ar = client.get(f"/api/program/lessons/{sample_lesson_id}")
    en = client.get(
        f"/api/program/lessons/{sample_lesson_id}",
        headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    assert en.status_code == 200
    assert en.json()["title"] != ar.json()["title"]


def test_paths_listing_honours_lang(client):
    ar = client.get("/api/program/paths")
    en = client.get("/api/program/paths?lang=en")
    assert ar.status_code == en.status_code == 200
    ar_titles = [p["title"] for p in ar.json().get("paths", ar.json())]
    en_titles = [p["title"] for p in en.json().get("paths", en.json())]
    assert ar_titles and en_titles
    assert ar_titles != en_titles
