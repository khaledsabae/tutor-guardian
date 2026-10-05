"""Erased-device tombstones (schema v35) — an account deleted in the app stays
deleted (review of PR #36).

Android's Auto Backup can restore an erased install's device id on a reinstall,
and the app then minted a fresh session for it: the deleted account "came
back" on the phone. Now an account erase keeps a one-way hash of every device
id it removed, and the session mint answers 410 device_erased — to builds
that send X-App-Build ≥ ERASED_DEVICE_410_MIN_BUILD; every other mint is
served exactly as before.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import SCHEMA_VERSION, db_path, get_conn
from app.routers import privacy as pv
from app.services import erased_devices as ed
from tests.device_proof_support import prove

GATE = "120"


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_pepper(monkeypatch):
    monkeypatch.delenv(ed.PEPPER_ENV, raising=False)
    monkeypatch.delenv(ed.MIN_BUILD_ENV, raising=False)


def _mint(client, device: str, build: str | None = None, token: str | None = None):
    headers = {}
    if build is not None:
        headers[ed.BUILD_HEADER] = build
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/api/chat/sessions", json={"device_id": device}, headers=headers)


def _erase(client, device: str) -> str:
    """A device with a child, proven, deleted through the API. Returns the
    token the deletion was made with (gone with the data)."""
    r = _mint(client, device)
    assert r.status_code == 201
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/children", json={"name": "سالم", "age_group": "7-9"},
                       headers=h).status_code == 201
    prove(client, h, push_token=f"fcm-{device}")
    r = client.delete("/api/privacy/account?confirm=true", headers=h)
    assert r.status_code == 200, r.text
    return token


def _tombstones() -> list[tuple]:
    conn = sqlite3.connect(db_path())
    try:
        return conn.execute("SELECT device_hash, erased_at FROM erased_devices").fetchall()
    finally:
        conn.close()


def test_the_table_is_v35_and_keyed_by_hash():
    assert SCHEMA_VERSION >= 35
    conn = get_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(erased_devices)")]
    pk = [r[1] for r in conn.execute("PRAGMA table_info(erased_devices)") if r[5]]
    conn.close()
    assert cols == ["device_hash", "erased_at"] and pk == ["device_hash"]


# ── What an erase keeps ───────────────────────────────────────────────────


def test_an_erase_tombstones_every_device_it_removes_and_never_the_id(client):
    """The caller, every phone confirmed-linked to its Google account, and a
    twin id folded into one of them (device_aliases) — one account."""
    r = _mint(client, "dev-main")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    prove(client, h, push_token="fcm-main")
    conn = sqlite3.connect(db_path())
    for dev in ("dev-main", "dev-old-phone"):
        conn.execute("INSERT INTO identity_links (device_id, google_id, confirmed) "
                     "VALUES (?, 'g-parent', 1)", (dev,))
    conn.execute("INSERT INTO device_aliases (device_id, canonical_device) "
                 "VALUES ('dev-twin', 'dev-main')")
    conn.commit()
    conn.close()
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 200

    stored = {row[0] for row in _tombstones()}
    assert stored == {ed.device_hash(d) for d in ("dev-main", "dev-old-phone", "dev-twin")}
    for device in ("dev-main", "dev-old-phone", "dev-twin"):
        assert ed.is_erased(device)
    assert not ed.is_erased("dev-bystander")
    # No id anywhere in the table, in any column; only 64-hex digests.
    for digest, erased_at in _tombstones():
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        for device in ("dev-main", "dev-old-phone", "dev-twin"):
            assert device not in digest and device not in erased_at


def test_the_hash_is_one_way_and_peppered_when_configured(monkeypatch):
    plain = ed.device_hash("550e8400-e29b-41d4-a716-446655440000")
    assert plain != hashlib.sha256(b"550e8400-e29b-41d4-a716-446655440000").hexdigest()
    monkeypatch.setenv(ed.PEPPER_ENV, "pepper-only-the-server-knows")
    peppered = ed.device_hash("550e8400-e29b-41d4-a716-446655440000")
    assert peppered != plain and re.fullmatch(r"[0-9a-f]{64}", peppered)
    # A tombstone written before the pepper was set still counts after it is.
    monkeypatch.delenv(ed.PEPPER_ENV)
    conn = get_conn()
    ed.record(conn, ["dev-before-pepper"])
    conn.commit()
    conn.close()
    monkeypatch.setenv(ed.PEPPER_ENV, "pepper-only-the-server-knows")
    assert ed.is_erased("dev-before-pepper")
    conn = get_conn()
    ed.record(conn, ["dev-after-pepper"])
    conn.commit()
    conn.close()
    assert ed.is_erased("dev-after-pepper")
    assert ed.device_hash("dev-after-pepper") in {row[0] for row in _tombstones()}


def test_a_failed_erase_leaves_no_tombstone_and_every_token(client, monkeypatch):
    """One transaction: the tokens, the data and the tombstones go together."""
    token = _mint(client, "dev-atomic").json()["token"]

    def explode(conn, devices):
        raise RuntimeError("disk full")

    from app.services import device_twins
    monkeypatch.setattr(device_twins, "forget_devices", explode)
    with pytest.raises(RuntimeError):
        pv.erase_account("dev-atomic")
    assert _tombstones() == [] and not ed.is_erased("dev-atomic")
    assert client.get("/api/children", headers={"Authorization": f"Bearer {token}"}
                      ).status_code == 200


def test_deleting_memory_alone_is_not_an_account_erase(client):
    r = _mint(client, "dev-memory-only")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    prove(client, h, push_token="fcm-memory-only")
    assert client.delete("/api/privacy/memory", headers=h).status_code == 200
    assert _tombstones() == []


# ── The mint ──────────────────────────────────────────────────────────────


def test_a_build_that_understands_it_gets_410(client, monkeypatch):
    _erase(client, "dev-gone")
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    r = _mint(client, "dev-gone", build="120")
    assert r.status_code == 410
    assert r.json() == {"detail": {"code": "device_erased", "message": ed.MESSAGE,
                                   "message_en": ed.MESSAGE_EN}}
    assert _mint(client, "dev-gone", build="999").status_code == 410
    # Nothing was minted for it.
    conn = sqlite3.connect(db_path())
    assert conn.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = 'dev-gone'"
                        ).fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize("gate,build", [
    (None, "200"),     # the server has not switched it on
    (GATE, None),      # a build that sends no header (every build on Play today)
    (GATE, "119"),     # a build below the floor
    (GATE, "12a"),     # not a build number
])
def test_every_other_mint_is_served_as_before(client, monkeypatch, gate, build):
    _erase(client, "dev-old-build")
    if gate:
        monkeypatch.setenv(ed.MIN_BUILD_ENV, gate)
    r = _mint(client, "dev-old-build", build=build)
    assert r.status_code == 201 and r.json()["device_id"] == "dev-old-build"
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/children", headers=h).json()["children"] == []


def test_a_new_device_id_is_never_refused(client, monkeypatch):
    _erase(client, "dev-erased")
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    assert _mint(client, "550e8400-e29b-41d4-a716-446655440000", build="120").status_code == 201


def test_a_token_from_before_the_deletion_is_no_proof(client, monkeypatch):
    """The restored backup holds the old token too — gone with the data."""
    old_token = _erase(client, "dev-restored")
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    assert _mint(client, "dev-restored", build="120", token=old_token).status_code == 410


def test_a_live_install_reborn_under_the_id_is_served(client, monkeypatch):
    """An older build reinstalled meanwhile and minted a new account under the
    old id: its token, issued after the deletion, proves a live install."""
    _erase(client, "dev-reborn")
    reborn = _mint(client, "dev-reborn").json()["token"]           # no header: an old build
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    r = _mint(client, "dev-reborn", build="120", token=reborn)
    assert r.status_code == 201 and r.json()["device_id"] == "dev-reborn"


def test_app_config_says_which_builds_get_it(client, monkeypatch):
    assert client.get("/api/app-config").json()["erased_device_410_min_build"] is None
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    assert client.get("/api/app-config").json()["erased_device_410_min_build"] == 120
    monkeypatch.setenv(ed.MIN_BUILD_ENV, "0")
    assert client.get("/api/app-config").json()["erased_device_410_min_build"] is None


# ── Settling a deletion whose answer was lost ─────────────────────────────


def test_a_resent_delete_answers_401_and_the_mint_settles_it(client, monkeypatch):
    r = _mint(client, "dev-settle")
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    prove(client, h, push_token="fcm-settle")
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 200
    # The answer was "lost": the same DELETE again — the token went with the data.
    assert client.delete("/api/privacy/account?confirm=true", headers=h).status_code == 401
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    assert _mint(client, "dev-settle", build="120", token=token).status_code == 410
    # …while an account that was NOT deleted answers 201 to the same question.
    alive = _mint(client, "dev-alive").json()["token"]
    r = _mint(client, "dev-alive", build="120", token=alive)
    assert r.status_code == 201 and r.json()["device_id"] == "dev-alive"


# ── Twins ─────────────────────────────────────────────────────────────────


def test_tombstones_survive_the_twin_repair(client, monkeypatch, tmp_path, capsys):
    """ops/tools/repair_device_twins.py folds a twin into its family; the
    account is then deleted; the repair runs again. Both ids stay
    tombstoned, the repair has nothing to fold, and neither id is minted."""
    from app.services import device_twins as twins
    from tests.test_repair_device_twins import _born, _child, _load, _push

    monkeypatch.delenv("TWIN_FOLD_BORN_BEFORE", raising=False)
    _born("U1", "2026-09-30 10:00:00")
    _child("U1", "2026-09-30 10:01:00")
    _born("H1", "2026-09-30 10:00:01")
    _born("H1", "2026-10-02 18:00:00")
    _push("U1", "fcm-1", "2026-09-30 10:00:05")
    _push("H1", "fcm-1", "2026-10-03 19:00:00")
    repair = _load()
    assert repair.main(["--apply", "--db", str(db_path()), "--backup-dir", str(tmp_path)]) == 0
    assert twins.canonical_of("H1") == "U1"

    pv.erase_account("U1")
    assert ed.is_erased("U1") and ed.is_erased("H1")
    before = _tombstones()

    capsys.readouterr()
    assert repair.main(["--apply", "--db", str(db_path()), "--backup-dir", str(tmp_path)]) == 0
    assert "folded 0 of 0" in capsys.readouterr().out
    assert twins.canonical_of("H1") is None              # the alias went with the account
    assert _tombstones() == before
    monkeypatch.setenv(ed.MIN_BUILD_ENV, GATE)
    assert _mint(client, "H1", build="120").status_code == 410
    assert _mint(client, "U1", build="120").status_code == 410
