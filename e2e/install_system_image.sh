#!/usr/bin/env bash
# Installs the emulator system image before reactivecircus/android-emulator-runner
# needs it, retried and verified. The action downloads it once per job (it is
# not in the AVD cache) with no retry, and on 2026-10-08 one download came back
# corrupt ("Error on ZipFile unknown archive"): the emulator never booted and the
# whole E2E job went red. With the image already in place the action's own
# `sdkmanager --install` finds it installed and skips the download.
#
#   install_system_image.sh 'system-images;android-35;google_apis;x86_64'
#
#   E2E_SDK_ATTEMPTS  tries before giving up (default 3)
#   E2E_SDK_BACKOFF   seconds before the 2nd try, doubled each time (default 15)
#   SDKMANAGER        sdkmanager to run (default: the SDK's cmdline-tools/latest)
#
# A try counts only if the unpacked image is complete — sdkmanager can print the
# zip error and still exit 0 — so its exit code is not trusted on its own.
set -uo pipefail

PKG="${1:?usage: install_system_image.sh 'system-images;android-NN;TAG;ABI'}"
case "$PKG" in
  system-images\;*\;*\;*) ;;
  *) echo "::error::not a system image package: $PKG"; exit 2 ;;
esac
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:?set ANDROID_HOME or ANDROID_SDK_ROOT}}"
ATTEMPTS="${E2E_SDK_ATTEMPTS:-3}"
BACKOFF="${E2E_SDK_BACKOFF:-15}"
if [ -z "${SDKMANAGER:-}" ]; then
  SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"
  [ -x "$SDKMANAGER" ] || SDKMANAGER=sdkmanager
fi
DIR="$SDK/${PKG//;//}"

# package.xml is written last, once sdkmanager has unpacked the whole archive;
# system.img and ramdisk.img are what the emulator boots.
complete() {
  local f
  for f in package.xml source.properties system.img ramdisk.img; do
    [ -s "$DIR/$f" ] || { echo "[sdk] incomplete: $DIR/$f missing or empty"; return 1; }
  done
}

if complete >/dev/null 2>&1; then
  echo "[sdk] $PKG already installed and complete"
  exit 0
fi

yes 2>/dev/null | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true

wait_s="$BACKOFF"
for attempt in $(seq 1 "$ATTEMPTS"); do
  echo "[sdk] installing $PKG (attempt $attempt/$ATTEMPTS)"
  "$SDKMANAGER" --install "$PKG" --channel=0
  rc=$?
  if [ "$rc" -eq 0 ] && complete; then
    echo "[sdk] $PKG installed and complete"
    exit 0
  fi
  echo "::warning title=SDK download::$PKG attempt $attempt/$ATTEMPTS failed (sdkmanager rc=$rc or the image is incomplete)"
  # Drop what the failed try left, so the next one downloads afresh instead of
  # reusing a corrupt archive or a half-unpacked directory.
  rm -rf "$DIR" "$SDK/.temp" "$SDK/.downloadIntermediates"
  if [ "$attempt" -lt "$ATTEMPTS" ]; then
    sleep "$wait_s"
    wait_s=$(( wait_s * 2 ))
  fi
done
echo "::error title=SDK download::$PKG could not be installed intact after $ATTEMPTS attempts"
exit 1
