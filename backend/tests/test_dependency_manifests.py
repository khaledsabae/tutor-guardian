"""Lightweight install-contract checks; no Docker, resolver, model or API calls.

Run directly with unittest so backend's application fixtures are not needed.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[2]
DEV_NAMES = {"pytest", "pytest-anyio"}
ML_PINS = {
    "torch": "==2.13.0", "transformers": "==5.16.1",
    "sentence-transformers": "==6.0.0", "huggingface-hub": "==1.29.0",
}


def requirements(path):
    return {
        canonicalize_name(req.name): req
        for line in path.read_text().splitlines()
        if (text := line.split("#", 1)[0].strip())
        for req in [Requirement(text)]
    }


class DependencyManifestTests(unittest.TestCase):
    def test_runtime_excludes_test_tools_and_keeps_runtime_consumers(self):
        runtime = requirements(ROOT / "backend/requirements.txt")
        self.assertFalse(DEV_NAMES & runtime.keys())
        self.assertTrue({"openai", "rank-bm25", "firebase-admin", "cryptography"} <= runtime.keys())
        for name, pin in ML_PINS.items():
            self.assertEqual(str(runtime[name].specifier), pin)
        self.assertEqual(str(runtime["chromadb"].specifier), "<1,>=0.5")

    def test_dev_file_contains_only_existing_test_tools(self):
        path = ROOT / "backend/requirements-dev.txt"
        self.assertTrue(path.exists(), "separate development manifest required")
        dev = requirements(path)
        self.assertEqual(set(dev), DEV_NAMES)
        self.assertEqual(str(dev["pytest"].specifier), ">=8.0")
        self.assertEqual(str(dev["pytest-anyio"].specifier), ">=0.0.0")

    def test_all_direct_requirements_fit_existing_production_constraints(self):
        constraints = requirements(ROOT / ".github/ci/constraints-prod.txt")
        for path in ("backend/requirements.txt", "backend/requirements-dev.txt"):
            self.assertTrue((ROOT / path).exists())
            for name, req in requirements(ROOT / path).items():
                self.assertIn(name, constraints)
                version = str(constraints[name].specifier).removeprefix("==")
                self.assertIn(version, req.specifier, f"{path}: {name}")

    def test_hosted_tests_install_both_manifests_under_same_constraints(self):
        action = yaml.safe_load((ROOT / ".github/actions/backend-env/action.yml").read_text())
        install = next(s["run"] for s in action["runs"]["steps"] if s.get("name") == "Install production's package set")
        self.assertIn('-r backend/requirements-dev.txt', install)
        self.assertIn('-c "$C"', install)
        cache = next(s["with"]["cache-dependency-path"] for s in action["runs"]["steps"] if s.get("uses", "").startswith("actions/setup-python"))
        self.assertIn("backend/requirements-dev.txt", cache)

    def test_image_install_remains_runtime_only(self):
        dockerfile = (ROOT / "backend/Dockerfile").read_text()
        self.assertIn('-r backend/requirements.txt -c backend/constraints-prod.txt', dockerfile)
        self.assertNotIn('-r backend/requirements-dev.txt', dockerfile)
        self.assertIn('https://download.pytorch.org/whl/cpu', dockerfile)

    def test_image_action_prepares_dev_tools_outside_image(self):
        action = yaml.safe_load((ROOT / ".github/actions/backend-image/action.yml").read_text())
        scripts = "\n".join(s.get("run", "") for s in action["runs"]["steps"])
        self.assertIn("CANDIDATE_TEST_TOOLS_DIR=", scripts)
        self.assertIn("--target", scripts)
        self.assertIn("-r backend/requirements-dev.txt", scripts)
        self.assertIn("-c .github/ci/constraints-prod.txt", scripts)

    def test_dependabot_only_proposes_dev_updates(self):
        path = ROOT / ".github/dependabot.yml"
        self.assertTrue(path.exists(), "bounded dependency update configuration required")
        config = yaml.safe_load(path.read_text())
        self.assertEqual(config["version"], 2)
        pip = next(u for u in config["updates"] if u["package-ecosystem"] == "pip")
        self.assertEqual(pip["directory"], "/backend")
        self.assertEqual({a["dependency-name"] for a in pip["allow"]}, DEV_NAMES)
        self.assertLessEqual(pip["open-pull-requests-limit"], 3)
        self.assertIn({"dependency-name": "*", "update-types": ["version-update:semver-major"]}, pip["ignore"])


class CandidateToolMountTests(unittest.TestCase):
    def invoke(self, tools=None):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            capture = scratch / "argv.json"
            docker = scratch / "docker"
            docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n')
            docker.chmod(0o700)
            env = dict(os.environ, PATH=str(scratch) + os.pathsep + os.environ["PATH"], CAPTURE=str(capture))
            env.pop("CANDIDATE_TEST_TOOLS_DIR", None)
            if tools == "existing":
                target = scratch / "test tools"
                target.mkdir()
                env["CANDIDATE_TEST_TOOLS_DIR"] = str(target)
            elif tools == "missing":
                env["CANDIDATE_TEST_TOOLS_DIR"] = str(scratch / "missing")
            result = subprocess.run(["bash", str(ROOT / "ops/tools/candidate_smoke.sh"), "candidate@sha256:abc", "test-container", "--", "python", "custom.py"], env=env, capture_output=True, text=True, timeout=10)
            argv = json.loads(capture.read_text()) if capture.exists() else None
            return result, argv

    def test_injected_tools_are_read_only_and_smoke_stays_offline(self):
        result, argv = self.invoke("existing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--mount", argv)
        mount = argv[argv.index("--mount") + 1]
        self.assertIn("target=/opt/candidate-test-tools", mount)
        self.assertIn("readonly", mount)
        self.assertIn("test tools", mount)
        self.assertIn("PYTHONPATH=/opt/candidate-test-tools:/app/backend", argv)
        self.assertEqual(argv[argv.index("--network") + 1], "none")
        self.assertEqual(argv[-3:], ["candidate@sha256:abc", "python", "custom.py"])

    def test_missing_tool_directory_fails_before_docker(self):
        result, argv = self.invoke("missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(argv)

    def test_command_override_without_tools_keeps_previous_contract(self):
        result, argv = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--mount", argv)
        self.assertIn("PYTHONPATH=/app/backend", argv)
        self.assertEqual(argv[argv.index("--network") + 1], "none")


if __name__ == "__main__":
    unittest.main()
