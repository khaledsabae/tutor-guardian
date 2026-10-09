#!/usr/bin/env bash
# Runs the E2E journeys on the emulator that reactivecircus/android-emulator-runner
# booted. Called by .github/workflows/mobile-e2e.yml — the header there explains
# what is tested, why, and how the production traffic is marked.
#
#   E2E_APKS  dir with head/ and baseline/ (app.apk, l10n/app_{ar,en}.arb, ref.txt)
#   E2E_OUT   dir for everything uploaded as artifacts
#
# Two install lineages, each = one device_id + one child named $CHILD_NAME:
#   fresh    PR head, fresh install, Arabic: nine checkpoints
#   upgrade  baseline build, English onboarding → restart (control) →
#            `adb install -r` PR head
# plus a third, informational lineage (see the gallery block below):
#   gallery  baseline → same shots tagged «before» → install -r head →
#            the same shots tagged «after» — the معرض قبل/بعد.
# A failed checkpoint does not stop the next one (each starts by returning to
# Today), except onboarding, which everything after it needs.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E2E="$ROOT/e2e"
FLOWS="$E2E/flows"
APKS="${E2E_APKS:?set E2E_APKS}"
OUT="${E2E_OUT:?set E2E_OUT}"
PKG=com.alsaba.almorabbi
CHILD_NAME="${E2E_CHILD_NAME:-E2E-Maestro}"
QUESTION="${E2E_QUESTION:-E2E test how can I teach my child to be honest}"
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

mkdir -p "$OUT/logcat" "$OUT/maestro" "$OUT/screens" "$OUT/device"
: > "$OUT/results.tsv"
RUN_START_UTC=$(date -u '+%Y-%m-%d %H:%M:%S')
FAILED=0

say() { echo "[e2e] $*"; }
mark() { adb shell log -t E2E "$*" >/dev/null 2>&1 || true; }   # flow boundaries in logcat

# ── device ───────────────────────────────────────────────────────────────
adb wait-for-device
adb shell svc power stayon true || true
adb shell settings put system screen_off_timeout 1800000 || true
adb shell input keyevent 82 || true
# No system "X isn't responding" dialogs: right after boot the Pixel Launcher
# ANRs on a loaded runner and its dialog covers the app (first run: both
# onboardings blocked). The app's own ANRs and crashes are still logged, and the
# logcat gate fails on them — it never relied on a dialog.
adb shell settings put global hide_error_dialogs 1 || true
# GA4 debug mode for the app: its events go to DebugView and are excluded from
# reports and the BigQuery export (Firebase docs, "Debug events").
adb shell setprop debug.firebase.analytics.app "$PKG"
# Crashlytics logs each non-fatal the app records at VERBOSE; the gate reads it.
adb shell setprop log.tag.FirebaseCrashlytics VERBOSE
adb shell getprop ro.build.version.release > "$OUT/device/android_version.txt" || true
adb shell getprop ro.product.model > "$OUT/device/model.txt" || true

# ── logcat for the whole run ─────────────────────────────────────────────
adb logcat -G 16M >/dev/null 2>&1 || true
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat/logcat.txt" 2>&1 &
LOGCAT_PID=$!
trap 'kill "$LOGCAT_PID" 2>/dev/null || true' EXIT

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
  # The checkpoint screenshots (takeScreenshot), flattened for browsing; the
  # failure screenshots stay in the per-flow report.
  find "$dir" -path '*takeScreenshot*' -name '*.png' | while read -r png; do
    cp "$png" "$OUT/screens/${lineage}__${name}__$(basename "$png")"
  done
  # A flow that retried as a parent would (a 5xx from production, a lost tap)
  # leaves a *retry* screenshot. A pass is still a pass, but it is said aloud.
  if [ -n "$(find "$dir" -path '*takeScreenshot*' -name '*retry*.png' -print -quit)" ]; then
    echo "::warning title=E2E $lineage/$name::passed only after a retry — see the *retry* screenshot in e2e-screenshots"
  fi
  echo "::endgroup::"
  if [ "$rc" -ne 0 ]; then
    if [ "$severity" = info ]; then
      echo "::warning title=E2E $lineage/$name::informational checkpoint failed (rc=$rc)"
    else
      FAILED=1
      echo "::error title=E2E $lineage/$name::checkpoint failed (rc=$rc) — see the e2e-maestro-report artifact"
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

# ── lineage 1: fresh install of the PR head (Arabic) ────────────────────
# One process from onboarding through 06 (no restarts), so the checkpoints that
# need the child do not depend on the identity surviving a cold start; 07/08
# then restart and check exactly that.
FRESH=(02_today_lesson 03_assistant 04_child_mode 05_dark_mode 06_english 07_cold_start 08_child_survives_restart 09_programs)
if install_fresh head && l10n_for head \
   && run_flow gate fresh 01_onboarding fresh/01_onboarding.yaml -e UI_LANG=ar; then
  for f in "${FRESH[@]}"; do
    run_flow gate fresh "$f" "fresh/$f.yaml" -e UI_LANG=ar || true
  done
else
  for f in "${FRESH[@]}"; do skip fresh "$f" "onboarding failed"; done
fi
# ── lineage 2: baseline → install -r PR head (English) ──────────────────
UPGRADE=(02_baseline_restart 03_after_upgrade 04_child_kept)
if install_fresh baseline && l10n_for baseline \
   && run_flow gate upgrade 01_baseline_onboarding upgrade/01_baseline_onboarding.yaml -e UI_LANG=en; then
  # Control: does the baseline keep its own child across a restart? If not, a
  # missing child after the upgrade is the baseline's doing, not the PR's.
  baseline_kept=yes
  run_flow info upgrade 02_baseline_restart upgrade/02_baseline_restart.yaml -e UI_LANG=en || baseline_kept=no
  base_code=$(pkg_field versionCode); base_first=$(pkg_field firstInstallTime)
  if adb install -r "$APKS/head/app.apk"; then
    head_code=$(pkg_field versionCode); head_first=$(pkg_field firstInstallTime)
    say "upgrade: versionCode $base_code -> $head_code, firstInstallTime '$base_first' -> '$head_first'"
    echo "upgrade: versionCode ${base_code} -> ${head_code}; firstInstallTime kept: $([ "$base_first" = "$head_first" ] && echo yes || echo NO)" \
      > "$OUT/device/upgrade.txt"
    if [ "$base_first" != "$head_first" ]; then
      echo "::error::install -r did not upgrade in place (firstInstallTime changed) — app data was not kept"
      FAILED=1
    fi
    if ! l10n_for head; then
      echo "::error::head selector generation failed after install -r"
      FAILED=1
      skip upgrade 03_after_upgrade "head selector generation failed"
      skip upgrade 04_child_kept "head selector generation failed"
    else
      run_flow gate upgrade 03_after_upgrade upgrade/03_after_upgrade.yaml -e UI_LANG=en || true
      if [ "$baseline_kept" = yes ]; then
        run_flow gate upgrade 04_child_kept upgrade/04_child_kept.yaml -e UI_LANG=en || true
      else
        skip upgrade 04_child_kept "baseline lost its own child on restart (control 02) — not attributable to the upgrade"
      fi
    fi
  else
    echo "::error::adb install -r of the head APK over the baseline failed (signature or downgrade?)"
    FAILED=1
    skip upgrade 03_after_upgrade "install -r failed"
    skip upgrade 04_child_kept "install -r failed"
  fi
else
  for f in "${UPGRADE[@]}"; do skip upgrade "$f" "baseline onboarding failed"; done
fi

# ── lineage 3: the before/after gallery (informational) ─────────────────
# Phase 0 of docs/NOOR_WAL_QANADIL_PLAN.md: every run photographs the same
# screens on the baseline build («before» — what users have now) and the PR
# head («after»), in Arabic and English, plus one 200%-font pass. One child,
# one install: the baseline is upgraded in place with install -r, exactly
# like the upgrade lineage, so the head shoots see the same child's state.
# The font scale is a runtime system setting (settings put system font_scale),
# NOT AVD configuration — the avd cache key is untouched, and -no-snapshot-save
# keeps the change out of the snapshot. It is reset after each pass.
# Informational by design: a failed shoot is a warning, never a gate failure —
# the 13 gate journeys above are the gate, the gallery is the eyes.
font2x() {  # 2.0 = large, 1.0 = back to normal
  adb shell settings put system font_scale "$1" >/dev/null 2>&1 || true
  sleep 3
}
shoot() {  # name lang tag variant [extra -e args...]
  local name=$1 lang=$2 tag=$3 variant=$4
  shift 4
  run_flow info gallery "$name" gallery/shoot.yaml -e UI_LANG="$lang" \
    -e GALLERY_TAG="$tag" -e GALLERY_VARIANT="$variant" "$@" || true
}
if install_fresh baseline && l10n_for baseline \
   && run_flow gate gallery 00_onboarding fresh/01_onboarding.yaml -e UI_LANG=ar; then
  shoot 01_before_ar ar before ar
  shoot 02_before_en en before en
  font2x 2.0
  shoot 03_before_font2x ar before ar_font2x
  font2x 1.0
  if adb install -r "$APKS/head/app.apk" && l10n_for head; then
    shoot 04_after_en en after en
    shoot 05_after_ar ar after ar
    font2x 2.0
    shoot 06_after_font2x ar after ar_font2x
    font2x 1.0
  else
    echo "::warning title=E2E gallery::install -r / head selector generation failed — no «after» shots"
    for f in 04_after_en 05_after_ar 06_after_font2x; do skip gallery "$f" "install -r failed"; done
  fi
else
  for f in 00_onboarding 01_before_ar 02_before_en 03_before_font2x \
           04_after_en 05_after_ar 06_after_font2x; do
    skip gallery "$f" "baseline onboarding failed"
  done
fi

# ── the gallery artifact: before/after pairs in one markdown ────────────
# Never gates: a broken pairing must not fail a green run.
python3 "$E2E/e2e_tool.py" gallery "$OUT/screens" --out "$OUT/gallery" \
  || echo "::warning title=E2E gallery::summary generation failed (screenshots are still in e2e-screenshots)"

# ── logcat gate ──────────────────────────────────────────────────────────
sleep 3
kill "$LOGCAT_PID" 2>/dev/null || true
wait "$LOGCAT_PID" 2>/dev/null || true
if ! python3 "$E2E/e2e_tool.py" logcat-gate "$OUT/logcat/logcat.txt" \
     --package "$PKG" --allowlist "$E2E/logcat_allowlist.txt" --out "$OUT/logcat/gate.txt"; then
  echo "::error title=E2E logcat gate::crash, ANR or Flutter error in logcat — see logcat/gate.txt"
  FAILED=1
fi

{
  echo "- head: \`$(cat "$APKS/head/ref.txt" 2>/dev/null)\` · baseline: \`$(cat "$APKS/baseline/ref.txt" 2>/dev/null)\`"
  echo "- device: $(cat "$OUT/device/model.txt" 2>/dev/null), Android $(cat "$OUT/device/android_version.txt" 2>/dev/null)"
  echo "- $(cat "$OUT/device/upgrade.txt" 2>/dev/null || echo 'upgrade: not reached')"
  echo "- test traffic: child \`$CHILD_NAME\` (one per lineage), question \`$QUESTION\`, UTC window $RUN_START_UTC → $(date -u '+%Y-%m-%d %H:%M:%S')"
} > "$OUT/meta.md"
python3 "$E2E/e2e_tool.py" summary "$OUT" || true
exit "$FAILED"
