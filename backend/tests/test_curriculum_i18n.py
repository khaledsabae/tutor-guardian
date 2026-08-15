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
from pathlib import Path
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.media_naming import language_of_filename
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


# ── Daily tips ────────────────────────────────────────────────────────────
# All 210 tips were translated in the same pass as the lessons, but the overlay
# loop covered only lessons and paths and `get_daily_tips()` took no language,
# so the English files sat unreachable on disk. This file's docstring claimed
# tips were covered while nothing here tested them.


def test_english_tip_translations_are_present_on_disk():
    assert list((cl.I18N_DIR / "en" / "daily_tips").glob("*.json")), \
        "no English daily-tip translations on disk"


def test_daily_tips_honour_lang():
    cl.load_curriculum()
    ar = cl.get_daily_tips("4-6")
    en = cl.get_daily_tips("4-6", lang="en")
    assert ar and en
    assert [t["id"] for t in ar] == [t["id"] for t in en], \
        "translation must not reorder or drop tips"
    assert [t["text"] for t in ar] != [t["text"] for t in en]


def test_daily_tip_pool_is_language_independent():
    """The per-day pick is `sha256(date:age:time) % len(pool)`.

    If a language changed pool length or order, two parents in one household
    would get different tips on the same day — the one property that hash
    exists to guarantee.
    """
    cl.load_curriculum()
    for age in ("0-3", "4-6", "7-9", "10-12", "13-15", "16-18"):
        ar = [t["id"] for t in cl.get_daily_tips(age)]
        en = [t["id"] for t in cl.get_daily_tips(age, lang="en")]
        assert ar == en, f"pool diverged for age {age}"


def test_daily_tip_endpoint_honours_lang(client):
    ar = client.get("/api/program/daily-tip?age_group=4-6")
    en = client.get("/api/program/daily-tip?age_group=4-6&lang=en")
    assert ar.status_code == en.status_code == 200
    assert ar.json()["id"] == en.json()["id"], "same day must pick the same tip"
    assert ar.json()["text"] != en.json()["text"]


def test_daily_tips_fall_back_to_arabic_for_unknown_language():
    cl.load_curriculum()
    assert cl.get_daily_tips("4-6", lang="de") == cl.get_daily_tips("4-6")


# ── Search ────────────────────────────────────────────────────────────────


def test_search_finds_english_content():
    """An English user has no Arabic string to hit, so until the overlay was
    searched the English curriculum was unreachable except by browsing."""
    cl.load_curriculum()
    assert cl.search("sleep", lang="en"), "English query returned nothing"


def test_search_renders_results_in_requested_language():
    """Same matches, rendered in the asked-for language.

    Compared as sets: results are sorted by title within a rank tier, and the
    localized title sorts differently, so the *order* legitimately differs
    between languages while the match set must not.
    """
    cl.load_curriculum()
    ar = cl.search("النوم", limit=500)
    en = cl.search("النوم", limit=500, lang="en")
    assert ar and en
    assert {r["id"] for r in ar} == {r["id"] for r in en}
    assert [r["title"] for r in ar] != [r["title"] for r in en]


# ── Media language ────────────────────────────────────────────────────────


def test_untagged_media_is_arabic_not_english():
    """Regression: the old inference read "no `_ar` in the name" as English.

    `lesson_10-12_cyber_01` → `docs/lesson_01_podcast.mp3` is 37.8 MB of
    Arabic carrying no `language` key. It matched neither branch, so it was
    handed to English users as English and the Arabic fallback never ran.
    """
    assert cl._media_lang(None, "docs/lesson_01_podcast.mp3") == "ar"
    assert cl._media_lang(None, "docs/lesson_0-3_x_podcast.mp3") == "ar"
    assert cl._media_lang("", "docs/path_videos/p_ar_eg.mp4") == "ar"


def test_tagged_media_language_is_read_not_guessed():
    assert cl._media_lang(None, "docs/lesson_x_podcast_en.mp3") == "en"
    assert cl._media_lang("en-US", "anything.mp3") == "en"
    assert cl._media_lang("ar", "docs/lesson_x_podcast_en.mp3") == "ar", \
        "an explicit tag always wins over the filename"


def test_path_video_prefers_requested_language_then_arabic(monkeypatch):
    """English falls back to Arabic; Arabic never falls forward to English."""
    present = {"docs/path_videos/p1_ar_eg.mp4", "docs/path_videos/p1_en_us.mp4",
               "docs/path_videos/p2_ar_eg.mp4"}
    monkeypatch.setattr(cl, "media_exists", lambda p: p in present)

    en = cl._add_path_video({"id": "p1"}, lang="en")
    assert en["video_mp4"] == "docs/path_videos/p1_en_us.mp4"
    assert en["video_language"] == "en"

    ar = cl._add_path_video({"id": "p1"}, lang="ar")
    assert ar["video_mp4"] == "docs/path_videos/p1_ar_eg.mp4"
    assert ar["video_language"] == "ar"

    # No English video for p2 — fall back, and say so.
    fb = cl._add_path_video({"id": "p2"}, lang="en")
    assert fb["video_mp4"] == "docs/path_videos/p2_ar_eg.mp4"
    assert fb["video_language"] == "ar", \
        "a path badged English must not claim its Arabic video is English"

    assert "video_mp4" not in cl._add_path_video({"id": "nope"}, lang="en")


# ── Visual assets carry a language too ────────────────────────────────────
# An infographic is Arabic text rendered into PIXELS: an English reader gets no
# partial understanding and no fallback is possible, because the text IS the
# image. Yet infographics, reports and data tables were served with
# `items[0].get("file")` — first entry wins, language never consulted.


def test_every_file_bearing_asset_declares_a_language():
    """156 infographics, 224 reports and 260 data tables carried no language."""
    import json
    index = Path(__file__).resolve().parents[2] / "docs" / "lesson_index.json"
    untagged = []
    for lesson in json.loads(index.read_text(encoding="utf-8"))["lessons"]:
        assets = lesson.get("assets") or {}
        for kind in ("podcasts", "videos", "infographics", "reports", "data_tables"):
            for entry in assets.get(kind) or []:
                if entry.get("file") and not (entry.get("language") or "").strip():
                    untagged.append(f"{lesson.get('lesson_id')}: {kind} {entry['file']}")
    assert not untagged, "asset with no language:\n" + "\n".join(untagged[:10])


def test_lesson_assets_report_the_language_actually_served(client):
    """The reported language must describe the file that was actually chosen.

    This asserted `in (None, "ar")` when no English media existed, and broke the
    day the first English infographic landed — it was pinning a snapshot of the
    backlog, not an invariant. Coverage is meant to change; what must not is the
    response describing a file it did not serve.
    """
    cl.load_curriculum()
    lesson_id = sorted(cl._assets_cache)[0]
    r = client.get(f"/api/program/lesson-assets/{lesson_id}?lang=en")
    assert r.status_code == 200
    body = r.json()
    langs = body["languages"]
    assert langs["requested"] == "en"
    for medium, key in (("podcast", "podcast_mp3"), ("video", "video_mp4"),
                        ("infographic", "infographic"), ("report", "report"),
                        ("data_table", "data_table")):
        served, reported = body.get(key), langs[medium]
        if served is None:
            assert reported is None, \
                f"{medium}: nothing served but language reported {reported!r}"
        else:
            assert reported == language_of_filename(served), (
                f"{medium}: serving {served} but reporting {reported!r}")


def test_arabic_video_declared_ar_eg_is_matched_as_arabic(client, monkeypatch):
    """Video entries declare `ar_eg`, podcasts declare `ar`.

    The old code compared those strings raw, so the video fallback branch
    (`language == "ar"`) could never fire and Arabic was returned only because
    it happened to be first in the list.

    Presence is monkeypatched rather than left to the host. This test asks one
    question — does `ar_eg` normalize to `ar` — and it used to answer it only by
    luck: media is gitignored, so it passed on a laptop that had the files and
    would have reported the same 'pass' on CI for the opposite reason, once
    selection began consulting the disk. What a test depends on should be in the
    test.
    """
    cl.load_curriculum()
    with_video = [lid for lid, a in cl._assets_cache.items()
                  if (a.get("videos") or [])]
    assert with_video, "fixture needs a lesson with a video"
    monkeypatch.setattr(cl, "media_exists", lambda p: True)
    r = client.get(f"/api/program/lesson-assets/{with_video[0]}?lang=en")
    assert r.status_code == 200
    assert r.json()["languages"]["video"] == "ar"


def test_a_missing_english_file_falls_back_to_arabic_not_to_nothing(
        client, monkeypatch):
    """An indexed file this host does not have must not cost the fallback too.

    The index runs ahead of the rsync by design, so an English podcast is
    registered before it lands. Choosing the best match first and dropping its
    path afterwards took the Arabic file down with it: the English entry won,
    then vanished at the existence check, and nobody went back for the Arabic
    file sitting on disk. The lesson lost both.
    """
    cl.load_curriculum()
    with_pod = [lid for lid, a in cl._assets_cache.items()
                if len([p for p in (a.get("podcasts") or []) if p.get("file")]) >= 2]
    if not with_pod:
        pytest.skip("fixture needs a lesson with podcasts in two languages")
    lid = with_pod[0]
    pods = cl._assets_cache[lid]["podcasts"]
    arabic = next((p["file"] for p in pods if p.get("language") == "ar"), None)
    assert arabic, "fixture needs an Arabic podcast to fall back to"

    # Everything is on disk except the English file.
    monkeypatch.setattr(cl, "media_exists", lambda p: p == arabic)
    body = client.get(f"/api/program/lesson-assets/{lid}?lang=en").json()
    assert body["podcast_mp3"] == arabic
    assert body["languages"]["podcast"] == "ar"

    # And with nothing on disk at all, the response must claim nothing.
    monkeypatch.setattr(cl, "media_exists", lambda p: False)
    body = client.get(f"/api/program/lesson-assets/{lid}?lang=en").json()
    assert body["podcast_mp3"] is None
    assert body["languages"]["podcast"] is None
