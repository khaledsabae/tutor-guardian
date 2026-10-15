#!/usr/bin/env bash
# Copy the app's own «ورق مقصوص» art (mobile/assets/svg/stories + noor) into
# public/noor/app/, so the reels draw the very pieces the app draws — the
# story scenes, the props and Noor's faces — instead of redrawn look-alikes.
# The copy is not committed (public/noor/app/ is git-ignored): the app's
# assets are the one source, and every render script runs this first.
#
#   scripts/sync_app_art.sh
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=../mobile/assets/svg
DST=public/noor/app
mkdir -p "$DST/stories" "$DST/noor"
cp "$SRC"/stories/*.svg "$DST/stories/"
cp "$SRC"/noor/*.svg "$DST/noor/"
echo "app art: $(ls "$DST/stories" | wc -l) story pieces, $(ls "$DST/noor" | wc -l) Noor faces"
