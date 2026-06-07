"""CI gate — the knowledge base must stay in sync (the drift-detector lesson).

Runs the integrity guard (fast mode) on the real units as a subprocess and
asserts a clean exit. If anyone adds a unit with a bad domain/enum, or lets the
schema drift from taxonomy.py, this test (and CI) goes red.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_base_has_no_drift():
    result = subprocess.run(
        [sys.executable, "ops/tools/check_kb_integrity.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        "KB integrity guard failed:\n" + result.stdout + result.stderr
    )
    assert "IN SYNC" in result.stdout
