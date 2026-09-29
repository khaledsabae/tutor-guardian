"""scripts/cron_gen_en_media.sh — the stall guard resets only on real delivery.

Runs the guard's inline Python (the heredoc in the cron script) as-is.
"""
import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# These test repo-level scripts/ (the NotebookLM pipeline). The deploy gate runs
# pytest inside the backend image, which does not ship scripts/ — skip there.
pytestmark = pytest.mark.skipif(
    not (REPO / "scripts" / "cron_gen_en_media.sh").exists(),
    reason="scripts/ not present (backend-only image)",
)



def _stall_snippet() -> str:
    text = (REPO / "scripts" / "cron_gen_en_media.sh").read_text()
    head = '"$PY" - "$TOTAL" "$RATELIMITED" "$STALL_FILE" <<\'PYEOF\'\n'
    start = text.index(head) + len(head)
    return text[start:text.index("\nPYEOF", start)]


def _stall(tmp_path, total: str, ratelimited: bool):
    path = tmp_path / "progress.json"
    r = subprocess.run(
        ["python3", "-", total, "1" if ratelimited else "0", str(path)],
        input=_stall_snippet(), capture_output=True, text=True, timeout=30,
    )
    return r.returncode, json.loads(path.read_text())


def test_stall_counter_resets_only_on_a_real_decrease(tmp_path):
    assert _stall(tmp_path, "100", False) == (0, {"remaining": 100, "stalled": 0})
    assert _stall(tmp_path, "100", False)[1]["stalled"] == 1
    assert _stall(tmp_path, "105", False)[1]["stalled"] == 2   # increase ≠ delivery
    assert _stall(tmp_path, "", False)[1] == {"remaining": 105, "stalled": 3}
    assert _stall(tmp_path, "105", True)[1]["stalled"] == 3    # refusal holds
    rc, st = _stall(tmp_path, "104", False)                     # delivery resets
    assert (rc, st) == (0, {"remaining": 104, "stalled": 0})


def test_stall_guard_fails_on_third_stalled_run(tmp_path):
    _stall(tmp_path, "50", False)
    _stall(tmp_path, "50", False)
    _stall(tmp_path, "50", True)
    assert _stall(tmp_path, "50", False)[0] == 0
    rc, st = _stall(tmp_path, "50", False)
    assert (rc, st["stalled"]) == (1, 3)


def test_stall_guard_reads_legacy_string_state(tmp_path):
    (tmp_path / "progress.json").write_text('{"remaining": "80", "stalled": 2}')
    assert _stall(tmp_path, "80", False) == (1, {"remaining": 80, "stalled": 3})
