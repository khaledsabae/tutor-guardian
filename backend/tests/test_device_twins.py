"""Device twins (2026-10-04): an install that 1.0.58-1.0.67 split into two
device ids is put back together — and nothing ever crosses families.

The shape every test builds is the one production has: the family's device U
(the visible engine, where the parent onboarded the child) and its childless
twin H (the headless engine), born within seconds, both registered with the
install's one FCM token. The family identity goes quiet after its first
session when the app comes back as the twin. See app/services/device_twins.py;
the review's attack scenarios live in test_device_twins_review.py.
"""
import json
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path, hash_token, init_db
from app.services import conversation_store as store
from app.services import device_twins as twins
from app.services import fiqh_guard

FCM = "fcm-token-of-the-install"
BIRTH = "2026-10-01 08:00:00"            # inside the cohort


# ── fixtures ──────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _born(device: str, at: str = BIRTH) -> str:
    """A session for `device` whose token was issued at `at`. Returns the token."""
    _, token = store.create_session_with_token(device_id=device)
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE token = ?", (at, hash_token(token)))
    return token


_token = _born          # another token for an existing device, issued at `at`


def _child(device: str, name: str = "Child", at: str = "2026-10-01 08:01:00") -> int:
    """A child created (and last edited) at `at` — the first session by default."""
    with _db() as conn:
        return conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group, created_at, updated_at) "
            "VALUES (?, ?, '7-9', ?, ?)", (device, name, at, at)).lastrowid


def _push(device: str, fcm: str = FCM, updated_at: str = "2026-10-01 08:00:05", build: int | None = 111):
    with _db() as conn:
        conn.execute(
            "INSERT INTO push_tokens (device_id, token, platform, updated_at, build_number) "
            "VALUES (?, ?, 'android', ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET token = excluded.token, "
            "updated_at = excluded.updated_at, build_number = excluded.build_number",
            (device, fcm, updated_at, build),
        )


def _rows_of(device: str) -> dict[str, int]:
    out = {}
    with _db() as conn:
        for table, col in twins.device_columns(conn, include_excluded=True):
            if table == "device_aliases":
                continue
            n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = ?', (device,)).fetchone()[0]
            if n:
                out[f"{table}.{col}"] = n
    return out


def _split_install(twin_born: str = "2026-10-01 08:00:01"):
    """U onboarded a child in its first minute; H is the childless twin with
    the same FCM token. U went quiet; the app now runs as H."""
    t_u = _born("U")
    t_h = _born("H", twin_born)
    child = _child("U", "Maryam")
    _push("U", updated_at="2026-10-01 08:00:05")
    _push("H", updated_at="2026-10-01 08:00:06")
    return t_u, t_h, child


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    monkeypatch.delenv("SESSION_MINT_ENFORCE", raising=False)
    monkeypatch.delenv("TWIN_FOLD_BORN_BEFORE", raising=False)
    from app.config.guardrails_loader import load_guardrails_config
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(c: TestClient, token: str, fcm: str = FCM):
    return c.post("/api/push/register", headers=_bearer(token),
                  json={"token": fcm, "platform": "android", "build_number": 112})


def _children(c: TestClient, token: str) -> list[str]:
    r = c.get("/api/children", headers=_bearer(token))
    assert r.status_code == 200, r.text
    return [ch["name"] for ch in r.json()["children"]]


def _mint(c: TestClient, device: str | None, token: str | None = None):
    headers = _bearer(token) if token else {}
    return c.post("/api/chat/sessions", headers=headers, json={"device_id": device} if device else {})


# ── recovery: the app came back as the twin ───────────────────────────────

def test_push_registration_folds_the_twin_into_the_family(client):
    _, t_h, _ = _split_install()
    assert _children(client, t_h) == []                 # what the parent saw

    r = _register(client, t_h)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "device_id": "U", "identity_recovered": True}
    assert _children(client, t_h) == ["Maryam"]        # the token the app holds
    assert store.validate_token(t_h)["device_id"] == "U"
    assert _rows_of("H") == {}
    with _db() as conn:
        # The live request's census, on the family's row; the twin's row is gone.
        assert conn.execute("SELECT build_number FROM push_tokens WHERE device_id = 'U'").fetchone()[0] == 112
        log = [tuple(r) for r in conn.execute("SELECT table_name, action FROM device_fold_log")]
    assert ("api_tokens", "moved") in log
    assert ("push_tokens", "deleted") in log


def test_the_twins_conversations_follow_it(client):
    _, t_h, _ = _split_install()
    sid = store.create_session(device_id="H")
    store.add_message(sid, "user", "a question asked while the app was the twin")
    _register(client, t_h)
    assert client.get(f"/api/chat/sessions/{sid}", headers=_bearer(t_h)).status_code == 200
    assert store.session_owner(sid) == (True, "U")


def test_a_second_registration_finds_nothing_left_to_fold(client):
    _, t_h, _ = _split_install()
    assert _register(client, t_h).json()["identity_recovered"] is True
    assert _register(client, t_h).json() == {"ok": True}   # the other engine of an old build
    assert _children(client, t_h) == ["Maryam"]


def test_minting_with_the_twins_proof_mints_for_the_family(client):
    _, t_h, _ = _split_install()
    r = _mint(client, "H", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _children(client, r.json()["token"]) == ["Maryam"]
    assert _rows_of("H") == {}


def test_disk_says_family_but_proof_is_the_twins(client):
    # The engines' keystore writes interleaved: tg_device_id = U, proof = T_H.
    _, t_h, _ = _split_install()
    r = _mint(client, "U", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _rows_of("H") == {}


def test_disk_says_twin_but_proof_is_the_familys(client):
    # Interleaved the other way: the app runs on the family's token. The proof
    # decides (U); the twin is not folded here — nothing presented is its own.
    t_u, _, _ = _split_install()
    r = _mint(client, "H", t_u)
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _children(client, r.json()["token"]) == ["Maryam"]
    assert _rows_of("H")


def test_an_ordinary_mint_names_its_own_device(client):
    r = _mint(client, "fresh-install")
    assert r.status_code == 201 and r.json()["device_id"] == "fresh-install"
    r = _mint(client, "fresh-install", r.json()["token"])
    assert r.status_code == 201 and r.json()["device_id"] == "fresh-install"


def test_the_family_device_registering_changes_nothing(client):
    t_u, _, _ = _split_install()
    assert _register(client, t_u).json() == {"ok": True}
    assert _rows_of("H")                                  # left for the repair script


# ── the fold must outlast the app's own memory ────────────────────────────

def test_after_the_fold_an_old_build_minting_the_twins_id_gets_the_family(client):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    r = _mint(client, "H")                                # builds < 106: no proof
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _children(client, r.json()["token"]) == ["Maryam"]


def test_after_the_fold_a_proof_carrying_remint_gets_the_family(client):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    r = _mint(client, "H", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "U"


def test_an_alias_does_not_bypass_minting_enforcement(client, monkeypatch):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    assert _mint(client, "H").status_code == 401           # a known device needs proof
    r = _mint(client, "H", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "U"


def test_the_fold_is_remembered_and_older_aliases_follow(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        twins.ensure_device_twin_tables(conn)
        conn.execute("INSERT INTO device_aliases (device_id, canonical_device) VALUES ('older', 'H')")
    _register(client, t_h)
    with _db() as conn:
        rows = dict(conn.execute("SELECT device_id, canonical_device FROM device_aliases").fetchall())
        relogged = conn.execute("SELECT COUNT(*) FROM device_fold_log WHERE table_name = 'device_aliases'"
                                ).fetchone()[0]
    assert rows == {"H": "U", "older": "U"}
    assert relogged == 1


# ── the bounds: outside them nothing folds ────────────────────────────────

def test_no_fold_before_the_first_splitting_build(client):
    _born("U", "2026-09-11 08:00:00")
    _child("U", "Maryam", at="2026-09-11 08:01:00")
    t_h = _born("H", "2026-09-11 08:00:01")
    _push("U", updated_at="2026-09-11 08:00:05")
    _push("H", updated_at="2026-09-11 08:00:06")
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == []


def test_no_fold_for_a_twin_born_after_the_cutoff(client, monkeypatch):
    assert twins.cohort_end().isoformat() == "2026-10-25T00:00:00"     # the default
    monkeypatch.setenv("TWIN_FOLD_BORN_BEFORE", "2026-10-01T08:00:01")
    _, t_h, _ = _split_install()
    assert _register(client, t_h).json() == {"ok": True}
    monkeypatch.setenv("TWIN_FOLD_BORN_BEFORE", "2026-10-02")
    assert _register(client, t_h).json()["identity_recovered"] is True


def test_no_fold_into_a_family_still_in_use(client):
    # A family active after its first session is not an install that came back
    # as the twin: folding would help nobody, and could only help an intruder.
    _, t_h, _ = _split_install()
    _push("U", updated_at="2026-10-02 19:00:00")           # the family app launched the next day
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == []


def test_an_expired_birth_token_cannot_fold_at_mint(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET expires_at = '2026-01-01 00:00:00' WHERE token = ?",
                     (hash_token(t_h),))
    r = _mint(client, "U", t_h)                        # an expired token still proves H…
    assert r.status_code == 201 and r.json()["device_id"] == "H"
    assert _rows_of("H")                                # …but never folds


def test_with_minting_enforced_a_later_twin_token_still_cannot_fold(client, monkeypatch):
    _split_install()
    later = _token("H", "2026-10-03 09:00:00")
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    assert _register(client, later).json() == {"ok": True}


def test_the_locked_recheck_has_the_last_word(client, monkeypatch):
    _, t_h, _ = _split_install()
    real = twins.twin_canonical
    calls = {"n": 0}

    def flips(conn, device_id, *, credential):
        calls["n"] += 1
        return real(conn, device_id, credential=credential) if calls["n"] == 1 else None

    monkeypatch.setattr(twins, "twin_canonical", flips)
    assert _register(client, t_h).json() == {"ok": True}
    calls["n"] = 0
    r = _mint(client, "U", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "H"    # not the family
    assert _rows_of("H")


def test_a_timezone_aware_timestamp_is_normalised(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = '2026-10-01T08:00:00+00:00' WHERE device_id = 'U'")
    r = _register(client, t_h)
    assert r.status_code == 200 and r.json()["device_id"] == "U"


def test_any_failure_in_the_check_falls_back_to_the_old_behaviour(client, monkeypatch):
    _, t_h, _ = _split_install()

    def boom(*a, **k):
        raise TypeError("anything at all")

    monkeypatch.setattr(twins, "family_of", boom)
    assert _register(client, t_h).json() == {"ok": True}
    r = _mint(client, "U", t_h)
    assert r.status_code == 201 and r.json()["device_id"] == "H"


# ── what a fold moves, and what it leaves ─────────────────────────────────

def test_only_birth_window_tokens_move(client):
    _, t_h, _ = _split_install()
    later = _token("H", "2026-10-02 10:00:00")
    _register(client, t_h)
    assert store.validate_token(t_h)["device_id"] == "U"
    assert store.validate_token(later)["device_id"] == "H"    # opens nothing now
    assert _children(client, later) == []


def test_a_colliding_unique_row_stays_with_the_twin(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        conn.execute("INSERT INTO referral_codes (device_id, code) VALUES ('U', 'FAMCODE1'), ('H', 'TWINCODE')")
    _register(client, t_h)
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM referral_codes WHERE code = 'TWINCODE'").fetchone()[0] == "H"
        assert conn.execute("SELECT device_id FROM referral_codes WHERE code = 'FAMCODE1'").fetchone()[0] == "U"


def test_google_links_and_backups_never_move(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        conn.execute("INSERT INTO parent_identities (google_id, email) VALUES ('g-1', 'x@example.invalid')")
        conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES ('H', 'g-1')")
        conn.execute("INSERT INTO user_backups (device_id, salt, nonce, payload) VALUES ('H', 's', 'n', 'p')")
    _register(client, t_h)
    with _db() as conn:
        assert conn.execute("SELECT device_id FROM identity_links").fetchone()[0] == "H"
        assert conn.execute("SELECT device_id FROM user_backups").fetchone()[0] == "H"


def _snapshot() -> dict:
    with _db() as conn:
        return {t: sorted(tuple(r) for r in conn.execute(f'SELECT rowid, * FROM "{t}"'))
                for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                         "AND name NOT LIKE 'sqlite_%' AND name NOT IN "
                                         "('device_aliases', 'device_fold_log')").fetchall()}


def test_every_change_is_logged_and_revert_fold_puts_it_back(client):
    _, t_h, _ = _split_install()
    sid = store.create_session(device_id="H")
    store.add_message(sid, "user", "asked as the twin")
    with _db() as conn:
        conn.execute("INSERT INTO referral_codes (device_id, code) VALUES ('U', 'FAMCODE1'), ('H', 'TWINCODE')")
    before = _snapshot()
    _register(client, t_h)
    with _db() as conn:
        log = [dict(r) for r in conn.execute("SELECT * FROM device_fold_log")]
        for e in log:
            if e["action"] == "moved":          # each logged row really is under U now
                now = conn.execute(f'SELECT "{e["column_name"]}" FROM "{e["table_name"]}" WHERE rowid = ?',
                                   (e["row_id"],)).fetchone()[0]
                assert now == "U", e
        assert twins.revert_fold(conn, "H") == len(log)
    after = _snapshot()
    # The family's push row also took this request's census (a live write,
    # not part of the fold); everything else is exactly as before.
    before.pop("push_tokens")
    after.pop("push_tokens")
    assert after == before
    with _db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM push_tokens WHERE device_id = 'H'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM device_aliases").fetchone()[0] == 0


# ── the fold itself, on production's schema ───────────────────────────────

FIXTURE = Path(__file__).parent / "fixtures" / "prod_device_tables_2026-10-04.sql"


def _fill(conn: sqlite3.Connection, table: str, values: dict) -> None:
    """Insert a row with `values`, defaulting every other NOT NULL column."""
    cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    row = dict(values)
    for _cid, name, ctype, notnull, default, pk in cols:
        rowid_alias = pk and "INT" in (ctype or "").upper()
        if name in row or rowid_alias or default is not None or not (notnull or pk):
            continue
        row[name] = 1 if "INT" in (ctype or "").upper() else f"{table}-{name}-{len(values)}"
    names = ", ".join(f'"{k}"' for k in row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', list(row.values()))


def _prod_schema(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "prod_schema.db")
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))
    return conn


def test_fold_on_production_schema_moves_logs_and_keeps(tmp_path):
    conn = _prod_schema(tmp_path)
    assert len(twins.device_columns(conn, include_excluded=True)) == 25
    for table, col in twins.device_columns(conn, include_excluded=True):
        _fill(conn, table, {col: "H"})
    conn.execute("UPDATE api_tokens SET created_at = '2026-10-01 08:00:01' WHERE device_id = 'H'")
    _fill(conn, "api_tokens", {"device_id": "U", "token": "u-birth", "session_id": "s-u",
                               "created_at": BIRTH})
    _fill(conn, "api_tokens", {"device_id": "H", "token": "h-later", "session_id": "s-h",
                               "created_at": "2026-10-03 09:00:00"})
    # Rows the family already holds once.
    _fill(conn, "push_tokens", {"device_id": "U", "token": FCM})
    _fill(conn, "referral_codes", {"device_id": "U", "code": "FAMILY"})
    _fill(conn, "referrals", {"referred_device": "U", "referrer_device": "R"})
    conn.commit()

    _, counts = twins._locked(conn, lambda: "U", lambda u: twins._fold_rows(conn, "H", u))

    left = {}
    for t, c in twins.device_columns(conn, include_excluded=True):
        if t != "device_aliases":
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" = ?', ("H",)).fetchone()[0]
            if n:
                left[f"{t}.{c}"] = n
    assert left == {
        "api_tokens.device_id": 1,            # the token minted later
        "identity_links.device_id": 1,        # never moves
        "user_backups.device_id": 1,          # never moves
        "referral_codes.device_id": 1,        # the family has its own
        "referrals.referred_device": 1,       # the family was referred already
    }
    assert counts["push_tokens.device_id:deleted"] == 1
    logged = conn.execute("SELECT COUNT(*) FROM device_fold_log WHERE action = 'moved'").fetchone()[0]
    assert logged == sum(v for k, v in counts.items() if ":" not in k)
    snap = conn.execute("SELECT row_json FROM device_fold_log WHERE action = 'deleted'").fetchone()[0]
    assert json.loads(snap)["device_id"] == "H"
    assert conn.execute("SELECT canonical_device FROM device_aliases WHERE device_id = 'H'").fetchone()[0] == "U"


def test_fold_is_all_or_nothing(tmp_path, monkeypatch):
    conn = _prod_schema(tmp_path)
    for table, col in twins.device_columns(conn):
        _fill(conn, table, {col: "H"})
    conn.commit()
    real = twins.device_columns
    monkeypatch.setattr(twins, "device_columns",
                        lambda c, **k: real(c, **k) + [("no_such_table", "device_id")])
    with pytest.raises(sqlite3.OperationalError):
        twins._locked(conn, lambda: "U", lambda u: twins._fold_rows(conn, "H", u, all_tokens=True))
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = 'H'").fetchone()[0] == 1


def test_a_device_is_never_folded_into_itself():
    with pytest.raises(ValueError):
        twins._fold_rows(sqlite3.connect(":memory:"), "U", "U")


# ── never across families ─────────────────────────────────────────────────

def test_a_different_fcm_token_is_another_install(client):
    _born("U")
    _child("U")
    _push("U", fcm="fcm-A")
    t_h = _born("H", "2026-10-01 08:00:01")
    _push("H", fcm="fcm-B")
    assert _register(client, t_h, fcm="fcm-B").json() == {"ok": True}
    assert _children(client, t_h) == []


def test_a_stolen_fcm_token_cannot_point_a_new_device_at_a_family(client):
    _born("U")
    _child("U")
    _push("U")
    t_x = _born("X", "2026-10-04 12:00:00")
    assert _register(client, t_x).json() == {"ok": True}
    assert _children(client, t_x) == []


def test_a_token_minted_later_for_the_twin_never_triggers(client):
    _split_install()
    late = _mint(client, "H").json()["token"]           # enforcement off: just the id
    assert _register(client, late).json() == {"ok": True}
    assert _rows_of("H")


def test_devices_born_apart_are_not_twins(client):
    _born("U")
    _child("U")
    _push("U")
    t_h = _born("H", "2026-10-03 08:00:00")
    _push("H")
    assert _register(client, t_h).json() == {"ok": True}


def test_a_twin_with_its_own_child_is_left_alone(client):
    _, t_h, _ = _split_install()
    _child("H", "re-onboarded")
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == ["re-onboarded"]


def test_two_families_on_one_token_is_ambiguous(client):
    _, t_h, _ = _split_install()
    _born("V", "2026-10-01 08:00:02")
    _child("V")
    _push("V")
    assert _register(client, t_h).json() == {"ok": True}


def test_a_proof_for_another_device_mints_for_the_proven_device(client):
    # Audit H5, as decided in the PR #29 review: the proof decides — the caller
    # gets its own device; the claimed one is untouched.
    t_a = _born("A")
    _child("A")
    _push("A", fcm="fcm-A")
    _born("B", "2026-10-01 08:00:01")
    _push("B", fcm="fcm-B")
    r = _mint(client, "B", t_a)
    assert r.status_code == 201 and r.json()["device_id"] == "A"
    assert _rows_of("B")


def test_another_devices_credential_cannot_fold_a_twin(client):
    _split_install()
    t_x = _born("X", "2026-10-01 08:00:02")
    with _db() as conn:
        assert twins.twin_canonical(conn, "H", credential=t_x) is None


# ── an id the API refuses (stored before SessionCreate validated it) ──────

SPACED = "abcd efgh ijkl mnop"
GARBAGE = "��k�9 �-��"
NEW_ID = "0b5c2f6e-1d2a-4c3b-9f8e-7a6b5c4d3e2f"


def test_a_family_on_a_refused_id_moves_to_the_apps_new_id(client):
    t_s = _born(SPACED)
    _child(SPACED, "Yusuf")
    _push(SPACED)
    r = _mint(client, NEW_ID, t_s)
    assert r.status_code == 201 and r.json()["device_id"] == NEW_ID
    assert _children(client, r.json()["token"]) == ["Yusuf"]
    assert store.validate_token(t_s)["device_id"] == NEW_ID
    assert _rows_of(SPACED) == {}
    with _db() as conn:
        assert conn.execute("SELECT canonical_device FROM device_aliases WHERE device_id = ?",
                            (SPACED,)).fetchone()[0] == NEW_ID
        assert conn.execute("SELECT COUNT(*) FROM device_fold_log WHERE from_device = ?",
                            (SPACED,)).fetchone()[0] >= 3


def test_a_refused_id_cannot_move_onto_a_device_that_exists(client):
    t_s = _born(SPACED)
    _child(SPACED, "Yusuf")
    _born("someone-else", "2026-09-01 08:00:00")
    _child("someone-else", "Other")
    r = _mint(client, "someone-else", t_s)
    assert r.status_code == 201 and r.json()["device_id"] == SPACED     # its own, as proven
    assert _children(client, r.json()["token"]) == ["Yusuf"]
    with _db() as conn:
        names = [n for (n,) in conn.execute("SELECT name FROM child_profiles WHERE device_id = 'someone-else'")]
    assert names == ["Other"]


def test_a_valid_proof_never_moves_onto_a_brand_new_id(client):
    t_a = _born("valid-device-A")
    r = _mint(client, "brand-new-id", t_a)
    assert r.status_code == 201 and r.json()["device_id"] == "valid-device-A"
    assert _rows_of("brand-new-id") == {}


def test_a_refused_device_id_is_logged_but_never_repeated(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        r = _mint(client, GARBAGE)
        r2 = _mint(client, SPACED)
        r3 = _mint(client, "abc\n")
    assert r.status_code == r2.status_code == r3.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "device_id"
    lines = [rec.getMessage() for rec in caplog.records if "session mint rejected device_id" in rec.getMessage()]
    assert len(lines) == 3
    assert "len=10" in lines[0] and "fffd=6" in lines[0] and "space=1" in lines[0]
    assert "len=19" in lines[1] and "space=3" in lines[1]
    assert GARBAGE not in caplog.text and SPACED not in caplog.text


def test_the_id_rule_is_a_full_match():
    assert twins.is_valid_device_id("0b5c2f6e-1d2a-4c3b-9f8e-7a6b5c4d3e2f")
    assert not twins.is_valid_device_id("abc\n")       # Python's `$` alone would accept it
    assert not twins.is_valid_device_id(SPACED)
    assert not twins.is_valid_device_id("a" * 129)


# ── account deletion (review item 9) ──────────────────────────────────────

def test_account_deletion_reaches_the_twin_and_its_bookkeeping(client):
    """Contract for the account-deletion path (PR #26, still open): deleting the
    family must also delete what a fold left under the twin id and the twin
    bookkeeping. Until that path exists this exercises the hook it must call
    (related_devices + forget_devices); once `privacy.erase_account` exists, it
    exercises the path itself — and fails if the path skips the twin."""
    _, t_h, _ = _split_install()
    later = _token("H", "2026-10-03 09:00:00")              # stays with the twin
    with _db() as conn:
        conn.execute("INSERT INTO referral_codes (device_id, code) VALUES ('U', 'FAMCODE1'), ('H', 'TWINCODE')")
    _register(client, t_h)
    from app.routers import privacy
    erase = getattr(privacy, "erase_account", None)
    if erase is not None:
        erase("U")
    else:
        with _db() as conn:
            devices = twins.related_devices(conn, ["U"])
            assert devices == {"U", "H"}
            twins.forget_devices(conn, devices)
            for table, col in twins.device_columns(conn, include_excluded=True):
                if table != "device_aliases":
                    conn.execute(f'DELETE FROM "{table}" WHERE "{col}" IN (?, ?)', ("U", "H"))
    with _db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM device_aliases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM device_fold_log").fetchone()[0] == 0
    assert _rows_of("U") == {} and _rows_of("H") == {}
    assert store.validate_token(later) is None
