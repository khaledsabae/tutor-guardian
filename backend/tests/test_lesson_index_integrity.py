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
    must equal path_videos/<its curriculum path_id>_ar_eg.mp4. Deriving the name
    any other way is what produced the 18 dead references.
    """
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
            expected = f"docs/path_videos/{path_id}_ar_eg.mp4"
            if f != expected:
                wrong.append(f"{lid}: {f} (curriculum path_id says {expected})")
    assert not wrong, "path video does not match its path_id:\n" + "\n".join(wrong)


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
