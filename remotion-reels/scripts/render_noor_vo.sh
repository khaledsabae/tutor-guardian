#!/usr/bin/env bash
# Render the voice-over cuts (`_vo`): the Arabic teaser and the six campaign
# reels, with the narrator on top of the soft generated sounds (no music).
# scripts/gen_vo.py only calls TTS for a line whose text/voice changed (the
# checked takes are committed under public/noor/vo/); it also re-plans the
# timing into src/noor/campaign/vo_lines.ts. Ends with a loudness report
# (target: -16…-18 LUFS integrated, true peak <= -1.5 dBFS).
#
#   scripts/render_noor_vo.sh            # into out/vo/
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/sync_app_art.sh
python3 scripts/gen_vo.py  # stops (exit 2) on a 429 and lists the lines still to record
OUT=out/vo
mkdir -p "$OUT"
for spec in NoorTeaserArVo:noor_teaser_ar_vo CampaignV1RememberVo:v1_remember_vo CampaignV2RoadVo:v2_road_vo \
	CampaignV3AskVo:v3_ask_vo CampaignV4HandoverVo:v4_handover_vo CampaignV5RamadanVo:v5_ramadan_vo CampaignV6StoriesVo:v6_stories_vo; do
	npx remotion render src/Root.tsx "${spec%%:*}" "$OUT/${spec##*:}.mp4" --codec=h264 --crf=18 --concurrency=8 --log=error
done
for f in "$OUT"/*.mp4; do
	stats=$(ffmpeg -nostats -i "$f" -filter_complex ebur128=peak=true:framelog=quiet -f null - 2>&1 | sed -n '/Summary/,$p')
	printf '%-24s %6.2f s  %5.1f MB  %6s LUFS  peak %5s dBFS\n' "$(basename "$f" .mp4)" \
		"$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")" "$(echo "$(stat -c %s "$f") / 1048576" | bc -l)" \
		"$(awk '/I:/ {print $2}' <<<"$stats")" "$(awk '/Peak:/ {print $2}' <<<"$stats")"
done
