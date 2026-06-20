#!/usr/bin/env bash
# Periodic NotebookLM podcast generation for the 48 new lessons, until done.
# Idempotent (gen_podcasts_cron.py skips existing *_podcast.mp3) + never
# infinite-loops on the daily quota, so cron drains the backlog over a few days.
# Refreshes auth each run, rsyncs finished podcasts to the VPS, and self-removes
# its crontab line once all are present.
set -u
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/gen_podcasts_cron.log"
VPS="root@72.62.44.131"
VPS_DOCS="/root/tutor-guardian/docs/"
export HOME="/home/khalednew"
export PYTHONUNBUFFERED=1
cd "$REPO" || exit 1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') podcast run =====" >> "$LOG"
timeout 60 ./notebooklm_env/bin/notebooklm login --browser-cookies chrome >> "$LOG" 2>&1
echo "----- auth refresh exit $? -----" >> "$LOG"

timeout 1800 "$REPO/backend/.venv/bin/python" scripts/gen_podcasts_cron.py >> "$LOG" 2>&1
echo "----- gen exit $? -----" >> "$LOG"

# Push finished podcasts (>=500KB) to the VPS (static bind-mount = no restart).
rsync -av --min-size=512000 --include='*_podcast.mp3' --exclude='*' \
    -e "ssh -i /home/khalednew/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=15" \
    docs/ "$VPS:$VPS_DOCS" >> "$LOG" 2>&1
echo "----- rsync exit $? -----" >> "$LOG"

# Self-disable once every new-lesson podcast exists.
NEED=$(/home/khalednew/projects/tutor-guardian/backend/.venv/bin/python -c "
import json,os
m=json.load(open('source_to_lesson.json'))
lids=[v[2] for v in m.values() if isinstance(v,list) and len(v)>=3]
miss=[l for l in lids if not (os.path.exists(f'docs/{l}_podcast.mp3') and os.path.getsize(f'docs/{l}_podcast.mp3')>500*1024)]
print(len(miss))
" 2>/dev/null)
echo "----- remaining: ${NEED:-?} -----" >> "$LOG"
if [ "${NEED:-1}" = "0" ]; then
    echo "All new-lesson podcasts done — removing cron line." >> "$LOG"
    crontab -l 2>/dev/null | grep -v 'cron_gen_podcasts.sh' | crontab -
fi
