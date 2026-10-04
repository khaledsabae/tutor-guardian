#!/usr/bin/env bash
# Run the in-image smoke (ops/tools/candidate_smoke.py) against a candidate
# backend image. The ONE invocation shared by deploy.yml (on the production
# host) and the candidate-image workflow (GitHub-hosted, on pull requests), so
# what a PR proves is what the deploy runs.
#
# Usage: ops/tools/candidate_smoke.sh IMAGE [CONTAINER_NAME] [-- COMMAND...]
#   CONTAINER_NAME  lets the caller remove the container if the job is
#                   cancelled — killing `docker run` does not stop the
#                   container (a cancelled deploy's test container ran on for
#                   an hour on 2026-10-04).
#   COMMAND         defaults to the smoke; deploy.yml reuses the same limits
#                   for the in-image KB integrity check.
#
# Limits, because on the production host this shares 4 vCPUs with live sites:
#   --cpus 1           a hard cap of one core;
#   --cpu-shares 256   cgroup v2 weight ~10 against the default 100, so under
#                      contention the live containers win (the container
#                      equivalent of `nice`);
#   --memory 4g        the smoke peaks around 2 GB; a runaway cannot push
#                      the host into swap;
#   --network none     hermetic: no production service, no model download,
#                      no hanging on DNS. Loopback still works for uvicorn.
# No .env, no secrets, no volumes: the image alone.
set -euo pipefail

image="${1:?usage: candidate_smoke.sh IMAGE [CONTAINER_NAME] [-- COMMAND...]}"
name="${2:-tg-candidate-smoke-$$}"
shift $(( $# >= 2 ? 2 : 1 ))
[ "${1:-}" = "--" ] && shift
[ $# -gt 0 ] || set -- python ops/tools/candidate_smoke.py

exec docker run --rm --name "$name" \
  --cpus "${SMOKE_CPUS:-1}" --cpu-shares 256 --memory 4g \
  --network none \
  -e PYTHONPATH=/app/backend \
  "$image" "$@"
