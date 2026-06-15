#!/usr/bin/env bash
# Daily retry of NotebookLM podcast regeneration until all 53 placeholder
# podcasts are replaced by real episodes. Idempotent: regen_podcasts.py skips
# any file already >=2MB, so once everything is real this run is a no-op.
# Google's daily audio quota means each run only completes a few; over several
# days it drains the backlog. After regen, it rsyncs the newly-real episodes to
# the VPS (idempotent, static bind-mount = no restart). Safe to leave scheduled
# — remove the crontab line when validate_podcasts.py reports 0 bad.
set -u
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/regen_podcasts_cron.log"
cd "$REPO" || exit 1
VPS="root@72.62.44.131"
VPS_DOCS="/root/tutor-guardian/docs/"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') regen run =====" >> "$LOG"
python3 scripts/regen_podcasts.py >> "$LOG" 2>&1
echo "----- regen exit $? -----" >> "$LOG"

# Deploy: push only newly-real podcasts (>=2MB) to the VPS. rsync transfers just
# the ones the VPS lacks; static bind-mount means the app serves them with no
# restart. No-op once everything is already in sync.
echo "----- rsync to VPS $(date '+%H:%M:%S') -----" >> "$LOG"
rsync -av --min-size=2097152 --include='*_podcast.mp3' --exclude='*' \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
    docs/ "$VPS:$VPS_DOCS" >> "$LOG" 2>&1
echo "----- rsync exit $? -----" >> "$LOG"
