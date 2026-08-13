"""Structural invariants of docs/lesson_index.json.

These are data-level checks with no media on disk, so they run in CI and inside
the deploy candidate image, where mp3/mp4 files are absent by design.

Two incidents motivate them:

  * One byte-identical podcast was listed under three different lessons, so two
    age groups played audio about someone else's topic. Nothing noticed.
  * The 0-3 -> prenatal-1 age-band migration rewrote video filenames from the
    age_group + topic_path pair instead of the lesson's curriculum path_id, so
    18 lessons pointed at 7 files that were never generated, and the API served
    those paths without complaint.
"""
import json
from pathlib import Path

import pytest

from app.media_naming import VIDEO_READ_TAGS

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "docs" / "lesson_index.json"
CURRICULUM = REPO_ROOT / "knowledge_base" / "curriculum" / "lessons"


@pytest.fixture(scope="module")
def lessons():
    return json.loads(INDEX.read_text(encoding="utf-8"))["lessons"]


def _curriculum_path_id(lesson_id):
    f = CURRICULUM / f"{lesson_id}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8")).get("path_id")


def test_no_podcast_file_is_shared_by_two_lessons(lessons):
    """A podcast belongs to exactly one lesson; sharing one means wrong audio."""
    owner = {}
    collisions = []
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        for podcast in (lesson.get("assets") or {}).get("podcasts") or []:
            f = podcast.get("file")
            if not f:
                continue
            if f in owner:
                collisions.append(f"{f} → {owner[f]} and {lid}")
            else:
                owner[f] = lid
    assert not collisions, "podcast served to more than one lesson:\n" + "\n".join(collisions)


def test_path_video_filenames_follow_curriculum_path_id(lessons):
    """Path-video filenames are derived from path_id, never from the age band.

    Path videos are shared by every lesson on the path, so a lesson's reference
    must equal path_videos/<its curriculum path_id>_<lang tag>.mp4. Deriving the
    name any other way is what produced the 18 dead references.

    The language tag is a set, not a constant: the invariant this test protects
    is the *path_id* half of the name. Pinning `_ar_eg` here as well would fire
    on the first English path video and read as a real regression, in a test
    written to catch a real incident, at the moment someone is shipping English
    media. The tag is verbatim the NotebookLM `--language` argument that wrote
    the file, so it stays checkable against the command.
    """
    tags = {tag for tags in VIDEO_READ_TAGS.values() for tag in tags}
    wrong = []
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        path_id = _curriculum_path_id(lid)
        if not path_id:
            continue
        for video in (lesson.get("assets") or {}).get("videos") or []:
            f = video.get("file") or ""
            if not f.startswith("docs/path_videos/"):
                continue  # per-lesson overview video, named after the lesson
            expected = {f"docs/path_videos/{path_id}_{tag}.mp4" for tag in tags}
            if f not in expected:
                wrong.append(
                    f"{lid}: {f} (curriculum path_id says one of {sorted(expected)})")
    assert not wrong, "path video does not match its path_id:\n" + "\n".join(wrong)


def test_every_media_entry_declares_a_language(lessons):
    """Language is data, not something the loader should have to infer.

    Exactly one entry omitted it, and the inference that covered for it served
    37.8 MB of Arabic to English users. The loader now defaults untagged to
    Arabic; this keeps the data honest so the default stays unused.
    """
    untagged = []
    for lesson in lessons:
        assets = lesson.get("assets") or {}
        for kind in ("podcasts", "videos"):
            for entry in assets.get(kind) or []:
                if not (entry.get("language") or "").strip():
                    untagged.append(
                        f"{lesson.get('lesson_id')}: {kind} {entry.get('file')}")
    assert not untagged, "media entry with no language:\n" + "\n".join(untagged)


def test_arabic_podcast_filenames_carry_no_language_tag(lessons):
    """The 214 Arabic podcasts are frozen as `<lesson_id>_podcast.mp3`.

    English adds `_en`; Arabic stays bare. Renaming Arabic to `_ar` for symmetry
    would cost a 7.35 GB re-rsync and rewrite every index entry, for no
    functional gain — this test exists to stop that tidy-up.
    """
    wrong = []
    for lesson in lessons:
        for p in (lesson.get("assets") or {}).get("podcasts") or []:
            f, lang = p.get("file") or "", (p.get("language") or "").lower()
            if lang == "ar" and f.endswith("_ar.mp3"):
                wrong.append(f"{lesson.get('lesson_id')}: {f}")
    assert not wrong, "Arabic podcast carries a language tag:\n" + "\n".join(wrong)


def test_no_reference_uses_a_renamed_age_band(lessons):
    """`prenatal-1` names a curriculum age group, never a path-video file.

    Every path video on disk uses the `path_0-3_` prefix. A `path_prenatal-1_`
    reference can therefore only ever resolve to nothing.
    """
    offenders = []
    for lesson in lessons:
        lid = lesson.get("lesson_id")
        for kind in ("videos", "podcasts"):
            for entry in (lesson.get("assets") or {}).get(kind) or []:
                f = entry.get("file") or ""
                if "path_prenatal-1_" in f:
                    offenders.append(f"{lid}: {f}")
    assert not offenders, "reference to a non-existent age-band filename:\n" + "\n".join(offenders)


# ── Path duration must reflect the lessons that exist ────────────────────────

def test_paths_do_not_promise_more_days_than_content():
    """A path may not advertise more than 3 days per lesson.

    Reported by voice note on 2026-08-02: a mother opened a path badged «28
    يوم», found four lessons, finished them in one sitting, and asked why.
    estimated_days had been set aspirationally — the same four-lesson shape
    carried values from 10 to 28 days across the catalogue, so the badge was
    not derived from anything. 3/lesson is the loosest ratio any well-formed
    path used, so nothing claims more pacing than the app's own best example.

    The real fix is more lessons; this only stops the number being a promise
    the content cannot keep.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "knowledge_base/curriculum"
    offenders = []
    for sub in ("paths", "i18n/en/paths"):
        for f in sorted((root / sub).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            n = len(d.get("lesson_ids") or [])
            days = d.get("estimated_days")
            if not (isinstance(days, int) and n):
                continue
            if days > n * 3:
                offenders.append(f"{sub}/{d.get('id')}: {days}d / {n} lessons")
    assert not offenders, "paths promising more than 3 days per lesson:\n  " + \
        "\n  ".join(offenders)
