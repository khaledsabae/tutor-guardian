"""install_system_image.sh against a stub sdkmanager: corrupt downloads are
retried from scratch, and only a complete image counts as installed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / 'install_system_image.sh'
PKG = 'system-images;android-35;google_apis;x86_64'

# Each `--install` call takes the next word of $PLAN:
#   ok       unpacks a complete image, exit 0
#   corrupt  the 2026-10-08 failure: prints the zip error, leaves a partial
#            image and a cached archive, and still exits 0
#   fail     exit 1, nothing written
# It also records whether a partial image or cached archive was still there.
STUB = r'''#!/bin/bash
[ "$1" = --licenses ] && { head -c 64 >/dev/null; exit 0; }
n=$(( $(cat "$STATE/calls" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE/calls"
echo "$*" >> "$STATE/args"
dir="$ANDROID_HOME/system-images/android-35/google_apis/x86_64"
[ -e "$dir" ] || [ -e "$ANDROID_HOME/.temp" ] && echo "call $n saw leftovers" >> "$STATE/leftovers"
step=$(echo "$PLAN" | cut -d' ' -f"$n")
case "$step" in
  ok) mkdir -p "$dir"; for f in package.xml source.properties system.img ramdisk.img; do echo x > "$dir/$f"; done ;;
  corrupt) echo "Warning: An error occurred while preparing SDK package Google APIs Intel x86_64 Atom System Image: Error on ZipFile unknown archive."
           mkdir -p "$dir" "$ANDROID_HOME/.temp"; echo x > "$dir/system.img"; echo x > "$ANDROID_HOME/.temp/image.zip" ;;
  fail) exit 1 ;;
esac
exit 0
'''


class InstallSystemImageTest(unittest.TestCase):
    def run_script(self, plan, attempts=3, preinstalled=False):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sdk, state = d / 'sdk', d / 'state'
            sdk.mkdir()
            state.mkdir()
            stub = d / 'sdkmanager'
            stub.write_text(STUB)
            stub.chmod(0o755)
            image = sdk / 'system-images/android-35/google_apis/x86_64'
            if preinstalled:
                image.mkdir(parents=True)
                for f in ('package.xml', 'source.properties', 'system.img', 'ramdisk.img'):
                    (image / f).write_text('x')
            env = dict(os.environ, ANDROID_HOME=str(sdk), SDKMANAGER=str(stub), STATE=str(state),
                       PLAN=plan, E2E_SDK_ATTEMPTS=str(attempts), E2E_SDK_BACKOFF='0')
            env.pop('ANDROID_SDK_ROOT', None)
            proc = subprocess.run(['bash', str(SCRIPT), PKG], env=env,
                                  capture_output=True, text=True, timeout=30)
            read = lambda name: (state / name).read_text() if (state / name).exists() else ''
            return proc, int(read('calls') or 0), read('leftovers'), read('args'), (image / 'package.xml').exists()

    def test_first_try_succeeds(self):
        proc, calls, _, args, installed = self.run_script('ok')
        self.assertEqual((proc.returncode, calls, installed), (0, 1, True), proc.stdout)
        self.assertIn(f'--install {PKG} --channel=0', args)

    def test_corrupt_download_is_retried_from_a_clean_slate(self):
        proc, calls, leftovers, _, installed = self.run_script('corrupt ok')
        self.assertEqual((proc.returncode, calls, installed), (0, 2, True), proc.stdout)
        self.assertEqual(leftovers, '', 'the partial image and cached archive must be gone before the retry')
        self.assertIn('::warning title=SDK download::', proc.stdout)

    def test_exit_zero_with_an_incomplete_image_is_not_success(self):
        proc, calls, _, _, installed = self.run_script('corrupt corrupt corrupt')
        self.assertEqual((proc.returncode, calls, installed), (1, 3, False))
        self.assertIn('::error title=SDK download::', proc.stdout)

    def test_gives_up_after_the_configured_attempts(self):
        proc, calls, _, _, _ = self.run_script('fail fail fail fail', attempts=2)
        self.assertEqual((proc.returncode, calls), (1, 2))

    def test_nonzero_exit_then_success(self):
        proc, calls, _, _, installed = self.run_script('fail ok')
        self.assertEqual((proc.returncode, calls, installed), (0, 2, True))

    def test_a_complete_image_is_not_downloaded_again(self):
        proc, calls, _, _, _ = self.run_script('fail', preinstalled=True)
        self.assertEqual((proc.returncode, calls), (0, 0), proc.stdout)

    def test_refuses_a_package_that_is_not_a_system_image(self):
        proc = subprocess.run(['bash', str(SCRIPT), 'emulator'], capture_output=True, text=True,
                              env=dict(os.environ, ANDROID_HOME='/nonexistent'), timeout=10)
        self.assertEqual(proc.returncode, 2)


if __name__ == '__main__':
    unittest.main()
