"""
Regression tests for Firebase credential loading in push_sender.

On 2026-07-27 push notifications were dead in production: backend/secrets is
bind-mounted from the host, firebase-adminsdk.json was 0600 root:root, and the
container runs as uid 10001. _load_credentials() called read_text() on a file
that only exists()-ed, so it raised PermissionError out of _ensure_app() rather
than degrading to "push disabled".

The file fallback was also pointing at the wrong directory, so it could never
have covered for the env path.
"""
import json
import os

import pytest

from app.services import push_sender


def test_credentials_path_points_at_backend_secrets():
    """Regression: this resolved to <root>/secrets, not <root>/backend/secrets."""
    p = push_sender._CREDENTIALS_PATH
    assert p.parent.name == "secrets"
    assert p.parent.parent.name == "backend"


def test_unreadable_file_disables_push_instead_of_raising(tmp_path, monkeypatch):
    cred = tmp_path / "firebase-adminsdk.json"
    cred.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
    cred.chmod(0o000)

    if os.access(cred, os.R_OK):
        pytest.skip("running as root — permission bits are not enforced")

    monkeypatch.delenv("FIREBASE_CREDENTIALS", raising=False)
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(cred))

    assert push_sender._load_credentials() is None


def test_malformed_file_disables_push_instead_of_raising(tmp_path, monkeypatch):
    cred = tmp_path / "firebase-adminsdk.json"
    cred.write_text("{not json", encoding="utf-8")

    monkeypatch.delenv("FIREBASE_CREDENTIALS", raising=False)
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(cred))

    assert push_sender._load_credentials() is None


def test_readable_file_loads(tmp_path, monkeypatch):
    cred = tmp_path / "firebase-adminsdk.json"
    cred.write_text(json.dumps({"type": "service_account", "project_id": "x"}), encoding="utf-8")

    monkeypatch.delenv("FIREBASE_CREDENTIALS", raising=False)
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(cred))

    assert push_sender._load_credentials() == {"type": "service_account", "project_id": "x"}


def test_env_json_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS", json.dumps({"type": "from_env"}))
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(tmp_path / "missing.json"))

    assert push_sender._load_credentials() == {"type": "from_env"}


def test_malformed_env_json_disables_push(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS", "{not json")

    assert push_sender._load_credentials() is None
