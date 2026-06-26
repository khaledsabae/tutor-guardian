#!/usr/bin/env bash
# Resumable infographics batch driver (cron-friendly).
# Each run: registers any PNGs already on disk, generates more until NotebookLM
# rate-limits, then commits+pushes the index. Self-disables once 0 lessons remain.
set -uo pipefail

REPO="/home/khalednew/projects/tutor-guardian"
PY="$REPO/notebooklm_env/bin/python"
LOG="$REPO/logs/infographics_cron.log"
TAG="resume_infographics_cron.sh"

cd "$REPO" || exit 1
mkdir -p "$REPO/logs"
echo "===== $(date '+%F %T') resume run =====" >> "$LOG"

missing=$("$PY" - <<'EOF'
import sys; sys.path.insert(0, "scripts")
from generate_missing_infographics import missing_infographic_lessons as m
print(len(m()))
EOF
)

if [ "${missing:-1}" = "0" ]; then
  echo "All infographics done — removing cron." >> "$LOG"
  crontab -l 2>/dev/null | grep -v "$TAG" | crontab -
  exit 0
fi

echo "missing=$missing — running generator" >> "$LOG"
"$PY" -u scripts/generate_missing_infographics.py --delay 4 >> "$LOG" 2>&1
echo "----- run end $(date '+%F %T') -----" >> "$LOG"
