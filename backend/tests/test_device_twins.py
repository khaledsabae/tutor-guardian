"""Device twins (2026-10-04): an install that 1.0.58-1.0.67 split into two
device ids is put back together — and nothing ever crosses families.

The shape every test builds is the one production has: the family's device U
(the visible engine, where the parent onboarded the child) and its childless
twin H (the headless engine), born within seconds, both registered with the
install's one FCM token. See app/services/device_twins.py.
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path, hash_token, init_db
from app.services import conversation_store as store
from app.services import device_twins as twins
from app.services import fiqh_guard

FCM = "fcm-token-of-the-install"
BIRTH = "2026-10-01 08:00:00"


# ── fixtures ──────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _born(device: str, at: str = BIRTH) -> str:
    """A device's first session; its token issued at `at`. Returns the token."""
    _, token = store.create_session_with_token(device_id=device)
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE device_id = ?", (at, device))
    return token


def _later_token(device: str, at: str) -> str:
    """Another token for an existing device, issued at `at`."""
    _, token = store.create_session_with_token(device_id=device)
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE token = ?", (at, hash_token(token)))
    return token


def _child(device: str, name: str = "Child") -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '7-9')",
            (device, name),
        )
        return cur.lastrowid


def _push(device: str, fcm: str = FCM, updated_at: str = BIRTH, build: int | None = 111):
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
        for table, col in twins.device_columns(conn):
            n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = ?', (device,)).fetchone()[0]
            if n:
                out[f"{table}.{col}"] = n
    return out


def _split_install(twin_born: str = "2026-10-01 08:00:01"):
    """U onboarded a child; H is the childless twin with the same FCM token."""
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
    from app.config.guardrails_loader import load_guardrails_config
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(c: TestClient, token: str, fcm: str = FCM):
    return c.post("/api/push/register", headers=_bearer(token),
                  json={"token": fcm, "platform": "android", "build_number": 111})


def _children(c: TestClient, token: str) -> list[str]:
    r = c.get("/api/children", headers=_bearer(token))
    assert r.status_code == 200, r.text
    body = r.json()
    items = body["children"] if isinstance(body, dict) else body
    return [ch["name"] for ch in items]


# ── recovery: the app came back as the twin ───────────────────────────────

def test_push_registration_folds_the_twin_into_the_family(client):
    _, t_h, _ = _split_install()
    assert _children(client, t_h) == []                 # what the parent saw

    r = _register(client, t_h)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "device_id": "U", "identity_recovered": True}

    # The token the app already holds now opens the family's data.
    assert _children(client, t_h) == ["Maryam"]
    assert store.validate_token(t_h)["device_id"] == "U"
    # Nothing of the twin is left behind (no orphan rows a delete would miss).
    assert _rows_of("H") == {}
    with _db() as conn:
        row = conn.execute("SELECT token, build_number FROM push_tokens WHERE device_id = 'U'").fetchone()
    assert (row["token"], row["build_number"]) == (FCM, 111)


def test_the_twins_conversations_follow_it(client):
    _, t_h, _ = _split_install()
    sid = store.create_session(device_id="H")
    store.add_message(sid, "user", "a question asked while the app was the twin")

    _register(client, t_h)

    r = client.get(f"/api/chat/sessions/{sid}", headers=_bearer(t_h))
    assert r.status_code == 200
    assert store.session_owner(sid) == (True, "U")


def test_a_second_registration_finds_nothing_left_to_fold(client):
    _, t_h, _ = _split_install()
    assert _register(client, t_h).json()["identity_recovered"] is True
    # Both engines of an old build register; the second is a plain registration.
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == ["Maryam"]


def test_minting_with_the_twins_proof_mints_for_the_family(client):
    _, t_h, _ = _split_install()
    r = client.post("/api/chat/sessions", headers=_bearer(t_h), json={"device_id": "H"})
    assert r.status_code == 201
    assert r.json()["device_id"] == "U"
    assert _children(client, r.json()["token"]) == ["Maryam"]
    assert _rows_of("H") == {}


def test_disk_says_family_but_proof_is_the_twins(client):
    # The two engines' writes interleaved: tg_device_id = U, tg_device_proof = T_H.
    _, t_h, _ = _split_install()
    r = client.post("/api/chat/sessions", headers=_bearer(t_h), json={"device_id": "U"})
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _rows_of("H") == {}


def test_disk_says_twin_but_proof_is_the_familys(client):
    # Interleaved the other way: tg_device_id = H, tg_device_proof = T_U. This
    # used to answer 403, the app dropped its proof and minted H again —
    # childless. Now the proven family device wins and the twin is folded.
    t_u, _, _ = _split_install()
    r = client.post("/api/chat/sessions", headers=_bearer(t_u), json={"device_id": "H"})
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _rows_of("H") == {}


def test_an_ordinary_mint_names_its_own_device(client):
    r = client.post("/api/chat/sessions", json={"device_id": "fresh-install"})
    assert r.status_code == 201 and r.json()["device_id"] == "fresh-install"
    token = r.json()["token"]
    r = client.post("/api/chat/sessions", headers=_bearer(token), json={"device_id": "fresh-install"})
    assert r.status_code == 201 and r.json()["device_id"] == "fresh-install"


def test_the_family_device_registering_changes_nothing(client):
    t_u, _, _ = _split_install()
    assert _register(client, t_u).json() == {"ok": True}
    assert _rows_of("H")                                  # left for the repair script


# ── the fold must outlast the app's own memory ────────────────────────────
# The app in the field keeps the twin's id on disk and sends it again at its
# next mint ("new conversation", a 401 renewal). Builds before 106 send no
# proof at all. Neither may be handed a fresh, childless identity.

def test_after_the_fold_an_old_build_minting_the_twins_id_gets_the_family(client):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    r = client.post("/api/chat/sessions", json={"device_id": "H"})   # < 106: no proof
    assert r.status_code == 201 and r.json()["device_id"] == "U"
    assert _children(client, r.json()["token"]) == ["Maryam"]
    assert _rows_of("H") == {}


def test_after_the_fold_a_proof_carrying_remint_gets_the_family(client):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    r = client.post("/api/chat/sessions", headers=_bearer(t_h), json={"device_id": "H"})
    assert r.status_code == 201 and r.json()["device_id"] == "U"


def test_an_alias_does_not_bypass_minting_enforcement(client, monkeypatch):
    _, t_h, _ = _split_install()
    _register(client, t_h)
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    # Knowing the twin's id is knowing a known device's id: proof required.
    assert client.post("/api/chat/sessions", json={"device_id": "H"}).status_code == 401
    r = client.post("/api/chat/sessions", headers=_bearer(t_h), json={"device_id": "H"})
    assert r.status_code == 201 and r.json()["device_id"] == "U"


def test_the_fold_is_remembered_and_older_aliases_follow(client):
    _, t_h, _ = _split_install()
    with _db() as conn:
        twins.ensure_device_aliases_table(conn)
        conn.execute("INSERT INTO device_aliases (alias, canonical) VALUES ('older', 'H')")
    _register(client, t_h)
    with _db() as conn:
        rows = dict(conn.execute("SELECT alias, canonical FROM device_aliases").fetchall())
    assert rows == {"H": "U", "older": "U"}


# ── never across families ─────────────────────────────────────────────────

def test_a_different_fcm_token_is_another_install(client):
    _born("U"); _child("U"); _push("U", fcm="fcm-A")
    t_h = _born("H", "2026-10-01 08:00:01"); _push("H", fcm="fcm-B")
    assert _register(client, t_h, fcm="fcm-B").json() == {"ok": True}
    assert _children(client, t_h) == []


def test_a_stolen_fcm_token_cannot_point_a_new_device_at_a_family(client):
    _born("U"); _child("U"); _push("U")
    # An attacker who somehow learned the family's FCM token registers it from
    # a device of their own, today. It was not born with the family's device.
    t_x = _born("X", "2026-10-04 12:00:00")
    assert _register(client, t_x).json() == {"ok": True}
    assert _children(client, t_x) == []
    assert store.validate_token(t_x)["device_id"] == "X"


def test_a_token_minted_later_for_the_twin_never_qualifies(client):
    # While SESSION_MINT_ENFORCE is off, knowing a device id is enough to mint
    # a NEW token for it. Such a token must not open the family's data.
    _split_install()
    late = client.post("/api/chat/sessions", json={"device_id": "H"}).json()["token"]
    assert _register(client, late).json() == {"ok": True}
    assert _children(client, late) == []
    assert _rows_of("H")


def test_with_minting_enforced_any_twin_token_descends_from_a_proof(client, monkeypatch):
    _, t_h, _ = _split_install()
    later = _later_token("H", "2026-10-03 09:00:00")  # e.g. a renewal, proof-checked
    monkeypatch.setenv("SESSION_MINT_ENFORCE", "true")
    assert _register(client, later).json()["device_id"] == "U"


def test_devices_born_apart_are_not_twins(client):
    # Same FCM token, but born two days apart: an identity reset on one phone,
    # not the startup race. Left to the operator, never folded at runtime.
    _born("U"); _child("U"); _push("U")
    t_h = _born("H", "2026-10-03 08:00:00"); _push("H")
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == []


def test_a_twin_with_its_own_child_is_left_alone(client):
    _, t_h, _ = _split_install()
    _child("H", "re-onboarded")
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == ["re-onboarded"]


def test_two_families_on_one_token_is_ambiguous(client):
    _, t_h, _ = _split_install()
    _born("V", "2026-10-01 08:00:02"); _child("V"); _push("V")
    assert _register(client, t_h).json() == {"ok": True}
    assert _children(client, t_h) == []


def test_a_proof_for_an_unrelated_device_is_still_refused(client):
    # The audit-H5 rule is unchanged outside a split install.
    t_a = _born("A"); _child("A"); _push("A", fcm="fcm-A")
    _born("B", "2026-10-01 08:00:01"); _push("B", fcm="fcm-B")
    r = client.post("/api/chat/sessions", headers=_bearer(t_a), json={"device_id": "B"})
    assert r.status_code == 403
    assert _rows_of("B")


def test_another_devices_credential_cannot_fold_a_twin(client):
    _split_install()
    t_x = _born("X", "2026-10-01 08:00:02")
    with _db() as conn:
        assert twins.twin_canonical(conn, "H", credential=t_x) is None


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
        row[name] = 1 if "INT" in (ctype or "").upper() else f"{table}-{name}"
    names = ", ".join(f'"{k}"' for k in row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', list(row.values()))


def test_fold_leaves_no_twin_row_in_any_production_table(tmp_path):
    conn = sqlite3.connect(tmp_path / "prod_schema.db")
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))
    columns = twins.device_columns(conn)
    assert len(columns) == 25          # 23 device_id tables + referrals' two columns

    for table, col in columns:
        _fill(conn, table, {col: "H"})
    # The family already holds the rows its unique keys allow once.
    _fill(conn, "push_tokens", {"device_id": "U", "token": FCM, "updated_at": "2026-10-01 08:00:00"})
    _fill(conn, "referral_codes", {"device_id": "U", "code": "FAMILY"})
    _fill(conn, "referrals", {"referred_device": "U", "referrer_device": "R"})
    conn.commit()

    counts = twins.merge_device(conn, "H", "U")

    for table, col in columns:
        left = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = ?', ("H",)).fetchone()[0]
        assert left == 0, f"{table}.{col} still holds the twin"
    assert counts["push_tokens.device_id:dropped"] == 1      # the family's row stays…
    assert conn.execute(
        "SELECT updated_at FROM push_tokens WHERE device_id = 'U'").fetchone()[0] != "2026-10-01 08:00:00"
    assert conn.execute(                                       # …carrying the twin's census
        "SELECT COUNT(*) FROM referral_codes WHERE device_id = 'U'").fetchone()[0] == 1
    assert conn.execute(                                       # the double-counted claim is gone
        "SELECT COUNT(*) FROM referrals WHERE referred_device = 'U'").fetchone()[0] == 1
    assert counts["api_tokens.device_id"] == 1
    assert conn.execute("SELECT canonical FROM device_aliases WHERE alias = 'H'").fetchone()[0] == "U"


def test_fold_is_all_or_nothing(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "prod_schema.db")
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))
    for table, col in twins.device_columns(conn):
        _fill(conn, table, {col: "H"})
    conn.commit()

    real = twins.device_columns

    def broken(c):
        return real(c) + [("no_such_table", "device_id")]

    monkeypatch.setattr(twins, "device_columns", broken)
    with pytest.raises(sqlite3.OperationalError):
        twins.merge_device(conn, "H", "U")
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = 'H'").fetchone()[0] == 1


def test_a_device_is_never_folded_into_itself():
    with pytest.raises(ValueError):
        twins._fold_rows(sqlite3.connect(":memory:"), "U", "U")
