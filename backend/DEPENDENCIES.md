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

- `requirements.txt`: the 20 runtime declarations; Docker installs this file.
- `requirements-dev.txt`: the two existing test declarations, installed alongside
  the runtime file by `.github/actions/backend-env/action.yml`. Its cache tracks
  both manifests and the constraint snapshot.
- Ruff remains the existing separate hosted lint-job install. No Ruff pin or
  additional formatter/resolver dependency is invented in this change.

## Constraint snapshot and reproducibility limits

The repository already has 143 exact pins in
`.github/ci/constraints-prod.txt`, from the recorded production Python 3.11.17
environment on 2026-10-04. Docker and hosted test CI both apply this file. All 22
direct declarations, including the moved test tools, accept their existing
snapshot versions. The snapshot itself and Dockerfile are unchanged.

The recorded snapshot SHA256 is
`bb0803c914f59a2ad0e15dc6c2c86b96ead40d284c081ba0e66f71eba6ae79de`.
Its requirements-file hash remains historical evidence of the original mixed
manifest. It is deliberately not rewritten to pretend this split was observed
in production. Hosted CI warns about that provenance difference. Constraints
continue to apply; a manifest-only change does not remove the pins.

The established development install sequence is:

```sh
C=.github/ci/constraints-prod.txt
torch_pin="$(grep '^torch==' "$C")"
python -m pip install --no-deps --index-url https://download.pytorch.org/whl/cpu "$torch_pin"
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt -c "$C"
python -m pip check
```

These are instructions, not an install executed in this task. The first command
preserves the existing CPU-wheel source; the default PyPI torch wheel can pull
CUDA dependencies. Preserve the explicit torch, transformers,
sentence-transformers and huggingface_hub pins and `chromadb<1`.

**This is a version-constrained approach, not a new fully resolved hash lock.**
A freeze does not prove dependency closure or wheel availability for every
platform, nor does it record artifact hashes. No resolver, package download,
model download, Docker build or live environment inspection was run here.
Do not label the new dev manifest a lock or use an unrelated local `pip freeze`
as production evidence.

Remaining work needs an independently reviewed, bounded resolver run for the
actual Python/Linux CPU target, with transitive closure, exact wheel sources and
hashes, a clean constrained install and `pip check`, and a candidate model-load
and offline smoke check. Platform/Python changes, Chroma's persisted-volume
migration, and ML major upgrades are separate tasks. Do not regenerate the
production snapshot merely to make its old provenance hash match this edit.

## Candidate smoke without production test installs

The candidate smoke runs a pytest subset in `--network none` containers. Removing
pytest from Docker without supplying those tools would break that deployment
gate. The shared hosted image action now prepares only the dev manifest into a
fresh runner-temporary target directory under the same constraints, allowing
binary wheels only. It exposes the path via `CANDIDATE_TEST_TOOLS_DIR`.

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

The ten checks cover manifest separation, compatibility with existing pins,
runtime consumers and ML bounds, CI/cache wiring, runtime-only Docker install,
bounded Dependabot configuration, and the actual shell wrapper using a fake
Docker executable. They verify read-only tooling mounts (including paths with
spaces), offline execution, rejection of missing tool directories before Docker,
and backward-compatible command overrides. They do not replace a real install
or container test.
