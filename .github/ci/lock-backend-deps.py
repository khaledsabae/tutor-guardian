#!/usr/bin/env python3
"""Regenerate the hash-locked backend install from production's constraints.

    .github/ci/requirements-prod.lock  what backend/Dockerfile installs
    .github/ci/requirements-dev.lock   test tools CI adds on top (pytest & co.)

Both come from .github/ci/constraints-prod.txt: this script never chooses a
version. It resolves backend/requirements.txt (and requirements-dev.txt) UNDER
those constraints to learn which pins each manifest needs, then records the
sha256 of every published file of exactly that version that can install on
production's platform (CPython 3.11, Linux x86_64 glibc; wheels only — the
installs use --only-binary). It fails rather than writes if the resolve picks a
version off the constraints, needs a package the constraints lack, or leaves a
constraint pin that neither manifest uses.

Sources, the same as the unhashed install it replaces:
  torch       the CPU-only build from https://download.pytorch.org/whl/cpu,
              written as a direct URL to that one wheel plus its sha256 (the
              PyPI torch wheel is the CUDA build and pulls ~4 GB of nvidia-*).
  the rest    PyPI. Hashes come from PyPI's JSON API for that exact version.

setuptools is the one locked package production's freeze does not record:
`pip freeze` hides it, but torch requires setuptools>=77.0.3, so the lock pins
it (TOOLING below) instead of leaving it to whatever the base image or runner
ships.

Run from the repo root, with a Python of production's minor version on Linux
x86_64 (environment markers are evaluated by the running interpreter):

    python3.11 -m venv /tmp/tg-lock && /tmp/tg-lock/bin/pip install -q packaging
    /tmp/tg-lock/bin/python .github/ci/lock-backend-deps.py

Needs network (pypi.org, download.pytorch.org); downloads metadata, not wheels.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import platform
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

CONSTRAINTS = Path(".github/ci/constraints-prod.txt")
RUNTIME = Path("backend/requirements.txt")
DEV = Path("backend/requirements-dev.txt")
PROD_LOCK = Path(".github/ci/requirements-prod.lock")
DEV_LOCK = Path(".github/ci/requirements-dev.lock")

TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
# Not in the freeze (pip hides it), required by torch. Bump deliberately.
TOOLING = {"setuptools": "84.0.0"}

# Every tag pip on production's image (or a GitHub-hosted Ubuntu runner) could
# accept: CPython 3.11, any manylinux glibc level on x86_64. A file outside this
# set can never be installed there, so its hash is left out of the allowlist.
_PLATFORMS = (
    [f"manylinux_2_{m}_x86_64" for m in range(60, 4, -1)]
    + ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64", "linux_x86_64"]
)
TARGET_TAGS = set(cpython_tags((3, 11), abis=["cp311", "abi3", "none"], platforms=_PLATFORMS)) | set(
    compatible_tags((3, 11), interpreter="cp311", platforms=_PLATFORMS)
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_constraints() -> tuple[dict[str, tuple[str, str]], str]:
    pins, python = {}, None
    for line in CONSTRAINTS.read_text().splitlines():
        if line.startswith("# python:"):
            python = line.split(":", 1)[1].strip()
        text = line.split("#", 1)[0].strip()
        if "==" in text:
            name, version = (part.strip() for part in text.split("==", 1))
            pins[canonicalize_name(name)] = (name, version)
    if not python:
        sys.exit(f"{CONSTRAINTS}: no '# python:' header")
    return pins, python


def resolve(manifests: list[Path], extra_constraints: Path) -> dict[str, str]:
    """{name: version} pip installs for these manifests under the constraints."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        cmd = [
            sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
            "--quiet", "--only-binary=:all:", "--report", str(report),
            "--index-url", "https://pypi.org/simple", "--extra-index-url", TORCH_INDEX,
            "-c", str(CONSTRAINTS), "-c", str(extra_constraints),
        ]
        for manifest in manifests:
            cmd += ["-r", str(manifest)]
        subprocess.run(cmd, check=True)
        data = json.loads(report.read_text())
    return {canonicalize_name(i["metadata"]["name"]): i["metadata"]["version"] for i in data["install"]}


def get(url: str, accept: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept} if accept else {})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def pypi_hashes(name: str, version: str) -> list[str]:
    data = json.loads(get(f"https://pypi.org/pypi/{name}/{version}/json"))
    hashes = sorted(
        f["digests"]["sha256"]
        for f in data["urls"]
        if f["packagetype"] == "bdist_wheel"
        and not f.get("yanked")
        and set(parse_wheel_filename(f["filename"])[3]) & TARGET_TAGS
    )
    if not hashes:
        sys.exit(f"{name}=={version}: no PyPI wheel installs on CPython 3.11 Linux x86_64")
    return hashes


class _Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs += [v for k, v in attrs if k == "href"]


def torch_line(version: str) -> str:
    page = f"{TORCH_INDEX}/torch/"
    parser = _Links()
    parser.feed(get(page).decode())
    found = []
    for href in parser.hrefs:
        url, _, fragment = urllib.parse.urljoin(page, href).partition("#")
        filename = urllib.parse.unquote(url.rsplit("/", 1)[1])
        if not filename.endswith(".whl") or not fragment.startswith("sha256="):
            continue
        _, ver, _, tags = parse_wheel_filename(filename)
        if str(ver) == version and set(tags) & TARGET_TAGS:
            found.append((filename, fragment.removeprefix("sha256=")))
    if len(found) != 1:
        sys.exit(f"torch=={version}: expected one CPython 3.11 Linux x86_64 wheel on {page}, found {found}")
    filename, digest = found[0]
    # The documented index host, not whichever CDN host the page links to today.
    url = f"{TORCH_INDEX}/{urllib.parse.quote(filename)}"
    return f"torch @ {url} \\\n    --hash=sha256:{digest}"


def write_lock(path: Path, names: list[str], versions: dict[str, str], pins, python: str, role: str) -> None:
    header = [
        f"# {role}",
        "# GENERATED by .github/ci/lock-backend-deps.py — do not edit by hand.",
        "# Every version is production's pin from .github/ci/constraints-prod.txt;",
        "# install with: pip install --require-hashes --no-deps --only-binary=:all: -r <this file>",
        "# Target: CPython 3.11, Linux x86_64 (wheels only).",
        f"# python: {python}",
        f"# constraints-sha256: {sha256(CONSTRAINTS)}",
        f"# requirements-sha256: {sha256(RUNTIME)}",
        f"# requirements-dev-sha256: {sha256(DEV)}",
        "",
    ]
    body = []
    for key in names:
        version = versions[key]
        if key == "torch":
            body.append(torch_line(version))
            continue
        display = pins[key][0] if key in pins else key
        hashes = pypi_hashes(display, version)
        body.append(f"{display}=={version} \\\n" + " \\\n".join(f"    --hash=sha256:{h}" for h in hashes))
        print(f"  {display}=={version}: {len(hashes)} file(s)", file=sys.stderr)
    path.write_text("\n".join(header) + "\n".join(body) + "\n")
    print(f"wrote {path} ({len(names)} packages)", file=sys.stderr)


def main() -> None:
    if not RUNTIME.exists():
        sys.exit("run from the repo root")
    pins, python = read_constraints()
    want = tuple(int(p) for p in python.split(".")[:2])
    if sys.version_info[:2] != want or sys.platform != "linux" or platform.machine() != "x86_64":
        sys.exit(f"run with Python {want[0]}.{want[1]} on Linux x86_64 (markers are evaluated "
                 f"by this interpreter); this is {platform.python_version()} {sys.platform} {platform.machine()}")

    with tempfile.NamedTemporaryFile("w", suffix=".txt") as tooling:
        tooling.write("".join(f"{n}=={v}\n" for n, v in TOOLING.items()))
        tooling.flush()
        runtime = resolve([RUNTIME], Path(tooling.name))
        everything = resolve([RUNTIME, DEV], Path(tooling.name))

    problems = []
    for name, version in everything.items():
        expected = TOOLING.get(name) or (pins[name][1] if name in pins else None)
        if expected is None:
            problems.append(f"{name}=={version} is required but has no pin in {CONSTRAINTS}")
        elif version != expected:
            problems.append(f"{name} resolved to {version}, pinned {expected}")
    unused = sorted(set(pins) - set(everything))
    if unused:
        problems.append(f"pinned in {CONSTRAINTS} but required by neither manifest: {', '.join(unused)}")
    if set(runtime) - set(everything):
        problems.append("runtime resolve is not a subset of runtime+dev resolve")
    if problems:
        sys.exit("refusing to write a lock:\n  " + "\n  ".join(problems))

    write_lock(PROD_LOCK, sorted(runtime), everything, pins, python,
               "Production install (backend/requirements.txt), hash-locked.")
    write_lock(DEV_LOCK, sorted(set(everything) - set(runtime)), everything, pins, python,
               "Test tools (backend/requirements-dev.txt) on top of requirements-prod.lock, hash-locked.")


if __name__ == "__main__":
    main()
