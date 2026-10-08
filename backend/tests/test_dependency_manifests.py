"""Lightweight install-contract checks; no Docker, resolver, model or API calls.

Run directly with unittest so backend's application fixtures are not needed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from urllib.parse import unquote

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename


ROOT = Path(__file__).resolve().parents[2]
DEV_NAMES = {"pytest", "pytest-anyio"}
ML_PINS = {
    "torch": "==2.13.0", "transformers": "==5.16.1",
    "sentence-transformers": "==6.0.0", "huggingface-hub": "==1.29.0",
}


CONSTRAINTS = ".github/ci/constraints-prod.txt"
PROD_LOCK = ".github/ci/requirements-prod.lock"
DEV_LOCK = ".github/ci/requirements-dev.lock"
TORCH_CPU = "https://download.pytorch.org/whl/cpu/"
# Locked but absent from the constraints: `pip freeze` hides setuptools, and
# torch requires setuptools>=77.0.3 (TOOLING in .github/ci/lock-backend-deps.py).
LOCK_ONLY = {"setuptools"}
SHA256 = re.compile(r"--hash=sha256:[0-9a-f]{64}")


def lock(path):
    """{name: (version, [hashes], url or None)} plus the `# key: value` header."""
    text = (ROOT / path).read_text()
    header = dict(
        line[2:].split(": ", 1) for line in text.splitlines()
        if line.startswith("# ") and re.match(r"# [a-z0-9-]+: ", line)
    )
    entries = {}
    for line in text.replace("\\\n", " ").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        spec, _, options = line.partition(" --")
        options = ("--" + options).split() if options else []
        hashes = [o for o in options if SHA256.fullmatch(o)]
        assert hashes and len(hashes) == len(options), f"{path}: only --hash options, at least one: {line[:80]}"
        req = Requirement(spec.strip())
        name = canonicalize_name(req.name)
        assert name not in entries, f"{path}: {name} twice"
        if req.url:
            version = str(parse_wheel_filename(unquote(req.url.rsplit("/", 1)[1]))[1])
        else:
            assert len(req.specifier) == 1 and next(iter(req.specifier)).operator == "==", line[:80]
            version = next(iter(req.specifier)).version
        entries[name] = (version, hashes, req.url)
    return entries, header


def pins(path):
    return {name: str(req.specifier).removeprefix("==") for name, req in requirements(ROOT / path).items()}


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

    def test_hosted_tests_install_both_locks_with_hashes(self):
        action = yaml.safe_load((ROOT / ".github/actions/backend-env/action.yml").read_text())
        install = next(s["run"] for s in action["runs"]["steps"] if s.get("name") == "Install production's package set")
        install = install.replace("\\\n", " ")
        self.assertRegex(install, r"pip install --require-hashes --no-deps --only-binary=:all: +"
                         rf"-r {re.escape(PROD_LOCK)} -r {re.escape(DEV_LOCK)}")
        self.assertNotIn("--index-url", install)
        self.assertNotIn("-r backend/requirements", install)
        self.assertIn("pip check", install)
        cache = next(s["with"]["cache-dependency-path"] for s in action["runs"]["steps"] if s.get("uses", "").startswith("actions/setup-python"))
        self.assertIn(PROD_LOCK, cache)
        self.assertIn(DEV_LOCK, cache)

    def test_image_install_is_the_hash_locked_runtime_set(self):
        dockerfile = (ROOT / "backend/Dockerfile").read_text()
        self.assertIn(f"COPY {PROD_LOCK} ./backend/requirements-prod.lock", dockerfile)
        installs = [r for r in re.findall(r"^RUN (.*?)(?<!\\)$", dockerfile, re.S | re.M) if "pip install" in r]
        self.assertEqual(len(installs), 1, "one pip install in the image: the lock")
        install = installs[0].replace("\\\n", " ")
        self.assertRegex(install, r"pip install --no-cache-dir --require-hashes --no-deps --only-binary=:all: +"
                         r"-r backend/requirements-prod\.lock")
        self.assertIn("pip check", install)
        self.assertNotIn("requirements-dev", dockerfile)
        self.assertNotIn(DEV_LOCK, dockerfile)
        self.assertNotIn("--index-url", dockerfile)

    def test_image_action_prepares_dev_tools_outside_image(self):
        action = yaml.safe_load((ROOT / ".github/actions/backend-image/action.yml").read_text())
        scripts = "\n".join(s.get("run", "") for s in action["runs"]["steps"]).replace("\\\n", " ")
        self.assertIn("CANDIDATE_TEST_TOOLS_DIR=", scripts)
        self.assertRegex(scripts, r"pip install --require-hashes --no-deps --only-binary=:all: --no-compile +"
                         rf"--target \"\$tools\" -r {re.escape(DEV_LOCK)}")

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



class HashLockTests(unittest.TestCase):
    """The hash locks and production's constraints describe one package set."""

    def setUp(self):
        self.constraints = pins(CONSTRAINTS)
        self.prod, self.prod_header = lock(PROD_LOCK)
        self.dev, self.dev_header = lock(DEV_LOCK)

    def test_locks_were_generated_from_the_current_inputs(self):
        # Any edit to the constraints or a manifest needs a regenerated lock
        # (.github/ci/lock-backend-deps.py), or the image installs a stale set.
        constraints_text = (ROOT / CONSTRAINTS).read_text()
        python = re.search(r"^# python: *(\S+)", constraints_text, re.M).group(1)
        for header in (self.prod_header, self.dev_header):
            for key, path in (("constraints-sha256", CONSTRAINTS),
                              ("requirements-sha256", "backend/requirements.txt"),
                              ("requirements-dev-sha256", "backend/requirements-dev.txt")):
                self.assertEqual(header.get(key), hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                                 f"{path} changed since the locks were generated — run .github/ci/lock-backend-deps.py")
            self.assertEqual(header.get("python"), python)

    def test_every_constraint_pin_is_locked_at_its_version_and_vice_versa(self):
        self.assertFalse(self.prod.keys() & self.dev.keys(), "a package in both locks")
        locked = {name: entry[0] for name, entry in {**self.prod, **self.dev}.items()}
        missing = sorted(set(self.constraints) - set(locked))
        self.assertFalse(missing, f"pinned in {CONSTRAINTS} but not locked")
        extra = sorted(set(locked) - set(self.constraints) - LOCK_ONLY)
        self.assertFalse(extra, f"locked but not pinned in {CONSTRAINTS}")
        off = {n: (locked[n], v) for n, v in self.constraints.items() if locked[n] != v}
        self.assertFalse(off, "lock version differs from the production pin (lock, pin)")
        self.assertEqual(len(locked), len(self.constraints) + len(LOCK_ONLY))
        self.assertTrue(LOCK_ONLY <= self.prod.keys())

    def test_manifests_are_covered_by_their_locks(self):
        for path, allowed in (("backend/requirements.txt", self.prod),
                              ("backend/requirements-dev.txt", {**self.prod, **self.dev})):
            for name, req in requirements(ROOT / path).items():
                self.assertIn(name, allowed, f"{path}: {name} not locked")
                self.assertIn(allowed[name][0], req.specifier, f"{path}: {name}")
        self.assertEqual(set(self.dev) & DEV_NAMES, DEV_NAMES)
        self.assertFalse(set(requirements(ROOT / "backend/requirements.txt")) & self.dev.keys())

    def test_torch_is_the_cpu_wheel_from_the_pytorch_index_and_nothing_else_is_a_url(self):
        version, hashes, url = self.prod["torch"]
        self.assertEqual(version, self.constraints["torch"])
        self.assertTrue(version.endswith("+cpu"))
        self.assertTrue(url.startswith(TORCH_CPU), url)
        _, _, _, tags = parse_wheel_filename(unquote(url.rsplit("/", 1)[1]))
        self.assertTrue(all(t.interpreter == "cp311" and t.platform.endswith("_x86_64") for t in tags))
        self.assertEqual(len(hashes), 1)
        urls = sorted(n for n, e in {**self.prod, **self.dev}.items() if e[2] and n != "torch")
        self.assertFalse(urls, "only torch may be a direct URL")
        self.assertFalse(any(n.startswith("nvidia-") for n in self.prod))

    def test_locks_carry_no_index_or_install_options(self):
        # The source is fixed by the install command (PyPI) and torch's URL; a
        # file-level --extra-index-url or --trusted-host would widen it.
        for path in (PROD_LOCK, DEV_LOCK):
            for line in (ROOT / path).read_text().splitlines():
                self.assertFalse(line.lstrip().startswith(("-", "--")) and not SHA256.search(line), line)


if __name__ == "__main__":
    unittest.main()
