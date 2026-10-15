#!/usr/bin/env bash
# The Ramadan rehearsal (gate G2) and the sound × recitation check, on the
# emulator that reactivecircus/android-emulator-runner booted for job
# `rehearsal` of .github/workflows/mobile-e2e.yml — the header there explains
# the why. Never talks to production: both APKs were built with
# API_BASE_URL=http://10.0.2.2:<proxy port> (the runner's loopback, seen from
# the emulator), and behind the proxy is the PR head's backend image with
# PROGRAMS_AS_OF_ENABLED=1.
#
#   E2E_APKS             dir with rehearsal-head/ and rehearsal-baseline/
#                        (app.apk, l10n/app_{ar,en}.arb, ref.txt)
#   E2E_OUT              dir for everything uploaded as artifacts
#   REHEARSAL_UPSTREAM   the candidate backend (default http://127.0.0.1:8091)
#   REHEARSAL_PROXY_PORT where the as-of proxy listens (default 8090)
#
# One install lineage, then the sound check:
#   00 the Play build (v1.0.72+117), fresh, Arabic onboarding        gate
#   b_* the Play build walks the six stages (the gallery's «before») info
#   install -r the PR head (an in-place upgrade: data kept)          gate
#   ar_* / en_* / dk_* the head walks the six stages in Arabic,
#      English and Arabic-dark; the Arabic pass ticks the marks      gate
#   sound: a recitation in the reader, three ticks, `dumpsys audio`  gate
# then: every gate stage's programs calls carried its as_of (the proxy log),
# the stage gallery has every head shot, and the logcat gate.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E2E="$ROOT/e2e"
FLOWS="$E2E/flows"
APKS="${E2E_APKS:?set E2E_APKS}"
OUT="${E2E_OUT:?set E2E_OUT}"
UPSTREAM="${REHEARSAL_UPSTREAM:-http://127.0.0.1:8091}"
PROXY_PORT="${REHEARSAL_PROXY_PORT:-8090}"
PROXY="http://127.0.0.1:$PROXY_PORT"
PKG=com.alsaba.almorabbi
CHILD_NAME="${E2E_CHILD_NAME:-E2E-Rehearsal}"
QUESTION="${E2E_QUESTION:-E2E test how can I teach my child to be honest}"
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

R="$OUT/rehearsal"
mkdir -p "$OUT/logcat" "$OUT/maestro" "$OUT/screens" "$OUT/device" "$R"
: > "$OUT/results.tsv"
: > "$R/expected_stages.txt"
AS_OF_FILE="$R/as_of.txt"
STAGES="$R/stages.tsv"
FAILED=0

say() { echo "[rehearsal] $*"; }
mark() { adb shell log -t E2E "$*" >/dev/null 2>&1 || true; }

# ── the as-of proxy, then the preflight (no emulator involved yet) ────────
: > "$AS_OF_FILE"
python3 "$E2E/e2e_tool.py" as-of-proxy --listen "127.0.0.1:$PROXY_PORT" --upstream "$UPSTREAM" \
  --as-of-file "$AS_OF_FILE" --log "$R/proxy.tsv" > "$R/proxy.out" 2>&1 &
PROXY_PID=$!
LOGCAT_PID=
trap 'kill "$PROXY_PID" 2>/dev/null || true; [ -n "$LOGCAT_PID" ] && kill "$LOGCAT_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -fsS -o /dev/null "$PROXY/health" 2>/dev/null && break
  sleep 1
done

if ! python3 "$E2E/e2e_tool.py" as-of-preflight --upstream "$UPSTREAM" --proxy "$PROXY" \
     --as-of-file "$AS_OF_FILE" --stages-out "$STAGES" --out "$R/preflight.md"; then
  echo "::error title=Ramadan rehearsal::the candidate does not honour as_of — nothing on the emulator would prove anything"
  FAILED=1
fi
if [ ! -s "$STAGES" ]; then
  python3 "$E2E/e2e_tool.py" summary "$OUT" --title "Ramadan rehearsal (G2)" || true
  exit 1
fi

# ── device ───────────────────────────────────────────────────────────────
adb wait-for-device
adb shell svc power stayon true || true
adb shell settings put system screen_off_timeout 1800000 || true
adb shell input keyevent 82 || true
adb shell settings put global hide_error_dialogs 1 || true
adb shell setprop debug.firebase.analytics.app "$PKG" || true
adb shell setprop log.tag.FirebaseCrashlytics VERBOSE || true
adb shell getprop ro.build.version.release > "$OUT/device/android_version.txt" || true
adb shell getprop ro.product.model > "$OUT/device/model.txt" || true
adb logcat -G 16M >/dev/null 2>&1 || true
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat/logcat.txt" 2>&1 &
LOGCAT_PID=$!

l10n_for() {
  if ! python3 "$E2E/e2e_tool.py" l10n --arb-dir "$APKS/$1/l10n" --out "$FLOWS/common/l10n.js"; then
    echo "::error::selector generation failed for $1"
    FAILED=1
    return 1
  fi
}

pkg_field() { adb shell dumpsys package "$PKG" | tr -d '\r' | grep -m1 -oE "$1=[^ ]+( [0-9:]+)?" | cut -d= -f2-; }

run_flow() {  # severity(gate|info) lineage name file [extra maestro args...]
  local severity=$1 lineage=$2 name=$3 file=$4 dir start rc
  shift 4
  dir="$OUT/maestro/$lineage/$name"
  mkdir -p "$dir"
  echo "::group::E2E $lineage / $name"
  mark "BEGIN $lineage/$name"
  start=$(date +%s)
  maestro test --format junit --output "$dir/report.xml" --test-output-dir "$dir" \
    -e CHILD_NAME="$CHILD_NAME" -e QUESTION="$QUESTION" "$@" "$FLOWS/$file"
  rc=$?
  mark "END $lineage/$name rc=$rc"
  printf '%s\t%s\t%s\t%s\t%s\n' "$lineage" "$name" "$rc" "$(( $(date +%s) - start ))" \
    "$([ "$severity" = info ] && echo informational)" >> "$OUT/results.tsv"
  find "$dir" -path '*takeScreenshot*' -name '*.png' | while read -r png; do
    cp "$png" "$OUT/screens/${lineage}__${name}__$(basename "$png")"
  done
  echo "::endgroup::"
  if [ "$rc" -ne 0 ]; then
    if [ "$severity" = info ]; then
      echo "::warning title=Rehearsal $lineage/$name::informational checkpoint failed (rc=$rc)"
    else
      FAILED=1
      echo "::error title=Rehearsal $lineage/$name::checkpoint failed (rc=$rc) — see the e2e-rehearsal artifact"
    fi
  fi
  return "$rc"
}

skip() { printf '%s\t%s\tskip\t0\t%s\n' "$1" "$2" "${3:-}" >> "$OUT/results.tsv"; }

install_fresh() {  # variant
  adb uninstall "$PKG" >/dev/null 2>&1 || true
  if ! adb install "$APKS/$1/app.apk"; then
    echo "::error::adb install of the $1 APK failed"
    FAILED=1
    return 1
  fi
}

set_stage() {  # date label — what the proxy adds from now on
  printf '%s %s\n' "$1" "$2" > "$AS_OF_FILE"
  mark "STAGE $2 as_of=$1"
  say "stage $2: as_of=$1"
}

# stage_pass severity tag variant prefix — walk the six stages of $STAGES.
# Only the head's Arabic pass ticks (day 1 and 15: the challenge, day 27:
# everything); the Play build ticks day 1's challenge, which the head must
# still show after the upgrade.
BASELINE_MARKED=false
HEAD_INSTALLED=no
# Read once, up front: adb and maestro both read stdin, and inside a
# `while read … < file` loop they would swallow the remaining stages.
mapfile -t STAGE_LINES < "$STAGES"
stage_pass() {
  local severity=$1 tag=$2 variant=$3 prefix=$4 line label date day mark lang expect rc
  lang=ar; [ "$variant" = en ] && lang=en
  for line in "${STAGE_LINES[@]}"; do
    IFS=$'\t' read -r label date day <<< "$line"
    [ -n "$label" ] || continue
    mark=none
    if [ "$tag" = before ] && [ "$label" = day1 ]; then mark=challenge; fi
    if [ "$tag" = after ] && [ "$variant" = ar ]; then
      case "$label" in day1|day15) mark=challenge ;; day27) mark=all ;; esac
    fi
    expect=false
    if [ "$tag" = after ] && [ "$variant" = ar ] && [ "$label" = day1 ]; then expect=$BASELINE_MARKED; fi
    set_stage "$date" "${prefix}_${label}"
    [ "$severity" = gate ] && echo "${prefix}_${label}" >> "$R/expected_stages.txt"
    rc=0
    run_flow "$severity" rehearsal "${prefix}_${label}" rehearsal/stage.yaml -e UI_LANG="$lang" \
      -e STAGE="$label" -e DAY="$day" -e TAG="$tag" -e VARIANT="$variant" -e MARK="$mark" \
      -e EXPECT_BASELINE_MARK="$expect" || rc=$?
    if [ "$tag" = before ] && [ "$label" = day1 ] && [ "$rc" -eq 0 ]; then BASELINE_MARKED=true; fi
  done
}

first_date=$(head -1 "$STAGES" | cut -f2)
HEAD_PASSES=(ar_ en_ dk_)

# ── the Play build: onboarding, then its walk (the gallery's «before») ────
set_stage "$first_date" onboarding
if install_fresh rehearsal-baseline && l10n_for rehearsal-baseline \
   && run_flow gate rehearsal 00_baseline_onboarding upgrade/01_baseline_onboarding.yaml -e UI_LANG=ar; then
  stage_pass info before ar b
  # ── the upgrade, in place ──────────────────────────────────────────────
  base_code=$(pkg_field versionCode); base_first=$(pkg_field firstInstallTime)
  if adb install -r "$APKS/rehearsal-head/app.apk"; then
    HEAD_INSTALLED=yes
    head_code=$(pkg_field versionCode); head_first=$(pkg_field firstInstallTime)
    say "upgrade: versionCode $base_code -> $head_code, firstInstallTime '$base_first' -> '$head_first'"
    echo "upgrade: versionCode ${base_code} -> ${head_code}; firstInstallTime kept: $([ "$base_first" = "$head_first" ] && echo yes || echo NO)" \
      > "$OUT/device/upgrade.txt"
    if [ "$base_first" != "$head_first" ]; then
      echo "::error::install -r did not upgrade in place (firstInstallTime changed) — app data was not kept"
      FAILED=1
    fi
    if l10n_for rehearsal-head; then
      stage_pass gate after ar ar
      if run_flow gate rehearsal en_settings rehearsal/variant.yaml -e UI_LANG=en -e THEME=light; then
        stage_pass gate after en en
      else
        skip rehearsal en_stages "could not switch to English"
      fi
      if run_flow gate rehearsal dk_settings rehearsal/variant.yaml -e UI_LANG=ar -e THEME=dark; then
        stage_pass gate after ar_dark dk
      else
        skip rehearsal dk_stages "could not switch to dark"
      fi
    else
      for p in "${HEAD_PASSES[@]}"; do skip rehearsal "${p}stages" "head selector generation failed"; done
    fi
  else
    echo "::error::adb install -r of the rehearsal head APK over the Play build failed (signature or downgrade?)"
    FAILED=1
    for p in "${HEAD_PASSES[@]}"; do skip rehearsal "${p}stages" "install -r failed"; done
  fi
else
  for p in b_ "${HEAD_PASSES[@]}"; do skip rehearsal "${p}stages" "Play-build onboarding failed"; done
fi

# ── sound × recitation ──────────────────────────────────────────────────
# On the head build — the only one with the CI key probe. If the upgrade
# never put it on the device, it gets a fresh install of its own. A
# recitation in the reader; the audio service's view before; three ticks
# through the probe; its view after, three times over three seconds (an ayah
# boundary can fall on one sample); the app's own view last.
: > "$AS_OF_FILE"
audio_dump() { adb shell dumpsys audio > "$1" 2>&1 || true; }
if [ "$HEAD_INSTALLED" != yes ]; then
  install_fresh rehearsal-head && l10n_for rehearsal-head \
    && run_flow gate sound 00_head_onboarding fresh/01_onboarding.yaml -e UI_LANG=ar \
    && HEAD_INSTALLED=yes
fi
if [ "$HEAD_INSTALLED" = yes ] && l10n_for rehearsal-head \
   && run_flow gate sound 01_recitation rehearsal/sound_start.yaml -e UI_LANG=ar; then
  uid=$(adb shell cmd package list packages -U "$PKG" | tr -d '\r' | grep -m1 -oE 'uid:[0-9]+' | cut -d: -f2)
  [ -n "$uid" ] || uid=$(adb shell dumpsys package "$PKG" | tr -d '\r' | grep -m1 -oE '(userId|appId)=[0-9]+' | cut -d= -f2)
  say "app uid: $uid"
  audio_dump "$R/audio_before.txt"
  # The ticks. F12 reaches the probe only if the key reaches the Flutter view
  # (on run 38714154049 three presses produced none), so it stays as a
  # witness; the system light/dark mode, there and back, reaches the app
  # whatever holds the focus (MainActivity handles uiMode itself: no restart).
  adb shell input keyevent KEYCODE_F12 || true
  sleep 1
  adb shell cmd uimode night yes || true
  sleep 2
  adb shell cmd uimode night no || true
  sleep 2
  for n in 1 2 3; do
    audio_dump "$R/audio_after_$n.txt"
    sleep 1
  done
  # The app's own account of what it was asked to sound (core/e2e_probes.dart).
  echo "- the probe's own log: $(grep -o 'tg.e2e: tick ([^)]*)' "$OUT/logcat/logcat.txt" 2>/dev/null | sort | uniq -c | sed 's/^ *//' | paste -sd';' - || true)" \
    > "$R/probe.md"
  verdict=0
  python3 "$E2E/e2e_tool.py" audio-focus --uid "$uid" --before "$R/audio_before.txt" \
    --after "$R/audio_after_1.txt" --after "$R/audio_after_2.txt" --after "$R/audio_after_3.txt" \
    --out "$R/sound.md" || verdict=$?
  printf 'sound\taudio_focus\t%s\t0\t\n' "$verdict" >> "$OUT/results.tsv"
  [ "$verdict" -eq 0 ] || FAILED=1
  run_flow gate sound 02_still_reciting rehearsal/sound_after.yaml -e UI_LANG=ar || true
else
  echo "::error title=Sound × recitation::the recitation could not be started on the head build — the check did not run"
  FAILED=1
  skip sound audio_focus "recitation not started"
fi

# ── every gate stage's programs calls carried its as_of ─────────────────
if ! python3 "$E2E/e2e_tool.py" as-of-report --log "$R/proxy.tsv" --expect "$R/expected_stages.txt" \
     --out "$R/as_of.md"; then
  FAILED=1
fi

# ── the stage gallery: every head shot present ───────────────────────────
if ! python3 "$E2E/e2e_tool.py" rehearsal-gallery "$OUT/screens" --out "$OUT/gallery" --require-after; then
  echo "::error title=Ramadan rehearsal gallery::a stage screen has no PR-head shot (e2e-rehearsal artifact)"
  FAILED=1
fi

# ── logcat gate ──────────────────────────────────────────────────────────
sleep 3
kill "$LOGCAT_PID" 2>/dev/null || true
wait "$LOGCAT_PID" 2>/dev/null || true
if ! python3 "$E2E/e2e_tool.py" logcat-gate "$OUT/logcat/logcat.txt" \
     --package "$PKG" --allowlist "$E2E/logcat_allowlist.txt" --out "$OUT/logcat/gate.txt"; then
  echo "::error title=Rehearsal logcat gate::crash, ANR or Flutter error in logcat — see logcat/gate.txt"
  FAILED=1
fi

{
  echo "- head: \`$(cat "$APKS/rehearsal-head/ref.txt" 2>/dev/null)\` · Play build: \`$(cat "$APKS/rehearsal-baseline/ref.txt" 2>/dev/null)\` · server: the PR head's backend image on the runner, \`PROGRAMS_AS_OF_ENABLED=1\` (never production)"
  echo "- device: $(cat "$OUT/device/model.txt" 2>/dev/null), Android $(cat "$OUT/device/android_version.txt" 2>/dev/null)"
  echo "- $(cat "$OUT/device/upgrade.txt" 2>/dev/null || echo 'upgrade: not reached')"
  echo
  cat "$R/preflight.md" 2>/dev/null
  echo
  cat "$R/as_of.md" 2>/dev/null
  echo
  cat "$R/sound.md" 2>/dev/null || echo "### SOUND×RECITATION CHECKPOINT: NOT RUN"
  cat "$R/probe.md" 2>/dev/null
} > "$OUT/meta.md"
python3 "$E2E/e2e_tool.py" summary "$OUT" --title "Ramadan rehearsal (G2) + sound × recitation" || true
exit "$FAILED"
