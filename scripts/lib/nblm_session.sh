# shellcheck shell=bash
# NotebookLM session guard for the English media pipeline.
#
#   source scripts/lib/nblm_session.sh
#   ensure_session tg-video || …
#
# Sourced by scripts/cron_gen_en_media.sh (and by its tests). The caller may
# define `say` and `LOG`; fallbacks are provided so the library stands alone.
#
# 🚨 Why this exists: the Chrome fallback used to run
#     notebooklm -p <profile> login --browser-cookies chrome
# straight into the LIVE profile. notebooklm-py 0.8.0 writes storage_state.json
# BEFORE it verifies the cookies (cli/services/login/refresh.py — the
# `atomic_write_json` call precedes `fetch_tokens_with_domains`) and on a failed
# verification it only prints "Saved anyway". So when Chrome itself was signed
# out, a dead extraction overwrote the only good session — twice on 2026-09-29
# (morning, and again at 09:15) — and there was no backup to go back to.
#
# The rule now: nothing touches the live file unless it has been proven by a
# real read first.
#   · the Chrome extraction lands in a CANDIDATE profile (`<profile>.candidate`)
#   · the candidate is validated with the same read the live session gets
#   · only a valid candidate is promoted: the live file is backed up to
#     storage_state.json.bak-<UTC timestamp>, then the candidate is `mv`-ed over
#     it (same directory tree → an atomic rename)
#   · an invalid candidate is deleted and the live file stays byte-identical
#   · every successful live validation refreshes storage_state.json.lastgood,
#     which is tried (again via a candidate) when both live and Chrome fail
#   · a live session that already validated earlier in THIS run is never
#     replaced — a later refusal is a quota kill or a hiccup, and swapping in
#     whatever Chrome holds is exactly how the good session was lost
#
# Path resolution (notebooklm/paths.py): `-p <name>` → get_storage_path(name) →
# ${NOTEBOOKLM_HOME:-~/.notebooklm}/profiles/<name>/storage_state.json. Names
# containing a dot are fine; only names escaping profiles/ are rejected. The
# account metadata the login writes lives in-band inside storage_state.json, so
# swapping that one file carries the whole session.

: "${LOG:=/dev/null}"
if ! declare -F say >/dev/null 2>&1; then
    say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
fi

NBLM_BIN="${NBLM_BIN:-./notebooklm_env/bin/notebooklm}"
NBLM_READ_TIMEOUT="${NBLM_READ_TIMEOUT:-90}"
# Multiplies every retry sleep; the tests set it to 0.
NBLM_SLEEP_SCALE="${NBLM_SLEEP_SCALE:-1}"
NBLM_KEEP_BACKUPS="${NBLM_KEEP_BACKUPS:-5}"
# Profiles whose live session validated earlier in this run (space-separated).
NBLM_VALIDATED_THIS_RUN="${NBLM_VALIDATED_THIS_RUN:-}"

nblm_profiles_dir() {
    if [ -n "${NOTEBOOKLM_HOME:-}" ]; then
        echo "$NOTEBOOKLM_HOME/profiles"
    else
        echo "$HOME/.notebooklm/profiles"
    fi
}

nblm_storage() { echo "$(nblm_profiles_dir)/$1/storage_state.json"; }

nblm_sleep() { sleep $(( $1 * NBLM_SLEEP_SCALE )); }

# One real read. The only definition of "alive" in this pipeline.
nblm_read_ok() {
    timeout "$NBLM_READ_TIMEOUT" "$NBLM_BIN" -p "$1" source list \
        -n "$NOTEBOOK_MAIN" --json 2>/dev/null | grep -q '"sources"'
}

# Three reads across a minute; one transient 502 is not a dead session
# (2026-08-18). $2 is the success wording, $3 = "quiet" suppresses per-attempt
# failure lines (the first pass over the live file is expected to fail
# sometimes and the summary line says so).
nblm_validate() {
    local p="$1" what="$2" mode="${3:-}" attempt
    for attempt in 1 2 3; do
        if nblm_read_ok "$p"; then
            if [ "$attempt" -gt 1 ]; then
                say "auth $what ✓ (attempt $attempt)"
            else
                say "auth $what ✓"
            fi
            return 0
        fi
        [ "$mode" = quiet ] || say "auth $p read failed (attempt $attempt/3)"
        if [ "$attempt" -lt 3 ]; then
            if [ "$mode" = quiet ]; then nblm_sleep 15; else nblm_sleep $((attempt * 20)); fi
        fi
    done
    return 1
}

nblm_mark_validated() {
    case " $NBLM_VALIDATED_THIS_RUN " in
        *" $1 "*) ;;
        *) NBLM_VALIDATED_THIS_RUN="${NBLM_VALIDATED_THIS_RUN:+$NBLM_VALIDATED_THIS_RUN }$1" ;;
    esac
}

nblm_validated_this_run() {
    case " $NBLM_VALIDATED_THIS_RUN " in *" $1 "*) return 0 ;; esac
    return 1
}

# Copy the live file to .lastgood via temp + mv, so a crash mid-copy can never
# leave a truncated "last good" behind.
nblm_refresh_lastgood() {
    local live tmp
    live="$(nblm_storage "$1")"
    [ -f "$live" ] || return 0
    tmp="$live.lastgood.tmp.$$"
    if cp -- "$live" "$tmp" && chmod 600 "$tmp" && mv -f -- "$tmp" "$live.lastgood"; then
        return 0
    fi
    rm -f -- "$tmp"
    say "WARN: could not refresh $1 lastgood"
    return 1
}

# Keep the newest $NBLM_KEEP_BACKUPS automatic backups. Only files matching the
# automatic pattern (bak-YYYYmmddTHHMMSSZ…) are rotated: a hand-made backup
# such as storage_state.json.bak-20260929 is never deleted by a cron job.
nblm_rotate_backups() {
    local dir="$1" n i
    local -a baks=()
    shopt -s nullglob
    baks=("$dir"/storage_state.json.bak-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z*)
    shopt -u nullglob
    n=${#baks[@]}
    # Glob expansion is sorted, and the UTC timestamp sorts chronologically.
    for (( i = 0; i < n - NBLM_KEEP_BACKUPS; i++ )); do
        rm -f -- "${baks[$i]}"
    done
}

# Promote a VALIDATED candidate profile over the live one.
nblm_promote() {
    local p="$1" cand="$2" live cand_file dir bak
    live="$(nblm_storage "$p")"
    cand_file="$(nblm_storage "$cand")"
    dir="$(dirname "$live")"
    mkdir -p "$dir" && chmod 700 "$dir"
    if [ -f "$live" ]; then
        bak="$live.bak-$(date -u +%Y%m%dT%H%M%SZ)"
        [ -e "$bak" ] && bak="$bak-$$-$RANDOM"
        if ! cp -p -- "$live" "$bak"; then
            say "auth $p: backup of live session FAILED — not replacing it"
            rm -rf -- "$(dirname "$cand_file")"
            return 1
        fi
        chmod 600 "$bak"
    fi
    chmod 600 "$cand_file"
    if ! mv -f -- "$cand_file" "$live"; then
        say "auth $p: promoting candidate FAILED — live file left as it was"
        rm -rf -- "$(dirname "$cand_file")"
        return 1
    fi
    rm -rf -- "$(dirname "$cand_file")"
    nblm_rotate_backups "$dir"
    say "auth $p: live session replaced by validated candidate${bak:+ (previous kept as $(basename "$bak"))}"
    return 0
}

ensure_session() {
    local p="$1" cand cand_dir lastgood
    # 2026-09-29: try the EXISTING state file first — the unconditional
    # `login --browser-cookies chrome` used to run before any read, and when
    # Chrome itself is signed out it extracts 206 stale cookies and OVERWRITES
    # a still-valid stored session with a dead one (measured this morning:
    # valid 45-cookie file restored by hand, then login smeared 206 stale
    # cookies over it and three reads refused → whole run aborted).
    if nblm_validate "$p" "$p verified by existing state" quiet; then
        nblm_mark_validated "$p"
        nblm_refresh_lastgood "$p"
        return 0
    fi

    if nblm_validated_this_run "$p"; then
        say "auth $p: session validated earlier this run now refused 3x — NOT replacing it (quota kill or hiccup; live file and lastgood untouched)"
        return 1
    fi

    cand="$p.candidate"
    cand_dir="$(dirname "$(nblm_storage "$cand")")"

    # Only now re-extract from Chrome — into the candidate, never the live file.
    say "auth $p: existing state refused 3x — extracting chrome cookies into candidate $cand"
    rm -rf -- "$cand_dir"
    timeout "$NBLM_READ_TIMEOUT" "$NBLM_BIN" -p "$cand" login --browser-cookies chrome \
        >> "$LOG" 2>&1
    if [ -f "$(nblm_storage "$cand")" ] \
            && nblm_validate "$cand" "$p chrome candidate verified by read"; then
        if nblm_promote "$p" "$cand"; then
            nblm_mark_validated "$p"
            nblm_refresh_lastgood "$p"
            return 0
        fi
    else
        say "auth $p: chrome candidate INVALID — discarded, live session left byte-identical"
    fi
    rm -rf -- "$cand_dir"

    # Last resort: the last session that was ever proven alive.
    lastgood="$(nblm_storage "$p").lastgood"
    if [ -f "$lastgood" ]; then
        say "auth $p: trying lastgood session via candidate"
        mkdir -p "$cand_dir" && chmod 700 "$cand_dir"
        if cp -- "$lastgood" "$(nblm_storage "$cand")" \
                && chmod 600 "$(nblm_storage "$cand")" \
                && nblm_validate "$cand" "$p lastgood candidate verified by read"; then
            if nblm_promote "$p" "$cand"; then
                nblm_mark_validated "$p"
                nblm_refresh_lastgood "$p"
                return 0
            fi
        else
            say "auth $p: lastgood candidate INVALID too — discarded"
        fi
        rm -rf -- "$cand_dir"
    fi

    say "auth $p FAILED — three reads refused across a minute, not a hiccup; chrome and lastgood candidates invalid"
    return 1
}
