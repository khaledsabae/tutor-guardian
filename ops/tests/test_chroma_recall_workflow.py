"""Safety contract for the manually dispatched hosted experiment."""
from pathlib import Path

import yaml


def test_recall_workflow_is_manual_hosted_and_isolated():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/chroma-1x-recall.yml"
    assert path.exists(), "manual recall workflow is missing"
    text = path.read_text()
    data = yaml.safe_load(text)
    # PyYAML's YAML 1.1 treats the unquoted Actions 'on' key as True.
    assert data.get("on", data.get(True)) == {"workflow_dispatch": None}
    assert data["permissions"] == {"contents": "read"}
    job = data["jobs"]["recall"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] <= 60
    assert "secrets." not in text and "environment" not in job
    assert "docker" not in text and "ssh " not in text
    steps = job["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    scripts = "\n".join(s.get("run", "") for s in steps)
    assert "requirements-prod.lock" in scripts and "--require-hashes" in scripts
    assert "constraints-prod.txt" in scripts and "pip check" in scripts
    assert 'python -m venv "$RUNNER_TEMP/baseline-venv"' in scripts
    assert 'python -m venv "$RUNNER_TEMP/candidate-venv"' in scripts
    assert "--ignore-installed --no-deps" in scripts and '"chromadb>=1,<2"' in scripts
    assert "chroma_recall_probe.py" in scripts and "--candidate" in scripts
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "${{ runner.temp }}/chroma-recall/evidence/"
    assert any("--summary" in s.get("run", "") and s.get("if") == "always()" for s in steps)
