#!/usr/bin/env bash
# Render the «نور» teaser: three MP4s (H.264, CRF 18) and six key stills of
# the Arabic portrait cut. Generated inputs are rebuilt first — sounds (seeded,
# so the WAVs only change if their recipe does), the Play QR codes, and the
# real app logo cut to a circle.
#
#   scripts/render_noor_teaser.sh            # everything into out/
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/sync_app_art.sh
python3 scripts/gen_teaser_sfx.py
python3 scripts/gen_teaser_qr.py
python3 scripts/make_round_logo.py

# NoorTeaserArWorld: the Arabic cut with the new world (road + corner) cut in — TeaserWorld.tsx
for id in NoorTeaserAr NoorTeaserEn NoorTeaserArWide NoorTeaserArWorld; do
	name=$(echo "$id" | sed -E 's/NoorTeaser//; s/([A-Z])/_\L\1/g; s/^_//')
	npx remotion render src/Root.tsx "$id" "out/noor_teaser_${name}.mp4" \
		--codec=h264 --crf=18 --concurrency=8 --log=error
done

mkdir -p out/stills
for spec in 1_peek:118 2_happy:222 3_lanterns:342 4_ask:410 5_answer:462 6_endcard:690; do
	npx remotion still src/Root.tsx NoorTeaserAr "out/stills/noor_teaser_ar_${spec%%:*}_f${spec##*:}.png" \
		--frame="${spec##*:}" --log=error
done
ls -la out/*.mp4 out/stills/
