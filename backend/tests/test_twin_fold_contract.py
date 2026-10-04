"""PR #26 × PR #29 (final review, item 10) — whichever lands second keeps it.

#29 folds a childless twin device into the family's device when the twin
registers the install's one FCM token. Two things must hold together:
  * a fold is not an unconfirmed push-token change: the family's proof stays
    good, nothing pauses, and no "opened on a new device" notice is owed;
  * account deletion covers the proof rows and `device_aliases`.

Skipped until both are on the same branch (app.services.device_twins exists).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

twins = pytest.importorskip("app.services.device_twins")

from app.db.init_db import get_conn  # noqa: E402
from app.services import conversation_store as store  # noqa: E402
from tests.device_proof_support import prove  # noqa: E402

FCM = "fcm-token-of-the-install"


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _born(device: str, at: str) -> str:
    _, token = store.create_session_with_token(device_id=device)
    conn = get_conn()
    conn.execute("UPDATE api_tokens SET created_at = ? WHERE device_id = ?", (at, device))
    conn.commit()
    conn.close()
    return token


def test_a_twin_fold_is_not_a_takeover_and_deletion_covers_it(client):
    t_u = _born("U-fold", "2026-10-01 08:00:00")
    t_h = _born("H-fold", "2026-10-01 08:00:01")
    hu = {"Authorization": f"Bearer {t_u}"}
    cid = client.post("/api/children", json={"name": "Maryam", "age_group": "7-9"},
                      headers=hu).json()["id"]
    prove(client, hu, push_token=FCM)
    assert client.get(f"/api/children/{cid}/memory", headers=hu).status_code == 200

    # The app comes back as the twin, with the install's one token: #29 folds it.
    r = client.post("/api/push/register", headers={"Authorization": f"Bearer {t_h}"},
                    json={"token": FCM, "platform": "android", "build_number": 120})
    assert r.status_code == 200 and r.json().get("device_id") == "U-fold", r.text

    status = client.get("/api/device-proof", headers=hu).json()
    assert status["proven"] is True
    assert status["cooldown_until"] is None and status["deletion_paused_until"] is None
    conn = get_conn()
    owed = conn.execute("SELECT COUNT(*) FROM device_alerts WHERE old_token IS NOT NULL").fetchone()[0]
    conn.close()
    assert owed == 0
    assert client.get(f"/api/children/{cid}/memory", headers=hu).status_code == 200

    r = client.delete("/api/privacy/account?confirm=true", headers=hu)
    assert r.status_code == 200, r.text
    conn = get_conn()
    left = {
        "device_aliases": conn.execute(
            "SELECT COUNT(*) FROM device_aliases WHERE alias IN ('U-fold', 'H-fold') "
            "OR canonical IN ('U-fold', 'H-fold')").fetchone()[0],
        "device_proof_sessions": conn.execute(
            "SELECT COUNT(*) FROM device_proof_sessions WHERE device_id IN ('U-fold', 'H-fold')"
        ).fetchone()[0],
        "device_proofs": conn.execute(
            "SELECT COUNT(*) FROM device_proofs WHERE device_id IN ('U-fold', 'H-fold')"
        ).fetchone()[0],
    }
    conn.close()
    assert left == {"device_aliases": 0, "device_proof_sessions": 0, "device_proofs": 0}
