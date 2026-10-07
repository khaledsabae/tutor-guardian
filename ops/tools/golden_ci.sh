#!/usr/bin/env bash
# Hosted candidate only. No .env, production volume, or provider credential.
set -euo pipefail
image="${1:?usage: golden_ci.sh IMAGE OUTPUT_DIR}"
output="${2:?output directory required}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
# The isolated runner's mounted output must be writable by image UID 10001.
chmod 777 "$output"
name="tg-golden-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
code=0
timeout --signal=TERM 10m docker run --rm --name "$name" \
  --network none --cpus 2 --memory 4g --cap-drop ALL --security-opt no-new-privileges \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e ANONYMIZED_TELEMETRY=False \
  -e GOLDEN_REVISION="${GITHUB_SHA:-unknown}" \
  --mount "type=bind,source=$PWD/ops/eval/golden_set.jsonl,target=/golden.jsonl,readonly" \
  --mount "type=bind,source=$output,target=/report" \
  "$image" python ops/tools/golden_ci.py --set /golden.jsonl --out /report || code=$?
if [ ! -s "$output/report.json" ]; then
  python3 ops/tools/golden_ci.py --set ops/eval/golden_set.jsonl --out "$output" \
    --unavailable "Candidate runtime did not complete (exit $code)" || true
fi
exit "$code"
