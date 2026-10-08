#!/usr/bin/env bash
# Rewrite .github/ci/constraints-prod.txt from the package set the LIVE backend
# container runs. Read-only on production: one `pip freeze` inside tg_backend.
#
# When: after a deploy that rebuilt the image's pip layer — i.e. after any change
# to backend/requirements.txt reached production, or after the deploy's buildx
# cache was dropped (deploy.yml drops it above 12 GB). The hosted pytest job warns
# when requirements.txt no longer matches the hash recorded below.
#
# Usage (from the repo root):  .github/ci/refresh-constraints-from-prod.sh
set -euo pipefail

VPS="${VPS:-root@72.62.44.131}"
OUT=".github/ci/constraints-prod.txt"
REQ="backend/requirements.txt"
[ -f "$REQ" ] || { echo "run from the repo root" >&2; exit 1; }

freeze="$(ssh "$VPS" 'docker exec tg_backend pip freeze')"
pyver="$(ssh "$VPS" 'docker exec tg_backend python -V' | awk '{print $2}')"
grep -q '^torch==' <<<"$freeze" || { echo "no torch pin in the freeze — wrong container?" >&2; exit 1; }

{
  echo "# Production's resolved package set. .github/ci/lock-backend-deps.py turns it"
  echo "# into the hash locks (requirements-prod.lock / requirements-dev.lock) that the"
  echo "# image and the GitHub-hosted backend jobs install, so a pull request is tested"
  echo "# against exactly what the live container runs, not whatever PyPI resolves today."
  echo "#"
  echo "# backend/requirements.txt keeps its ranges: the deploy image resolves them at"
  echo "# build time and buildx caches that layer until requirements.txt changes — so any"
  echo "# byte change there (even a comment) re-resolves every package in the next"
  echo "# production image, and this file must then be regenerated after that deploy."
  echo "#"
  echo "# Source: \`pip freeze\` in tg_backend (Python ${pyver}), $(date -u +%Y-%m-%d)."
  echo "# Regenerate: .github/ci/refresh-constraints-from-prod.sh (read-only on prod)."
  echo "# requirements-sha256: $(sha256sum "$REQ" | cut -d' ' -f1)"
  echo "# python: ${pyver}"
  echo "$freeze"
} > "$OUT"
echo "wrote $OUT ($(grep -c '==' "$OUT") pins, Python ${pyver})"
echo "next: regenerate the hash locks — .github/ci/lock-backend-deps.py (see backend/DEPENDENCIES.md)"
