"""Story pre-generation cache tests (growth plan §5.1).

The cache must: only serve gendered variants, personalize the hero name,
reject too-short or hero-less stories, resolve gender only for children the
device actually owns, and fall back silently (None) in every doubtful case.
"""
import pytest

from app.db.init_db import get_conn, init_db
from app.services import story_service

STORY = (
    "العنوان: سالم والصدق\n\n"
    "كان سالم ولداً صغيراً يحب اللعب في الحديقة مع أصدقائه كل مساء بعد أن "
    "ينهي واجباته المدرسية بنشاط وهمة عالية.\n\n"
    "وفي يوم من الأيام كسر سالم مزهرية أمه وهو يلعب بالكرة داخل البيت، "
    "فوقف حائراً بين أن يخفي الأمر أو يقول الحقيقة كاملة لأمه الحبيبة.\n\n"
    "قرر سالم أن يصدق مهما كان الثمن، فذهب إلى أمه واعترف لها بما حدث، "
    "فابتسمت أمه وقالت له: صدقك أغلى عندي من ألف مزهرية يا حبيبي.\n\n"
    "الدرس المستفاد: الصدق يجعلك أقرب إلى الله وإلى قلوب من تحب."
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    init_db()
    yield


def test_store_and_serve_round_trip():
    assert story_service.store_pregen_story("honesty", "4-6", "male", "سالم", STORY)
    hit = story_service.get_cached_story("honesty", "4-6", "male")
    assert hit is not None
    assert hit["hero_name"] == "سالم"
    assert "سالم" in hit["story"]


def test_personalize_replaces_every_occurrence():
    out = story_service.personalize(STORY, "سالم", "يوسف")
    assert "سالم" not in out
    assert out.count("يوسف") == STORY.count("سالم")


def test_no_gender_means_no_cache_hit():
    story_service.store_pregen_story("honesty", "4-6", "male", "سالم", STORY)
    assert story_service.get_cached_story("honesty", "4-6", None) is None
    assert story_service.get_cached_story("honesty", "4-6", "other") is None


def test_wrong_key_misses():
    story_service.store_pregen_story("honesty", "4-6", "male", "سالم", STORY)
    assert story_service.get_cached_story("courage", "4-6", "male") is None
    assert story_service.get_cached_story("honesty", "7-9", "male") is None
    assert story_service.get_cached_story("honesty", "4-6", "female") is None


def test_validation_rejects_bad_stories():
    assert not story_service.store_pregen_story("honesty", "4-6", "male", "سالم", "قصير")
    no_hero = STORY.replace("سالم", "ماجد")
    assert not story_service.store_pregen_story("honesty", "4-6", "male", "سالم", no_hero)


def test_resolve_child_gender_enforces_ownership():
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group, gender) "
            "VALUES ('dev-A', 'مريم', '4-6', 'female')"
        )
        child_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    assert story_service.resolve_child_gender("dev-A", child_id) == "female"
    assert story_service.resolve_child_gender("dev-B", child_id) is None
    assert story_service.resolve_child_gender("dev-A", 99999) is None
    assert story_service.resolve_child_gender(None, child_id) is None
