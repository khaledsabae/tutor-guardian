#!/usr/bin/env bash
# Daily retry of NotebookLM podcast regeneration until all 53 placeholder
# podcasts are replaced by real episodes. Idempotent: regen_podcasts.py skips
# any file already >=2MB, so once everything is real this run is a no-op.
# Google's daily audio quota means each run only completes a few; over several
# days it drains the backlog. Safe to leave scheduled — remove the crontab line
# when validate_podcasts.py reports 0 bad.
set -u
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/regen_podcasts_cron.log"
cd "$REPO" || exit 1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') regen run =====" >> "$LOG"
python3 scripts/regen_podcasts.py >> "$LOG" 2>&1
echo "----- exit $? -----" >> "$LOG"
