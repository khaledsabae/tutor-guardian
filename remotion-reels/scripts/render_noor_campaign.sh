#!/usr/bin/env bash
# Render the six «المربّي» campaign reels (1080×1920, H.264, 30 fps), one
# cover still per reel, a contact sheet pulled from the MP4s, and a loudness
# report (ffmpeg ebur128: integrated LUFS and true peak, target about
# -23 LUFS with peaks at or below -3 dBFS). Generated inputs are rebuilt
# first: the sounds (seeded), the Play QR codes, the round app logo.
#
#   scripts/render_noor_campaign.sh            # everything into out/campaign/
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/sync_app_art.sh
python3 scripts/gen_teaser_sfx.py
python3 scripts/gen_teaser_qr.py
python3 scripts/make_round_logo.py

OUT=out/campaign
mkdir -p "$OUT"

# composition : file name : cover frame (the strongest still for a thumbnail)
REELS=(
	"CampaignV1Remember:v1_remember:28"
	"CampaignV2Road:v2_road:250"
	"CampaignV3Ask:v3_ask:250"
	"CampaignV4Handover:v4_handover:170"
	"CampaignV5Ramadan:v5_ramadan:436"
	"CampaignV6Stories:v6_stories:200"
)

for spec in "${REELS[@]}"; do
	IFS=: read -r id name cover <<<"$spec"
	npx remotion render src/Root.tsx "$id" "$OUT/$name.mp4" --codec=h264 --crf=18 --concurrency=8 --log=error
	npx remotion still src/Root.tsx "$id" "$OUT/${name}_cover.png" --frame="$cover" --log=error
done

python3 scripts/make_campaign_sheet.py "$OUT/contact_sheet.png" "$OUT" \
	v1_remember:1.0,2.0,6.3,8.6,11.8,17.5 \
	v2_road:1.3,4.4,5.6,9.0,10.8,14.2 \
	v3_ask:0.9,2.6,6.6,9.7,11.8,17.5 \
	v4_handover:0.8,3.8,6.2,7.8,10.0,13.8 \
	v5_ramadan:1.2,4.0,7.2,12.5,14.6,18.5 \
	v6_stories:1.2,3.4,6.8,9.6,13.8,19.0

for spec in "${REELS[@]}"; do
	IFS=: read -r _ name _ <<<"$spec"
	f="$OUT/$name.mp4"
	stats=$(ffmpeg -nostats -i "$f" -filter_complex ebur128=peak=true:framelog=quiet -f null - 2>&1 | sed -n '/Summary/,$p')
	lufs=$(awk '/I:/ {print $2}' <<<"$stats")
	peak=$(awk '/Peak:/ {print $2}' <<<"$stats")
	dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
	printf '%-14s %6.2f s  %5.1f MB  %6s LUFS  peak %5s dBFS\n' "$name" "$dur" "$(echo "$(stat -c %s "$f") / 1048576" | bc -l)" "$lufs" "$peak"
done
