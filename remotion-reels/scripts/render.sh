#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PATH_ID="${1:-}"
if [ -n "$PATH_ID" ]; then
  python3 scripts/make_reel_data.py "$PATH_ID"
else
  python3 scripts/make_reel_data.py
fi
mkdir -p out
npx remotion render src/Root.tsx Reel "out/reel_${PATH_ID:-sample}.mp4" --concurrency=1 --log=info
