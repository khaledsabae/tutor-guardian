#!/usr/bin/env bash
# Run the in-image smoke (ops/tools/candidate_smoke.py) against a candidate
# backend image. The ONE invocation, used by .github/actions/backend-image for
# the deploy's image job, PR checks and manual verify runs (all GitHub-hosted),
# so what a PR proves is what gates a deploy. The production host runs no
# smoke any more: it pulls the image this passed on.
#
# Usage: ops/tools/candidate_smoke.sh IMAGE [CONTAINER_NAME] [-- COMMAND...]
#   CONTAINER_NAME  lets the caller remove the container if the job is
#                   cancelled — killing `docker run` does not stop the
#                   container (a cancelled deploy's test container ran on for
#                   an hour on 2026-10-04).
#   COMMAND         defaults to the smoke; the same limits are reused for
#                   the in-image KB integrity check.
#
# Limits — written for the production host, where this ran beside live sites
# until 2026-10-04; kept so the smoke stays bounded and hermetic anywhere:
#   --cpus 1           a hard cap of one core;
#   --cpu-shares 256   cgroup v2 weight ~10 against the default 100, so under
#                      contention the live containers win (the container
#                      equivalent of `nice`);
#   --memory 4g        the smoke peaks around 2 GB; a runaway cannot push
#                      the host into swap;
#   --network none     hermetic: no production service, no model download,
#                      no hanging on DNS. Loopback still works for uvicorn.
# No .env, secrets or production volumes. Hosted CI may supply test tooling
# through CANDIDATE_TEST_TOOLS_DIR: a read-only mount, not an image install.
set -euo pipefail

image="${1:?usage: candidate_smoke.sh IMAGE [CONTAINER_NAME] [-- COMMAND...]}"
name="${2:-tg-candidate-smoke-$$}"
shift $(( $# >= 2 ? 2 : 1 ))
[ "${1:-}" = "--" ] && shift
[ $# -gt 0 ] || set -- python ops/tools/candidate_smoke.py

tool_mount=()
pythonpath=/app/backend
if [ -n "${CANDIDATE_TEST_TOOLS_DIR:-}" ]; then
  [ -d "$CANDIDATE_TEST_TOOLS_DIR" ] || {
    echo "::error::candidate test-tool directory does not exist" >&2
    exit 1
  }
  tool_mount=(--mount "type=bind,source=$CANDIDATE_TEST_TOOLS_DIR,target=/opt/candidate-test-tools,readonly")
  pythonpath=/opt/candidate-test-tools:/app/backend
fi

exec docker run --rm --name "$name" \
  --cpus "${SMOKE_CPUS:-1}" --cpu-shares 256 --memory 4g \
  --network none \
  "${tool_mount[@]}" \
  -e "PYTHONPATH=$pythonpath" \
  "$image" "$@"
