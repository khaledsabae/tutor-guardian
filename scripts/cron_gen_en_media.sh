#!/usr/bin/env bash
# Daily English media generation — video first, then audio with what is left.
#
#   scripts/cron_gen_en_media.sh
#
# Why one driver and not two agents
# ---------------------------------
# 🚨 This comment used to state as measured fact that the quota is ~24/day and
# shared across audio and video. It was neither. It was inferred from one
# afternoon (19 video + 5 audio, then RateLimit) and then written down without
# the inference, so every later decision treated it as a ceiling.
#
# 2026-08-15 disproved it: 60 generations were accepted in a single day —
# 20 video, and 20 audio twice, in separate runs. Whatever meters this, it is
# not a 24/day pool.
#
# What the numbers actually suggest is a per-RUN ceiling near 20, not a daily
# one: audio stopped at exactly 20 in both of its runs, and video was accepted
# for exactly 20 in its own. That is a hypothesis, not a measurement — it is
# settled by two consecutive audio-only runs on one day, which is why the agent
# was disabled for 2026-08-16 rather than left to blur the result again.
#
# So the reason for one driver is not a shared pool. It is that two agents on
# the same Google account rotate each other's cookies out (see below), and one
# driver makes the order deliberate rather than a race.
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
NOTEBOOK_MAIN="94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
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
# 🚨 Verified by EFFECT, not by the login command's exit code.
#
# On 2026-08-15 at 06:30 `login` exited 0 and printed "Cookies verified
# successfully" for both profiles — and every generate call that followed
# failed with "re-authenticate". The run produced nothing and PCC recorded it
# "ok", because the guard trusted a success message instead of asking the API
# a question. That is the failure this whole pipeline keeps producing, written
# into the guard meant to catch it.
#
# So: log in, then make a real read. If the read comes back with data, the
# session is alive. If not, stop — a run that cannot authenticate cannot
# generate, and should say so rather than spend an hour proving it.
# 🚨 And re-checked before EVERY step, not once at the top.
#
# Checking once was worth 124 failed calls on 2026-08-15 — every infographic
# call in the run, 344 errors, read at the time as a quota ceiling because a
# whole medium failing at once looks like one.
#
# ⚠️ CORRECTION to what e0fabcf's message says. That commit blamed session
# *age*: video up to 45 min, audio up to 45 more, so tg-video reached the
# infographic step ~80 minutes past a check it had passed. The fix is right and
# the reason was wrong, and the difference matters for anyone reasoning about
# this later.
#
# Measured directly on 2026-08-16, audio alone, nothing else running:
#
#   · session verified alive by a real read immediately before the run
#   · 20 generations accepted, then `rate-limited` on the 21st
#   · seconds later the same session was DEAD — a plain `source list` refused
#   · a fresh `login` recovered it instantly
#
# Recovered by login means killed, not expired. **Hitting the quota ceiling
# kills the session.** And because tg-video and tg-audio sit on the same Google
# account, the audio step's refusal takes tg-video down with it — the
# infographic step then finds a corpse, whatever its age. A run that never hit
# the ceiling would have been fine at 80 minutes.
#
# This also re-reads an older symptom: `no task id` was diagnosed on 08-15 as a
# dead session. True, but it is the second link in the chain, not the first —
# ceiling → session killed → every later call returns `no task id`. The two
# refusals are the same event seen before and after the kill, which is why the
# same lesson id appears under both wordings in the 08-16 logs.
#
# So re-authenticating before each step is not hygiene against drift; it is
# recovery from a kill that the previous step causes. Separate profiles still
# prevent the cookie rotation that killed the session three times on 08-14,
# but they were never going to prevent this: one account, one ceiling.
ensure_session() {
    local p="$1"
    timeout 90 ./notebooklm_env/bin/notebooklm -p "$p" login --browser-cookies chrome \
        >> "$LOG" 2>&1
    if timeout 90 ./notebooklm_env/bin/notebooklm -p "$p" source list \
            -n "$NOTEBOOK_MAIN" --json 2>/dev/null | grep -q '"sources"'; then
        say "auth $p verified by read ✓"
        return 0
    fi
    say "auth $p FAILED — login reported success but the API refuses reads"
    return 1
}

if ! ensure_session tg-video || ! ensure_session tg-audio; then
    say "FAIL: no usable session — nothing can be generated"
    exit 1
fi

# ── Harvest first — before anything can spend, or die ──
#
# 🚨 This runs FIRST, always, and it is not an optimisation.
#
# In-flight tasks are generations already charged against the quota, finished
# on Google's servers, waiting to be downloaded. Collecting them costs nothing.
# But polling shares a session with generating, and generating hits the ceiling,
# and hitting the ceiling KILLS the session (measured 2026-08-16). So a run that
# generates before it collects arrives at the download step with a dead session
# and returns "error" on every poll — losing, for free, work that was already
# paid for. That is exactly what happened this morning: 20 completed episodes,
# zero downloaded, exit 0.
#
# 18 episodes were lost outright on 2026-08-15 the same way. Order is the fix.
ensure_session tg-audio || say "WARN: tg-audio unusable before harvest"
timeout 1800 "$PY" scripts/gen_podcasts_cron.py --lang en --harvest-only \
    > "$RUN_OUT" 2>&1
cat "$RUN_OUT" >> "$LOG"
say "harvest exit $? · $(grep -c '✓ downloaded' "$RUN_OUT") downloaded, \
$(grep -oE '[0-9]+ still in flight' "$RUN_OUT" | head -1)"

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

# ── Audio — always attempted, even when video was refused ──
#
# Whether NotebookLM meters audio and video from one pool or from separate
# ones is NOT established. It was inferred from co-occurrence (19 video + 5
# audio on 2026-08-14, then a refusal) and never tested in isolation: a probe
# with video already refused found audio refused too, which fits one exhausted
# pool and two exhausted pools equally well.
#
# The design does not need that answer, because the costs are asymmetric:
#   · an attempt that is refused costs nothing — a refusal is not a generation
#   · skipping while capacity exists costs a whole day of that medium
# So attempt audio regardless. Under one shared pool this adds one cheap
# refused call; under separate pools it is the difference between finishing the
# audio backlog and never touching it once video reaches its ceiling.
#
# To settle it: run audio alone on a fresh day and count how many it gets
# before refusal. If it reaches roughly the video ceiling on its own, the
# pools are separate.
ensure_session tg-audio || say "WARN: tg-audio unusable — attempting anyway"
timeout 2700 "$PY" scripts/gen_podcasts_cron.py --lang en > "$RUN_OUT" 2>&1
AUD_EXIT=$?
cat "$RUN_OUT" >> "$LOG"
say "audio exit $AUD_EXIT (video refused: $RATELIMITED)"
grep -qi "rate.limit" "$RUN_OUT" && RATELIMITED=1

# ── Infographics ──
# Also attempted regardless, for the same asymmetry: a refusal is free.
#
# `generate infographic` DOES take --language, unlike `generate quiz` and
# `generate flashcards`, which take none and return English whatever the prompt
# says (OPERATIONS_LOG 2026-08-14). NOTEBOOKLM_HL is set anyway because it
# defaults to "en" only when unset — an inherited ar_001 from a shell that ran
# the Arabic pipeline would quietly produce Arabic into `_en` filenames.
# 🚨 tg-video has been idle through video AND audio by now — up to 80 minutes.
# This is the step that lost 124 calls to an expired session on 2026-08-15.
if ! ensure_session tg-video; then
    say "SKIP infographics: tg-video session is dead and re-login did not fix it"
    INFO_EXIT=99
else
    NOTEBOOKLM_HL=en timeout 2700 "$PY" scripts/generate_missing_infographics.py \
        --lang en > "$RUN_OUT" 2>&1
    INFO_EXIT=$?
    cat "$RUN_OUT" >> "$LOG"
    say "infographics [en] exit $INFO_EXIT"
    grep -qi "rate.limit" "$RUN_OUT" && RATELIMITED=1

    # The 14 Arabic gaps. The driver ran `--lang en` only, so these were never
    # attempted by anything — and they do not show up as missing in any English
    # count, which is why they sat unnoticed. Last, because English is the
    # backlog this driver exists for; Arabic is 14 files, not 124.
    if [ "$RATELIMITED" -eq 0 ]; then
        NOTEBOOKLM_HL=ar timeout 1200 "$PY" scripts/generate_missing_infographics.py \
            --lang ar > "$RUN_OUT" 2>&1
        cat "$RUN_OUT" >> "$LOG"
        say "infographics [ar] exit $?"
        grep -qi "rate.limit" "$RUN_OUT" && RATELIMITED=1
    fi
fi

# An infographic is text rendered into pixels: nothing in the filename, the
# index or the exit code knows what language is actually drawn inside it. OCR
# the new ones rather than let a wrong-language image reach review as if it
# were fine. Reported, not blocking — the run already produced the files.
timeout 900 "$PY" ops/tools/check_infographic_language.py --lang en >> "$LOG" 2>&1
say "infographic language check exit $?"

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

rsync -av --chmod=F644 \
    --include='*_infographic_*_en.png' --include='*/' --exclude='*' \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
    docs/lesson_assets/infographics/ \
    "$VPS:${VPS_DOCS}lesson_assets/infographics/" >> "$LOG" 2>&1
say "rsync infographics exit $?"

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
# Count what is BUILDABLE, not what exists. Only 80 of 174 lessons have an
# infographic prompt block in scripts/infographic_prompts.md; counting all of
# them leaves 94 permanently "remaining", so the total never reaches zero, the
# agent never self-retires, and the stall guard fires every day on work that
# was never possible.
from scripts.infographic_prompts_lib import buildable_targets
i = len(buildable_targets("en")[0])
print(f"{a+v+i} {a} {v} {i}")
PYEOF
)
say "remaining: ${REMAIN:-?} (total audio video infographic)"

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
