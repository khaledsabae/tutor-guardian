"""Manual hosted runtime experiment must never become a deployment gate."""
from pathlib import Path

import yaml


def test_runtime_workflow_is_manual_readonly_and_uses_copied_production_index():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/chroma-1x-runtime.yml"
    assert path.exists(), "runtime workflow is missing"
    text = path.read_text()
    data = yaml.safe_load(text)
    assert data.get("on", data.get(True)) == {"workflow_dispatch": None}
    assert data["permissions"] == {"contents": "read"}
    assert "secrets." not in text and "ssh " not in text
    job = data["jobs"]["runtime"]
    assert job["runs-on"] == "ubuntu-latest" and "environment" not in job
    assert all("runner." not in str(v) for v in job["env"].values())
    steps = job["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    scripts = "\n".join(s.get("run", "") for s in steps)
    assert "$GITHUB_ENV" in scripts and "--require-hashes" in scripts
    assert scripts.count("python -m venv") == 2
    assert "requirements-prod.lock" in scripts and "requirements-dev.lock" in scripts
    assert '"chromadb==1.5.9"' in scripts and "pip check" in scripts
    assert "--constraints" in scripts and "candidate-constraints.txt" in scripts
    assert "pytest backend/tests" in scripts and "--junitxml" in scripts
    assert job["env"]["SKIP_API_SMOKE"] == "1"
    build = next(i for i, s in enumerate(steps) if "chroma_runtime_probe.py build" in s.get("run", ""))
    copy = next(i for i, s in enumerate(steps) if "chroma_runtime_probe.py copy" in s.get("run", ""))
    migrate = next(i for i, s in enumerate(steps) if "chroma_runtime_probe.py candidate" in s.get("run", ""))
    assert build < copy < migrate
    assert '"$COPIED_INDEX"' in steps[migrate]["run"]
    assert "freeze" in scripts
    summary = next(s for s in steps if "chroma_runtime_probe.py summary" in s.get("run", ""))
    assert summary["if"] == "always()"
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "always()" and upload["with"]["if-no-files-found"] == "error"
    tests = next(s for s in steps if "pytest backend/tests" in s.get("run", ""))
    assert "always()" in tests["if"]  # Migration failure must not suppress test evidence.
