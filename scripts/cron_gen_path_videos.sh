#!/usr/bin/env bash
# Periodic NotebookLM path-video generation for the 12 new paths, until done.
# Idempotent: gen_path_videos_cron.py skips paths whose mp4 already exists, and
# never infinite-loops on the daily quota — so running this every few hours
# drains the backlog over ~3 days. rsyncs newly-finished videos to the VPS
# (static bind-mount = no restart). Self-removes its own crontab line once all
# 12 videos exist. Safe to leave scheduled.
set -u
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/gen_path_videos_cron.log"
VPS="root@72.62.44.131"
VPS_DOCS="/root/tutor-guardian/docs/"
export HOME="/home/khalednew"
export PYTHONUNBUFFERED=1
cd "$REPO" || exit 1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') path-video run =====" >> "$LOG"
# Refresh NotebookLM auth each run (the session expires every few hours; without
# this the poll/download calls fail silently and the backlog never drains).
timeout 60 ./notebooklm_env/bin/notebooklm login --browser-cookies chrome >> "$LOG" 2>&1
echo "----- auth refresh exit $? -----" >> "$LOG"

# Bound each run so a stuck poll never wedges the slot; next cron resumes.
timeout 1800 "$REPO/backend/.venv/bin/python" scripts/gen_path_videos_cron.py >> "$LOG" 2>&1
echo "----- gen exit $? -----" >> "$LOG"

# Push finished videos (>5MB) to the VPS — rsync only transfers the new ones.
rsync -av --min-size=5242880 --include='*_ar_eg.mp4' --include='*/' --exclude='*' \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
    docs/path_videos/ "$VPS:${VPS_DOCS}path_videos/" >> "$LOG" 2>&1
echo "----- rsync exit $? -----" >> "$LOG"

# Self-disable once every mapped path has a video.
NEED=$(python3 -c "
import json,os
m=json.load(open('scratch/path_source_mapping_new.json'))
miss=[t['path_id'] for t in m if not (os.path.exists(f\"docs/path_videos/{t['path_id']}_ar_eg.mp4\") and os.path.getsize(f\"docs/path_videos/{t['path_id']}_ar_eg.mp4\")>5*1024*1024)]
print(len(miss))
" 2>/dev/null)
echo "----- remaining: ${NEED:-?} -----" >> "$LOG"
if [ "${NEED:-1}" = "0" ]; then
    echo "All path videos done — removing cron line." >> "$LOG"
    crontab -l 2>/dev/null | grep -v 'cron_gen_path_videos.sh' | crontab -
fi
