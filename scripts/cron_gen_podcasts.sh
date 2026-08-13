#!/usr/bin/env bash
# Periodic NotebookLM podcast generation, one language per invocation.
#
#   scripts/cron_gen_podcasts.sh          # Arabic (default)
#   scripts/cron_gen_podcasts.sh en       # English
#
# Idempotent (the generator skips lessons that already own a podcast IN THAT
# LANGUAGE) + never infinite-loops on the daily quota, so cron drains the
# backlog over a few days. Refreshes auth each run, rsyncs finished podcasts to
# the VPS, and self-removes its crontab line once all are present.
#
# 🚨 This wrapper spent weeks calling `scripts/gen_podcasts_cron.py` after
# b704d67 moved that file to `scripts/archive/`. `set -u` is not `set -e`, so
# python exited 2, the log recorded `gen exit 2`, and the rsync and self-disable
# blocks ran regardless — a cron that looked healthy and generated nothing. The
# generator is back at the path below; keep them in step.
set -u
# Generators create media 0600. The container runs as uid 10001 and docs/ is a
# host bind mount, so 0600 files are unreadable in production — that is the
# 2026-07-27 outage. umask fixes what this script creates; --chmod fixes what
# lands on the VPS regardless of the local mode.
umask 022
LANG_CODE="${1:-ar}"
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/gen_podcasts_cron_${LANG_CODE}.log"
VPS="root@72.62.44.131"
VPS_DOCS="/root/tutor-guardian/docs/"
export HOME="/home/khalednew"
export PYTHONUNBUFFERED=1
cd "$REPO" || exit 1

PY="$REPO/backend/.venv/bin/python"

# Arabic files carry no tag; every other language does. Kept in step with
# PODCAST_TAG in backend/app/media_naming.py.
if [ "$LANG_CODE" = "ar" ]; then
    RSYNC_GLOB='*_podcast.mp3'
else
    RSYNC_GLOB="*_podcast_${LANG_CODE}.mp3"
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') podcast run (lang=$LANG_CODE) =====" >> "$LOG"
timeout 60 ./notebooklm_env/bin/notebooklm login --browser-cookies chrome >> "$LOG" 2>&1
echo "----- auth refresh exit $? -----" >> "$LOG"

timeout 1800 "$PY" scripts/gen_podcasts_cron.py --lang "$LANG_CODE" >> "$LOG" 2>&1
GEN_EXIT=$?
echo "----- gen exit $GEN_EXIT -----" >> "$LOG"
# A missing or crashing generator must not look like a completed run. Skipping
# the rsync and the self-disable is what makes the failure visible instead of
# leaving a healthy-looking log behind.
if [ "$GEN_EXIT" -ne 0 ]; then
    echo "generator failed — skipping rsync and self-disable." >> "$LOG"
    exit "$GEN_EXIT"
fi

# Push finished podcasts to the VPS (static bind-mount = no restart).
# --min-size matches MIN_PODCAST_BYTES (2 MB): the old 512000 let through
# half-written artifacts that the generator itself would have rejected.
rsync -av --chmod=F644 --min-size=2097152 --include="$RSYNC_GLOB" --exclude='*' \
    -e "ssh -i /home/khalednew/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=15" \
    docs/ "$VPS:$VPS_DOCS" >> "$LOG" 2>&1
echo "----- rsync exit $? -----" >> "$LOG"

# Self-disable once every lesson has a podcast in THIS language.
NEED=$("$PY" -c "
import json, os, sys
sys.path.insert(0, 'backend')
from app.media_naming import podcast_rel, MIN_PODCAST_BYTES
lang = '$LANG_CODE'
m = json.load(open('source_to_lesson.json'))
lids = [v[2] for v in m.values() if isinstance(v, list) and len(v) >= 3]
miss = [l for l in lids
        if not (os.path.exists(podcast_rel(l, lang))
                and os.path.getsize(podcast_rel(l, lang)) > MIN_PODCAST_BYTES)]
print(len(miss))
" 2>/dev/null)
echo "----- remaining ($LANG_CODE): ${NEED:-?} -----" >> "$LOG"
if [ "${NEED:-1}" = "0" ]; then
    # Remove only THIS language's line. The Arabic line predates the argument
    # and so carries none — a plain `grep -v cron_gen_podcasts.sh` would take
    # the English line down with it, and `grep -v "...sh ar"` would match
    # neither. Match the bare form only for Arabic.
    if [ "$LANG_CODE" = "ar" ]; then
        PAT='cron_gen_podcasts\.sh([[:space:]]+ar)?[[:space:]]*(>|$)'
    else
        PAT="cron_gen_podcasts\.sh[[:space:]]+${LANG_CODE}([[:space:]]|$)"
    fi
    echo "All $LANG_CODE podcasts done — removing cron line (/$PAT/)." >> "$LOG"
    crontab -l 2>/dev/null | grep -vE "$PAT" | crontab -
fi
