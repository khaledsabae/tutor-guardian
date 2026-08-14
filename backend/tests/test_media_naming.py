"""Media naming is a contract between the API and the generators.

Both sides used to derive it independently, which produced two live defects:
a 37.8 MB Arabic podcast served to English users, and skip-predicates that
would make an English generation run inspect the Arabic file, skip every
lesson, and exit 0 having produced nothing.
"""
import pytest

from app.media_naming import (
    AUDIO_CLI_LANG,
    MIN_PODCAST_BYTES,
    PODCAST_TAG,
    SOURCE_LANG,
    VIDEO_CLI_LANG,
    VIDEO_WRITE_TAG,
    language_of_filename,
    norm_lang,
    path_video_candidates,
    path_video_rel,
    podcast_rel,
)


def test_arabic_podcast_name_is_untagged():
    """The 214 shipped files. Tagging them would cost a 7.35 GB re-rsync."""
    assert podcast_rel("lesson_0-3_x_01") == "docs/lesson_0-3_x_01_podcast.mp3"
    assert podcast_rel("lesson_0-3_x_01", "ar") == podcast_rel("lesson_0-3_x_01")


def test_english_podcast_name_is_distinct_from_arabic():
    """The skip-predicate bug: if these collided, an English run would see the
    Arabic file, judge it complete, and skip all 170 lessons silently."""
    assert podcast_rel("l1", "en") == "docs/l1_podcast_en.mp3"
    assert podcast_rel("l1", "en") != podcast_rel("l1", "ar")


def test_path_video_write_names():
    assert path_video_rel("p1") == "docs/path_videos/p1_ar_eg.mp4"
    assert path_video_rel("p1", "en") == "docs/path_videos/p1_en_us.mp4"


def test_english_video_falls_back_to_arabic_but_not_the_reverse():
    en = path_video_candidates("p1", "en")
    assert en[0] == "docs/path_videos/p1_en_us.mp4"
    assert en[-1] == "docs/path_videos/p1_ar_eg.mp4", "English must fall back"
    ar = path_video_candidates("p1", "ar")
    assert ar == ("docs/path_videos/p1_ar_eg.mp4",), \
        "Arabic must never fall forward to English"


def test_english_video_reader_accepts_both_plausible_tags():
    """The code NotebookLM honours for English video is not confirmed until a
    real generation runs. A reader that knew only one would strand a directory
    of correct files while reporting no English video."""
    en = path_video_candidates("p1", "en")
    assert "docs/path_videos/p1_en.mp4" in en
    assert "docs/path_videos/p1_en_us.mp4" in en


@pytest.mark.parametrize("name,expected", [
    ("docs/lesson_01_podcast.mp3", "ar"),          # the file that was mislabelled
    ("docs/lesson_0-3_x_01_podcast.mp3", "ar"),
    ("docs/lesson_x_podcast_en.mp3", "en"),
    ("docs/path_videos/p1_ar_eg.mp4", "ar"),
    ("docs/path_videos/p1_en_us.mp4", "en"),
    ("docs/path_videos/p1_en.mp4", "en"),
    ("no_tag_at_all.mp4", "ar"),
])
def test_language_of_filename(name, expected):
    assert language_of_filename(name) == expected


def test_language_of_filename_round_trips_every_writer():
    """Anything the writers emit must be readable back as the same language."""
    for lang in ("ar", "en"):
        assert language_of_filename(podcast_rel("lesson_x", lang)) == lang
        assert language_of_filename(path_video_rel("p1", lang)) == lang


@pytest.mark.parametrize("raw,expected", [
    ("en-US,en;q=0.9", "en"), ("EN", "en"), ("ar", "ar"),
    ("de", "ar"), ("", "ar"), (None, "ar"), ("en_US", "en"),
])
def test_norm_lang(raw, expected):
    assert norm_lang(raw) == expected


def test_every_language_is_defined_across_all_four_tables():
    """A language half-added is how a generator writes a file the API cannot
    find. Adding French means all four tables, and this test says so."""
    langs = set(PODCAST_TAG)
    for table, name in ((AUDIO_CLI_LANG, "AUDIO_CLI_LANG"),
                        (VIDEO_CLI_LANG, "VIDEO_CLI_LANG"),
                        (VIDEO_WRITE_TAG, "VIDEO_WRITE_TAG")):
        assert set(table) == langs, f"{name} disagrees with PODCAST_TAG"
    assert SOURCE_LANG in langs
    assert PODCAST_TAG[SOURCE_LANG] == "", "the source language carries no tag"


def test_thresholds_are_a_single_number():
    """Four generators used 500 KB, 2 MB, 10 KB and 10 MB for the same check."""
    assert MIN_PODCAST_BYTES == 2 * 1024 * 1024


# ── Index registration ────────────────────────────────────────────────────
# A generated file that is not in the index never reaches a user: the
# /lesson-assets endpoint reads docs/lesson_index.json, not the disk. Three
# English episodes sat on disk with zero index entries while English users kept
# being served Arabic.


def _upsert():
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "ops" / "tools" / "media_index.py"
    spec = importlib.util.spec_from_file_location("media_index", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_upsert_adds_english_without_erasing_arabic(tmp_path):
    """`assets["podcasts"] = [...]` — what regen_podcasts.py does — would drop
    the Arabic reference on the first English download. The file stays on disk,
    so check_served_assets sees nothing wrong and every Arabic user silently
    loses their podcast at the next deploy."""
    import json
    m = _upsert()
    idx = tmp_path / "lesson_index.json"
    idx.write_text(json.dumps({"lessons": [{"lesson_id": "L1", "assets": {
        "podcasts": [{"file": "docs/L1_podcast.mp3", "language": "ar"}]}}]}))

    assert m.upsert_media("L1", "podcasts", {
        "file": "docs/L1_podcast_en.mp3", "language": "en"}, idx) == "inserted"
    pods = json.loads(idx.read_text())["lessons"][0]["assets"]["podcasts"]
    assert {p["language"] for p in pods} == {"ar", "en"}


def test_upsert_is_idempotent_per_language(tmp_path):
    import json
    m = _upsert()
    idx = tmp_path / "lesson_index.json"
    idx.write_text(json.dumps({"lessons": [{"lesson_id": "L1", "assets": {}}]}))
    m.upsert_media("L1", "podcasts", {"file": "a.mp3", "language": "en", "size_bytes": 1}, idx)
    assert m.upsert_media("L1", "podcasts",
                          {"file": "a.mp3", "language": "en", "size_bytes": 2}, idx) == "replaced"
    pods = json.loads(idx.read_text())["lessons"][0]["assets"]["podcasts"]
    assert len(pods) == 1 and pods[0]["size_bytes"] == 2


def test_upsert_treats_ar_eg_as_arabic(tmp_path):
    """Video entries declare `ar_eg`, podcasts `ar`. Comparing raw strings
    would let a second Arabic entry in alongside the first."""
    import json
    m = _upsert()
    idx = tmp_path / "lesson_index.json"
    idx.write_text(json.dumps({"lessons": [{"lesson_id": "L1", "assets": {
        "videos": [{"file": "v_ar_eg.mp4", "language": "ar_eg"}]}}]}))
    assert m.upsert_media("L1", "videos",
                          {"file": "v2_ar_eg.mp4", "language": "ar"}, idx) == "replaced"
    assert len(json.loads(idx.read_text())["lessons"][0]["assets"]["videos"]) == 1


def test_upsert_refuses_an_entry_with_no_language(tmp_path):
    """An unlabelled entry is what made 37.8 MB of Arabic get served as
    English. The writer must not be able to create one."""
    import json
    import pytest as _pytest
    m = _upsert()
    idx = tmp_path / "lesson_index.json"
    idx.write_text(json.dumps({"lessons": [{"lesson_id": "L1", "assets": {}}]}))
    with _pytest.raises(ValueError):
        m.upsert_media("L1", "podcasts", {"file": "a.mp3"}, idx)
