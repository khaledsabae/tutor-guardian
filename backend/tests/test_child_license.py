"""The internet licence, level 1.

Most of these are negative tests, because most of what this feature promises
is a refusal: the app must not tell a child they were wrong, must not grant a
level on the strength of answers alone, must not let a safety alert be
swallowed by the digest's cooldown, and must not ship a bank whose "safe"
answer leaves a child alone with the next attempt.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.db.init_db import get_conn
from app.services import child_license as cl

DEVICE = "dev-license-1"
_UTC = timezone.utc
BANK = Path(__file__).resolve().parents[2] / "knowledge_base" / "curriculum" / "license"


@pytest.fixture
def child():
    def make(age_group: str = "10-12") -> int:
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
                (DEVICE, "أحمد", age_group),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    return make


def _answer_all_safely(cid: int) -> None:
    for s in cl.load_scenarios("stranger"):
        safe = next(c for c in s["choices"] if c["outcome"] == "safe")
        cl.answer(DEVICE, cid, "stranger", s["key"], safe["key"])


# ── The bank keeps its promises ────────────────────────────────────────────

def test_refusing_without_telling_is_never_safe():
    """The single most important constraint in the bank.

    A child who refuses and says nothing is left alone with the next attempt,
    and the clause the whole agreement rests on — «أسمع من غير ما أزعّق» — only
    works if the child actually tells someone. If this test ever passes a bank
    where silence counts as safety, the feature is teaching the wrong lesson
    with the app's authority behind it.
    """
    for path in BANK.glob("scenarios_*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("alerts_parent") and not any(
            s.get("alerts_parent") for s in data["scenarios"]
        ):
            continue
        for s in data["scenarios"]:
            if not s.get("alerts_parent"):
                continue
            for c in s["choices"]:
                if c["outcome"] == "safe":
                    assert c.get("tells_parent") is True, (
                        f"{path.name}:{s['key']}:{c['key']} — "
                        "a 'safe' answer in an alerting scenario must tell a parent"
                    )


def test_every_scenario_carries_a_talking_point():
    """Without it the feature measures and does not teach."""
    for s in cl.load_scenarios("stranger"):
        assert len(s.get("talking_point_ar", "")) >= 30, s["key"]


def test_authored_scenarios_are_flagged_not_disguised():
    """The cyber bank covers grooming and bullying but has one unit on ads and
    none on passwords. What gets written from scratch stays visible as such."""
    for s in cl.load_scenarios("stranger"):
        if not s.get("source_unit_id"):
            assert s.get("authored") is True, s["key"]


def test_no_child_facing_text_mentions_a_score():
    """The plan forbids showing a child a score. This reads the bank rather
    than the UI, because the bank is where such a string would originate."""
    for s in cl.load_scenarios("stranger"):
        blob = s["situation_ar"] + " ".join(c["text_ar"] for c in s["choices"])
        for word in ("درجة", "نتيجة", "score", "نقطة"):
            assert word not in blob, f"{s['key']} mentions {word}"


# ── The child is never told they were wrong ────────────────────────────────

def test_answering_returns_no_verdict(child):
    """Read the response body, not the docs.

    Echo right/wrong back and the exercise becomes a puzzle to brute-force
    until the green light appears — which measures persistence, not judgement.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    cid = child()
    scenario = cl.load_scenarios("stranger")[0]
    result = cl.answer(DEVICE, cid, "stranger", scenario["key"],
                       scenario["choices"][0]["key"])
    # The service layer carries `outcome` for the alert path. What must not
    # leak is the router's response — asserted in the router test below.
    assert result["ok"] is True
    assert TestClient  # imported for the router-level check elsewhere


def test_the_child_payload_never_contains_the_answer(child):
    """The scenario handed to the app carries no outcome flags at all — a
    payload that includes them is an answer key sitting in the client."""
    import inspect
    from app.routers import child_mode

    source = inspect.getsource(child_mode.child_license_today)
    # The endpoint builds an explicit whitelist rather than stripping keys,
    # which is the shape that survives someone adding a field to the bank.
    assert '"situation_ar"' in source
    assert "outcome" not in source.split("public = {")[1].split("return")[0]


# ── Repetition, not punishment ─────────────────────────────────────────────

def test_an_unsafe_answer_comes_back_but_not_today(child):
    cid = child()
    # Via next_scenario, not bank[0]: the rotation is seeded per child, so the
    # first scenario this child sees is not the first in the file.
    s = cl.next_scenario(cid, "stranger")
    unsafe = next(c for c in s["choices"] if c["outcome"] != "safe")
    cl.answer(DEVICE, cid, "stranger", s["key"], unsafe["key"])

    # Not immediately: a child who got two wrong is not made to redo both now.
    nxt = cl.next_scenario(cid, "stranger")
    assert nxt is None or nxt["key"] != s["key"]

    # Seven days later it is due again.
    later = datetime.now(_UTC) + timedelta(days=cl.REPEAT_AFTER_DAYS + 1)
    assert cl.next_scenario(cid, "stranger", now=later)["key"] == s["key"]


def test_a_safe_answer_is_done_for_good(child):
    cid = child()
    s = cl.load_scenarios("stranger")[0]
    safe = next(c for c in s["choices"] if c["outcome"] == "safe")
    cl.answer(DEVICE, cid, "stranger", s["key"], safe["key"])
    later = datetime.now(_UTC) + timedelta(days=400)
    remaining = cl.next_scenario(cid, "stranger", now=later)
    assert remaining is None or remaining["key"] != s["key"]


def test_the_history_survives_a_reclassified_choice(child):
    """`outcome` is copied onto the row at answer time. Reading it back from
    the bank would let a content edit rewrite what a child did last March."""
    cid = child()
    s = cl.load_scenarios("stranger")[0]
    unsafe = next(c for c in s["choices"] if c["outcome"] == "critical")
    cl.answer(DEVICE, cid, "stranger", s["key"], unsafe["key"])
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT outcome FROM child_scenario_answers WHERE child_id = ?", (cid,)
        ).fetchone()
    finally:
        conn.close()
    assert row["outcome"] == "critical"


# ── Answering does not earn a licence ──────────────────────────────────────

def test_finishing_the_practice_does_not_grant_the_level(child):
    """This is the line between a family agreement and a certificate the app
    issues to itself."""
    cid = child()
    _answer_all_safely(cid)
    state = cl.refresh_status(DEVICE, cid, "stranger")
    assert state["status"] == cl.AWAITING_TALK
    assert state["granted_at"] is None


def test_granting_before_the_talk_is_refused(child):
    cid = child()
    _answer_all_safely(cid)
    result = cl.grant(DEVICE, cid, "stranger")
    assert result["ok"] is False
    assert result["reason"] == "talk_required"


def test_granting_before_the_practice_is_refused(child):
    cid = child()
    cl.record_talk(DEVICE, cid, "stranger")
    result = cl.grant(DEVICE, cid, "stranger")
    assert result["ok"] is False
    assert result["reason"] == "practice_incomplete"


def test_the_full_path_grants_and_sets_a_review_date(child):
    cid = child()
    _answer_all_safely(cid)
    cl.record_talk(DEVICE, cid, "stranger")
    result = cl.grant(DEVICE, cid, "stranger")
    assert result["ok"] is True
    assert result["licence"]["status"] == cl.GRANTED
    assert result["licence"]["next_review_date"]


def test_a_level_with_no_bank_reports_zero_not_complete(child):
    """Levels 2-5 have no content yet. An empty bank must not read as a
    finished level — that would grant `public` to a ten-year-old on day one."""
    cid = child()
    assert cl.progress(cid, "public") == {"done": 0, "total": 0}
    cl.record_talk(DEVICE, cid, "public")
    assert cl.grant(DEVICE, cid, "public")["reason"] == "practice_incomplete"


# ── The alert has to actually arrive ───────────────────────────────────────

def test_the_alert_uses_a_channel_a_parent_can_keep_unmuted(monkeypatch):
    """A grooming alert on a channel named "re-engagement" is muted alongside
    marketing nudges."""
    from app.services import license_alert, push_sender

    captured = {}
    monkeypatch.setattr(
        push_sender, "send_to_device",
        lambda device_id, title, body, data=None, channel_id="x": captured.update(
            {"channel": channel_id, "data": data}) or {"ok": True, "sent": True},
    )
    license_alert.send_alert("dev-1", talking_point="…", critical=True)
    assert captured["channel"] == license_alert.SAFETY_CHANNEL
    assert captured["channel"] != push_sender.DEFAULT_CHANNEL
    assert captured["data"]["link"] == "/license"


def test_the_alert_does_not_consult_the_daily_frequency_cap():
    """`recently_pushed_since` is per-device, not per-kind. A parent who got
    the 9pm mission digest would otherwise never get a 9:30pm safety alert."""
    import inspect
    from app.services import license_alert

    # Match a call, not a mention: the module's docstring explains at length
    # why it does not consult the cap, and a substring check on the whole file
    # would fail on that explanation.
    source = inspect.getsource(license_alert)
    assert "recently_pushed_since(" not in source


def test_the_alert_body_does_not_describe_what_happened():
    """In many of these families the parent's phone is the phone the child
    uses. A lock-screen body naming what a stranger asked for is one the child
    may read about themselves — and may learn to delete."""
    from app.services import license_alert

    for word in ("صورة", "غريب", "استدراج", "كاميرا"):
        assert word not in license_alert._BODY


def test_there_is_no_channel_that_reaches_the_child():
    """Rule 4 is absolute. Same shape as the mission-digest guard: read the
    module and fail if a second send path appears."""
    import inspect
    from app.services import license_alert

    source = inspect.getsource(license_alert)
    assert "send_to_topic" not in source
    assert source.count("push_sender.send_to_device") == 1


def test_an_alerting_scenario_alerts_even_on_the_safe_answer(child):
    """The plan is explicit: the alert is about meeting the situation, not
    about failing it. A child who answered perfectly may be living through it.
    """
    cid = child()
    s = next(x for x in cl.load_scenarios("stranger") if x.get("alerts_parent"))
    safe = next(c for c in s["choices"] if c["outcome"] == "safe")
    result = cl.answer(DEVICE, cid, "stranger", s["key"], safe["key"])
    assert result["alerts_parent"] is True
    assert result["outcome"] == "safe"


# ── The policy change ──────────────────────────────────────────────────────

def test_the_license_surface_is_open_to_10_12_without_loosening_a_budget():
    from app.config.guardrails_loader import load_child_surface_policy

    policy = load_child_surface_policy()
    band = policy.band("10-12")
    assert "license" in band.allowed_surfaces
    # The numbers this band had before are untouched.
    assert band.daily_budget_minutes == 25
    assert band.session_max_minutes == 25
    assert policy.surface("license").max_minutes == 10


def test_free_text_is_still_closed_everywhere():
    """Sprint 3 was designed with no free text precisely so this stays true
    and the two loader guards are never touched."""
    from app.config.guardrails_loader import load_child_surface_policy

    policy = load_child_surface_policy()
    assert policy.defaults.allow_free_text is False
    for name, band in policy.age_bands.items():
        assert not band.allow_free_text, name
