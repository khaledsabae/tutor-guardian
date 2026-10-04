"""translate_knowledge_base.py: `--only` translates exactly the named units, and the
Ollama key is read from ~/projects/email-twin/.env inside Python, never from a command line.

Why `--only`: new units arrive in batches (the 2026-10-05 KB-gap refill added 17)
while dozens of other Arabic units have no English twin yet. `--limit N` takes the
first N by file name, `--all` takes every one of them — neither can translate a
batch without sweeping in the rest. No network here: the selection and the key
loading are pure functions.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "ops" / "tools"


def _tool():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("translate_knowledge_base",
                                                  TOOLS / "translate_knowledge_base.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pending(*ids):
    return [(Path(f"/x/{uid}.json"), {"id": uid, "language": "ar"}) for uid in ids]


def test_only_selects_exactly_the_named_pending_units():
    t = _tool()
    chosen, missing = t.select_only(_pending("isl-a", "isl-b", "isl-c"), {"isl-a", "isl-c"})
    assert [d["id"] for _, d in chosen] == ["isl-a", "isl-c"]
    assert missing == []


def test_only_reports_a_name_that_is_not_pending_instead_of_skipping_it():
    t = _tool()
    chosen, missing = t.select_only(_pending("isl-a"), {"isl-a", "isl-gone"})
    assert [d["id"] for _, d in chosen] == ["isl-a"]
    assert missing == ["isl-gone"]


def test_the_key_comes_from_the_env_file_when_the_environment_has_none(monkeypatch, tmp_path):
    t = _tool()
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nOLLAMA_API_KEY='k-test'\n", encoding="utf-8")
    assert t.load_api_key(env) is True
    assert os.environ["OLLAMA_API_KEY"] == "k-test"


def test_an_existing_key_is_kept_and_a_missing_one_is_reported(monkeypatch, tmp_path):
    t = _tool()
    monkeypatch.setenv("OLLAMA_API_KEY", "already")
    env = tmp_path / ".env"
    env.write_text("OLLAMA_API_KEY=other\n", encoding="utf-8")
    assert t.load_api_key(env) is True and os.environ["OLLAMA_API_KEY"] == "already"
    monkeypatch.delenv("OLLAMA_API_KEY")
    assert t.load_api_key(tmp_path / "absent.env") is False
    assert "OLLAMA_API_KEY" not in os.environ
