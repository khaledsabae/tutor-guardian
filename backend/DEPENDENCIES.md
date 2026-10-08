# Backend dependency manifests (Phase 3)

## Audited baseline and scope

Base: `origin/main` at `5d566611efb09808bb4b94f47ae7ea25b0abe4b2`.
PR 61 was still open at the audit; no changes were taken from its branch.

The original manifest had 22 direct dependencies, including two test-only
packages: `pytest` and `pytest-anyio`. No production application imports either.
Tests import pytest; AnyIO already supplies pytest integration as a runtime
transitive dependency. The existing `pytest-anyio` declaration is retained here
without changing its bound or trying to remove it as part of this split.

`openai` (Azure/cloud gateway), `rank-bm25` (hybrid retrieval), `firebase-admin`
(push sender), and `cryptography` (sync encryption) are runtime dependencies,
even though three were previously below the Dev/Test heading. Their declarations
stay in `requirements.txt`. No runtime dependency version or bound changes.

- `requirements.txt`: the 20 runtime declarations. Docker installs their
  hash-locked closure, `.github/ci/requirements-prod.lock` (see below).
- `requirements-dev.txt`: the two existing test declarations. Their hash-locked
  additions, `.github/ci/requirements-dev.lock`, are installed on top of the prod
  lock by `.github/actions/backend-env/action.yml`; its pip cache tracks both locks.
- Ruff remains the existing separate hosted lint-job install. No Ruff pin or
  additional formatter/resolver dependency is invented in this change.

## Constraint snapshot and reproducibility limits

The repository already has 143 exact pins in
`.github/ci/constraints-prod.txt`, from the recorded production Python 3.11.17
environment on 2026-10-04. Docker and hosted test CI install exactly these
versions through the hash locks generated from it (next section). All 22
direct declarations, including the moved test tools, accept their existing
snapshot versions. The snapshot itself is unchanged.

The recorded snapshot SHA256 is
`bb0803c914f59a2ad0e15dc6c2c86b96ead40d284c081ba0e66f71eba6ae79de`.
Its requirements-file hash remains historical evidence of the original mixed
manifest. It is deliberately not rewritten to pretend this split was observed
in production. Hosted CI warns about that provenance difference. The pins
continue to apply; a manifest-only change does not remove them (and now also
requires regenerating the locks).

## Hash-locked install (production image and hosted CI)

The constraints say *which version*; the locks also say *which file*. Every
install of the backend's package set names each allowed artifact by sha256, so a
wheel that is republished, swapped on a mirror or compromised upstream fails the
install instead of entering the image:

| File | Contents | Installed by |
|---|---|---|
| `.github/ci/requirements-prod.lock` | closure of `requirements.txt`: 139 constraint pins + `setuptools` | `backend/Dockerfile`; CI `backend-env` |
| `.github/ci/requirements-dev.lock` | what `requirements-dev.txt` adds: `pytest`, `pytest-anyio`, `pluggy`, `iniconfig` | CI `backend-env`; candidate-smoke tools (`backend-image`, `--target`) |

Both are generated from the constraints and never choose a version: together
they hold exactly the 143 pins of `constraints-prod.txt`, at the same versions,
plus `setuptools` (below). The install command everywhere is

```sh
pip install --require-hashes --no-deps --only-binary=:all: -r .github/ci/requirements-prod.lock [-r .github/ci/requirements-dev.lock]
pip check
```

- `--require-hashes`: every line carries `--hash=sha256:…`; pip refuses any
  file whose digest is not listed, and any requirement without one.
- `--no-deps`: the lock *is* the closure; pip resolves nothing. `pip check`
  afterwards proves no dependency is missing or off-range (both installs run it).
- `--only-binary=:all:`: no sdist, so no package's build code runs during the
  install (and no unhashed build dependencies get fetched).
- Hashes listed per package are those of the published wheels of that exact
  version that can install on CPython 3.11 / Linux x86_64 (any manylinux level);
  sdists and other platforms are left out of the allowlist.

**torch (CPU).** The source is unchanged: the CPU-only build from
`https://download.pytorch.org/whl/cpu` (the default PyPI Linux wheel is the CUDA
build and drags in ~4 GB of `nvidia-*`). The prod lock names it as a direct URL
to that one wheel with its sha256, e.g.
`torch @ https://download.pytorch.org/whl/cpu/torch-2.13.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl --hash=sha256:…`,
taken from the PyTorch index's own `#sha256=` link. No `--index-url` /
`--extra-index-url` is needed anywhere, so every other package can only come
from PyPI. The image build still fails if any `nvidia-*` package appears.

**setuptools** is the one locked package the constraints lack: `pip freeze`
hides it, but torch 2.13 requires `setuptools>=77.0.3`. It is pinned in the
generator (`TOOLING`) at production's own version, 79.0.1, read from `tg_backend`
with `importlib.metadata` on 2026-10-08 (same container: Python 3.11.17, pip
24.0), rather than left to whatever the base image or runner ships. Keep it equal
to production's; a future refresh could capture it with `pip freeze --all`.

### Regenerating

After `.github/ci/refresh-constraints-from-prod.sh`, or any edit to
`requirements.txt` / `requirements-dev.txt` / the constraints file:

```sh
python3.11 -m venv /tmp/tg-lock && /tmp/tg-lock/bin/pip install -q packaging
/tmp/tg-lock/bin/python .github/ci/lock-backend-deps.py   # from the repo root
```

It must run under Python 3.11 on Linux x86_64 (environment markers are evaluated
by the running interpreter; it refuses otherwise) and needs pypi.org and
download.pytorch.org. It resolves both manifests under the constraints with
`pip install --dry-run --report` (resolution only), then reads hashes from
PyPI's JSON API and the PyTorch CPU index. It **refuses to write** if the resolve
lands off a pin, needs a package the constraints do not pin, or leaves a pin
neither manifest uses. Re-running it on unchanged inputs reproduces the files
byte for byte. Each lock records the sha256 of the constraints and both
manifests it was generated from.

### The check that keeps them in agreement

`HashLockTests` in `backend/tests/test_dependency_manifests.py` (part of the
hosted pytest run, i.e. the deploy gate) fails when:

- the constraints file or either manifest changed since the locks were generated
  (recorded sha256 / Python header mismatch);
- any constraint pin is missing from the locks or locked at another version, or
  the locks hold a package the constraints do not pin (besides `setuptools`), or
  a package appears in both locks;
- a line lacks a sha256 hash, carries any other option, or a lock sets an index;
- a direct requirement of either manifest is not locked, or its locked version
  falls outside the declared range;
- torch is anything but the `+cpu` cp311 x86_64 wheel on
  `download.pytorch.org/whl/cpu`, or anything else is a direct URL.

Wiring tests in the same file pin the install commands in `backend/Dockerfile`,
`backend-env` and `backend-image`. The lock files are in the path filters of
`backend.yml`, `deploy.yml` (prod lock), `candidate-image.yml` and `docker.yml`,
and in `ops/tools/check_deploy_drift.py`.

### Developer machines

The locks target Linux x86_64 / CPython 3.11 only. Elsewhere, install the
manifests under the constraints (unhashed) as before:

```sh
C=.github/ci/constraints-prod.txt
python -m pip install --no-deps --index-url https://download.pytorch.org/whl/cpu "$(grep '^torch==' "$C")"
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt -c "$C"
python -m pip check
```

### Limits

- The base image `python:3.11-slim` (a moving tag), its `pip`, and CI's
  `pip install --upgrade pip` are not hash-pinned; neither are apt packages.
- Hashes prove the files are the ones locked, not that the upstream release was
  benign when locked. A regeneration trusts PyPI and download.pytorch.org at
  that moment; review lock diffs (new hashes for an unchanged version are a red flag).
- Platform/Python changes, Chroma's persisted-volume migration, and ML major
  upgrades remain separate tasks.

## Candidate smoke without production test installs

The candidate smoke runs a pytest subset in `--network none` containers. Removing
pytest from Docker without supplying those tools would break that deployment
gate. The shared hosted image action now installs only the hash-locked dev
additions (`requirements-dev.lock`, `--no-deps`, binary wheels only) into a fresh
runner-temporary target directory; what pytest imports besides them (packaging,
pygments, anyio) is already in the image at the same pinned version. It exposes
the path via `CANDIDATE_TEST_TOOLS_DIR`.

`ops/tools/candidate_smoke.sh` checks the directory exists, mounts it read-only at
`/opt/candidate-test-tools`, and prepends it to `PYTHONPATH`. The exact candidate
image/digest is still smoked: no replacement image or development layer is
published. Its network, CPU/memory limits and default non-root image user stay
unchanged. No production directory, DB or secrets are mounted. Both the normal
smoke and deliberately broken-image checks inherit this hosted job environment.
The host prepares the tools before the offline run; no pip install occurs in
the smoke container. A custom command can still run without a tooling mount.

This injection necessarily makes pytest and its dependencies visible during
the disposable smoke. Their existing pins must be reviewed with dev updates;
it does not demonstrate a pytest-free container integration run in this task.
Before merge, parent review must confirm the constrained tooling install and
real offline candidate smoke on a permitted hosted runner. No workflow was
dispatched, build performed, image pushed or production setting changed here.

## Update proposals

`.github/dependabot.yml` enables monthly pip version-update proposals for
`pytest` and `pytest-anyio` only, grouped for review, capped at three open PRs,
with major updates ignored. Runtime and ML packages are outside that allowlist.
This adds no auto-merge, publish or deployment step. Repository security-alert
settings are separate from this version-update configuration.

A proposal that requires a version incompatible with the existing constraints
must fail CI until the constraint provenance and target install are reviewed;
do not relax production pins blindly to accept it. Full transitive lock refresh
automation and runtime update proposals are not implemented in this phase.

## Bounded verification

The meaningful install/workflow contract checks run without application fixtures,
Docker, network or a package resolver:

```sh
python3 -m unittest discover -s backend/tests -p test_dependency_manifests.py -v
bash -n ops/tools/candidate_smoke.sh
```

The fifteen checks cover manifest separation, compatibility with existing pins,
runtime consumers and ML bounds, CI/cache wiring, the hash-locked runtime-only
Docker install, lock/constraints agreement (above), bounded Dependabot
configuration, and the actual shell wrapper using a fake
Docker executable. They verify read-only tooling mounts (including paths with
spaces), offline execution, rejection of missing tool directories before Docker,
and backward-compatible command overrides. They do not replace a real install
or container test.
