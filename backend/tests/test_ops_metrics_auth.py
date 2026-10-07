"""Route-level authentication for private operational metrics (audit M15)."""
import secrets
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.routers import stats


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("configured,supplied", [
    ("test-ops-token", None),
    ("test-ops-token", "wrong-test-token"),
    (None, None),
    (None, "test-ops-token"),
    ("", None),
    ("", "test-ops-token"),
    (" ", None),
    (" ", "test-ops-token"),
    (" ", " "),
    ("\t", None),
    ("\t", "test-ops-token"),
    (" \n ", None),
    (" \n ", "test-ops-token"),
])
def test_denied_before_any_metrics_access(client, monkeypatch, configured, supplied):
    if configured is None:
        monkeypatch.delenv("OPS_METRICS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("OPS_METRICS_TOKEN", configured)
    telemetry = Mock(side_effect=AssertionError("unauthorized telemetry read"))
    database = Mock(side_effect=AssertionError("unauthorized operational DB read"))
    monkeypatch.setattr(stats.sqlite3, "connect", telemetry)
    monkeypatch.setattr(stats, "get_conn", database)
    headers = {} if supplied is None else {"X-Ops-Token": supplied}

    response = client.get("/api/stats/ops-llm", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}
    telemetry.assert_not_called()
    database.assert_not_called()


def test_configured_exact_token_uses_constant_time_comparison_and_reads_metrics(
    client, monkeypatch, tmp_path,
):
    from app.services import ai_gateway

    token = "test-ops-token"
    monkeypatch.setenv("OPS_METRICS_TOKEN", token)
    path = tmp_path / "telemetry.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_calls (ts TEXT, ok INTEGER, latency_ms INTEGER, "
                     "provider TEXT, prompt_tokens INTEGER, completion_tokens INTEGER)")
        conn.execute("INSERT INTO llm_calls VALUES (datetime('now'), 1, 42, 'answer_cache', 0, 0)")
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", path)
    digest = Mock(wraps=secrets.compare_digest)
    monkeypatch.setattr(stats.secrets, "compare_digest", digest)

    response = client.get("/api/stats/ops-llm?days=3", headers={"X-Ops-Token": token})

    assert response.status_code == 200, response.text
    digest.assert_called_once_with(token, token)
    data = response.json()
    assert data["window_days"] == 3
    assert data["calls"] == 1
    assert data["p95_latency_ms"] == 42
    assert data["success_rate"] == 1.0
    assert data["cache_hit_rate"] == 1.0
    assert "telemetry_error" not in data
