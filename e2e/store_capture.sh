#!/usr/bin/env bash
# Store-listing capture (dispatch only: mobile-e2e.yml, input store_capture).
# Real app screens for the Play listing, with a family a stranger would
# recognise — not the CI marker names — and therefore NEVER against
# production: the APK is the rehearsal head (API_BASE_URL=http://10.0.2.2:8090),
# and behind the as-of proxy on :8090 is the PR head's backend image on this
# runner, with a fresh SQLite DB and no secrets. Production's test-traffic
# filter (backend/app/core/real_traffic.py) keys on «E2E-Maestro» and
# «E2E test…»; a natural name there would count as a real family, which is
# why this lives beside the rehearsal and not in run.sh.
#
#   E2E_APKS  dir with rehearsal-head/ (app.apk, l10n/app_{ar,en}.arb, ref.txt)
#   E2E_OUT   dir for everything uploaded as the e2e-store-capture artifact
#   REHEARSAL_UPSTREAM / REHEARSAL_PROXY_PORT  as in rehearsal.sh
#
# Per language (ar, en), one fresh install:
#   onboarding (child CHILD_NAME, band 7-9) → gallery/shoot.yaml «after» pass
#   (adds SECOND_CHILD, band 4-6: family road, child corner …) → family
#   programs → the Ramadan street at day 1 / 15 / 27 (the as-of proxy moves
#   the server's date; ticks light the lanterns).
# Informational throughout; exits non-zero only when a store slot's shot is
# missing, so a dispatch never looks complete without its pictures.
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
QUESTION="${E2E_QUESTION:-كيف أعلّم طفلي الصدق؟}"
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

# lang  CHILD_NAME  SECOND_CHILD
FAMILIES=("ar|سارة|يوسف" "en|Sara|Yusuf")

R="$OUT/store"
mkdir -p "$OUT/maestro" "$OUT/screens" "$OUT/logcat" "$R"
: > "$OUT/results.tsv"
AS_OF_FILE="$R/as_of.txt"
STAGES="$R/stages.tsv"

say() { echo "[store] $*"; }
mark() { adb shell log -t E2E "$*" >/dev/null 2>&1 || true; }

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
python3 "$E2E/e2e_tool.py" as-of-preflight --upstream "$UPSTREAM" --proxy "$PROXY" \
  --as-of-file "$AS_OF_FILE" --stages-out "$STAGES" --out "$R/preflight.md" || true
: > "$AS_OF_FILE"   # today's real date for everything before the street

adb wait-for-device
adb shell svc power stayon true || true
adb shell settings put system screen_off_timeout 1800000 || true
adb shell input keyevent 82 || true
adb shell settings put global hide_error_dialogs 1 || true
adb shell setprop debug.firebase.analytics.app "$PKG" || true
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat/logcat.txt" 2>&1 &
LOGCAT_PID=$!

l10n_head() { python3 "$E2E/e2e_tool.py" l10n --arb-dir "$APKS/rehearsal-head/l10n" --out "$FLOWS/common/l10n.js"; }

run_flow() {  # lineage name file child second [extra maestro args...]
  local lineage=$1 name=$2 file=$3 child=$4 second=$5 dir rc
  shift 5
  dir="$OUT/maestro/$lineage/$name"
  mkdir -p "$dir"
  echo "::group::store $lineage / $name"
  mark "BEGIN $lineage/$name"
  maestro test --format junit --output "$dir/report.xml" --test-output-dir "$dir" \
    -e CHILD_NAME="$child" -e SECOND_CHILD="$second" -e QUESTION="$QUESTION" "$@" "$FLOWS/$file"
  rc=$?
  mark "END $lineage/$name rc=$rc"
  printf '%s\t%s\t%s\n' "$lineage" "$name" "$rc" >> "$OUT/results.tsv"
  find "$dir" -path '*takeScreenshot*' -name '*.png' | while read -r png; do
    cp "$png" "$OUT/screens/${lineage}__${name}__$(basename "$png")"
  done
  echo "::endgroup::"
  [ "$rc" -eq 0 ] || echo "::warning title=store $lineage/$name::flow failed (rc=$rc)"
  return "$rc"
}

mapfile -t STAGE_LINES < "$STAGES"
street() {  # lineage lang child second
  local line label date day markwhat
  for line in "${STAGE_LINES[@]}"; do
    IFS=$'\t' read -r label date day <<< "$line"
    case "$label" in day1|day15) markwhat=challenge ;; day27) markwhat=all ;; *) continue ;; esac
    printf '%s %s\n' "$date" "$1_$label" > "$AS_OF_FILE"
    run_flow "$1" "street_$label" rehearsal/stage.yaml "$3" "$4" -e UI_LANG="$2" \
      -e STAGE="$label" -e DAY="$day" -e TAG=after -e VARIANT="$2" -e MARK="$markwhat" \
      -e EXPECT_BASELINE_MARK=false || true
  done
  : > "$AS_OF_FILE"
}

if ! l10n_head; then
  echo "::error::selector generation failed"
  exit 1
fi
for fam in "${FAMILIES[@]}"; do
  IFS='|' read -r lang child second <<< "$fam"
  say "family $lang: $child + $second"
  adb uninstall "$PKG" >/dev/null 2>&1 || true
  if ! adb install "$APKS/rehearsal-head/app.apk"; then
    echo "::error::install failed"
    continue
  fi
  run_flow "$lang" onboard fresh/01_onboarding.yaml "$child" "$second" -e UI_LANG=ar || continue
  run_flow "$lang" shoot gallery/shoot.yaml "$child" "$second" -e UI_LANG="$lang" \
    -e GALLERY_TAG=after -e GALLERY_VARIANT="$lang" || true
  run_flow "$lang" programs fresh/09_programs.yaml "$child" "$second" -e UI_LANG="$lang" || true
  if run_flow "$lang" settings rehearsal/variant.yaml "$child" "$second" -e UI_LANG="$lang" -e THEME=light; then
    street "$lang" "$lang" "$child" "$second"
  fi
done

kill "$LOGCAT_PID" 2>/dev/null || true
missing=0
for lang in ar en; do
  for shot in home family_road child_corner week_lanterns stories_open next_step day27_street; do
    if ! ls "$OUT/screens/" | grep -q "^${lang}__.*${shot}\.png$"; then
      echo "::error title=store capture::no ${lang} ${shot} shot"
      missing=1
    fi
  done
done
exit "$missing"
