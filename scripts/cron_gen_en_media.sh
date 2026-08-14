#!/usr/bin/env bash
# Daily English media generation — video first, then audio with what is left.
#
#   scripts/cron_gen_en_media.sh
#
# Why one driver and not two agents
# ---------------------------------
# The NotebookLM quota is ~24 generations/day and it is **shared across audio
# and video** — measured 2026-08-14: 19 video + 5 audio, then RateLimit. Two
# agents running blind would race for the same pool and neither would finish.
# One driver spends it in a deliberate order.
#
# Video first because it is nearly done: 20 paths remain against 172 lessons,
# so video clears in about a day and audio then gets the whole budget every
# day after. Finishing one medium beats half-finishing both.
#
# Each generator stops itself on the first RateLimit — that is the design, not
# a fault. If video hits it, audio is skipped rather than run to burn a second
# refusal.
set -u
umask 022
REPO="/home/khalednew/projects/tutor-guardian"
LOG="/tmp/gen_en_media.log"
VPS="root@72.62.44.131"
VPS_DOCS="/root/tutor-guardian/docs/"
export HOME="/home/khalednew"
export PYTHONUNBUFFERED=1
cd "$REPO" || exit 1
PY="$REPO/backend/.venv/bin/python"
[ -x "$PY" ] || PY="/usr/bin/python3"

say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
say "===== English media run ====="

# Each generator authenticates its own profile (tg-video / tg-audio). One
# profile shared by two processes rotates cookies out from under the other —
# the session died three times on 2026-08-14 that way.
AUTH_FAILED=0
for p in tg-video tg-audio; do
    timeout 90 ./notebooklm_env/bin/notebooklm -p "$p" login --browser-cookies chrome \
        >> "$LOG" 2>&1
    rc=$?
    say "auth $p exit $rc"
    [ "$rc" -ne 0 ] && AUTH_FAILED=1
done
if [ "$AUTH_FAILED" -ne 0 ]; then
    say "FAIL: could not authenticate — nothing can be generated"
    exit 1
fi

# ── Video ──
# 🚨 This run's output only, never "$LOG".
# The log accumulates across runs, so `grep rate.limit "$LOG"` would match the
# FIRST rate limit ever recorded and go on matching it forever — audio skipped
# every day after, and the stall guard below permanently excused by a refusal
# that happened weeks ago. Exactly the class of always-true signal this whole
# pipeline kept tripping over.
RUN_OUT=$(mktemp)
trap 'rm -f "$RUN_OUT"' EXIT
timeout 2700 "$PY" scripts/gen_path_videos_cron.py --lang en > "$RUN_OUT" 2>&1
VID_EXIT=$?
cat "$RUN_OUT" >> "$LOG"
say "video exit $VID_EXIT"
RATELIMITED=0
grep -qi "rate.limit" "$RUN_OUT" && RATELIMITED=1

# ── Audio, only if the pool is not already spent ──
if [ "$RATELIMITED" -eq 0 ]; then
    timeout 2700 "$PY" scripts/gen_podcasts_cron.py --lang en > "$RUN_OUT" 2>&1
    AUD_EXIT=$?
    cat "$RUN_OUT" >> "$LOG"
    say "audio exit $AUD_EXIT"
    grep -qi "rate.limit" "$RUN_OUT" && RATELIMITED=1
else
    say "audio skipped — quota already spent by video this run"
fi

# ── Publish ──
# Media never reaches production through the deploy; it is gitignored and
# arrives only by rsync. --chmod=F644 is load-bearing: the CLI writes 0600 and
# the container runs as uid 10001 against a host bind mount, which is the
# 2026-07-27 outage.
rsync -av --chmod=F644 --min-size=2097152 \
    --include='*_podcast_en.mp3' --include='*/' --exclude='*' \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
    docs/ "$VPS:$VPS_DOCS" >> "$LOG" 2>&1
say "rsync audio exit $?"

rsync -av --chmod=F644 --min-size=5242880 \
    --include='*_en_us.mp4' --include='*/' --exclude='*' \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
    docs/path_videos/ "$VPS:${VPS_DOCS}path_videos/" >> "$LOG" 2>&1
say "rsync video exit $?"

# ── Report coverage, and retire when there is nothing left ──
REMAIN=$("$PY" - <<'PYEOF' 2>/dev/null
import json, os, sys
sys.path.insert(0, "backend")
from app.media_naming import (MIN_PODCAST_BYTES, MIN_VIDEO_BYTES,
                              path_video_rel, podcast_rel)
def have(rel, floor):
    return os.path.exists(rel) and os.path.getsize(rel) > floor
lids = [v[2] for v in json.load(open("source_to_lesson.json")).values()
        if isinstance(v, list) and len(v) >= 3]
pids = [t["path_id"] for t in json.load(open("scratch/path_source_mapping_new.json"))]
a = sum(1 for x in lids if not have(podcast_rel(x, "en"), MIN_PODCAST_BYTES))
v = sum(1 for x in pids if not have(path_video_rel(x, "en"), MIN_VIDEO_BYTES))
print(f"{a+v} {a} {v}")
PYEOF
)
say "remaining: ${REMAIN:-?} (total audio video)"

# 🚨 exit 0 must not mean "ran"; it must mean "worked, or had a reason not to".
#
# This is the failure this whole pipeline kept producing: a cron calling a file
# that no longer existed, a generator printing "no task id" on a stale source, a
# duration gate that silently degraded to a size check. Every one exited 0 and
# every one produced nothing for weeks. An agent whose success signal is its own
# exit code inherits that.
#
# So: a run that generated nothing is fine when the quota refused it — that is
# the design. A run that generated nothing for three consecutive runs with no
# refusal to explain it is broken, and PCC should say so.
TOTAL="${REMAIN%% *}"
STALL_FILE="$REPO/scratch/en_media_progress.json"
"$PY" - "$TOTAL" "$RATELIMITED" "$STALL_FILE" <<'PYEOF'
import json, os, sys
total, ratelimited, path = sys.argv[1], sys.argv[2] == "1", sys.argv[3]
state = {}
if os.path.exists(path):
    try:
        state = json.load(open(path))
    except Exception:
        state = {}
same = 0 if (state.get("remaining") != total or ratelimited) else state.get("stalled", 0) + 1
json.dump({"remaining": total, "stalled": same}, open(path, "w"))
sys.exit(1 if same >= 3 else 0)
PYEOF
STALLED=$?
if [ "$STALLED" -ne 0 ]; then
    say "FAIL: three runs with no progress and no rate limit — something is broken, not throttled"
    exit 1
fi

# Self-retire the same way the Arabic agents did, but through PCC rather than
# by editing the crontab — the crontab is PCC-managed and hand edits are
# forbidden (see ~/projects/CLAUDE.md).
if [ "${REMAIN%% *}" = "0" ]; then
    say "all English media present — disabling agent"
    /home/khalednew/projects/publishing-center/bin/pcc disable tutor_en_media \
        --reason "English media complete" >> "$LOG" 2>&1
fi
