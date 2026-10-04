#!/usr/bin/env bash
# The in-image smoke is a gate only if it can say no. Break a copy of the
# candidate image three ways and require ops/tools/candidate_smoke.sh to fail
# on each — at the step that should catch it, not by accident somewhere else.
#
# Usage: .github/ci/reject-broken-images.sh IMAGE   (an image in the local daemon)
# Builds with the daemon's own builder (plain `docker build`), which can start
# FROM a local image.
set -uo pipefail
base="${1:?usage: reject-broken-images.sh IMAGE}"

# name · the step the smoke must stop at · how the image is broken
sabotage() {
  # Broken as root (the HF cache's parent dir is root's), run as appuser like
  # the real image.
  if ! printf 'FROM %s\nUSER root\nRUN %s\nUSER appuser\n' "$base" "$3" \
      | docker build -q -t "tg-broken:$1" - >/dev/null; then
    echo "::error::could not build the sabotaged image $1"
    return 1
  fi
  if out=$(ops/tools/candidate_smoke.sh "tg-broken:$1" 2>&1); then
    echo "::error::the smoke PASSED an image with $1 — it would have deployed it"
    return 1
  fi
  if ! grep -q "candidate smoke FAILED — $2" <<<"$out"; then
    tail -n 25 <<<"$out"
    echo "::error::the smoke rejected $1, but not at '$2'"
    return 1
  fi
  echo "✓ $1: rejected — $(grep -m1 'candidate smoke FAILED' <<<"$out" | cut -c1-160)"
}

rc=0
sabotage missing-router imports 'rm /app/backend/app/routers/health.py' || rc=1
sabotage missing-models models 'rm -rf /app/.cache/huggingface' || rc=1
sabotage boot-failure server 'rm /app/backend/guardrails/child_surface.v1.yaml' || rc=1
docker image rm tg-broken:missing-router tg-broken:missing-models tg-broken:boot-failure >/dev/null 2>&1 || true
exit $rc
