"""Exercise the real shell runner with fake device/CLI boundaries; no builds."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class RunnerTest(unittest.TestCase):
    def run_runner(self, fail_flow='', fail_head_l10n=False, fail_l10n='', retry_flow=''):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'e2e').mkdir()
            shutil.copy(Path(__file__).with_name('run.sh'), root / 'e2e/run.sh')
            bins = root / 'bin'
            bins.mkdir()
            scripts = {
                'adb': '''#!/bin/bash
if [[ "$*" == 'shell dumpsys package '* ]]; then
  echo 'versionCode=113 firstInstallTime=2026-10-07 10:00:00'
fi
exit 0
''',
                'maestro': '''#!/bin/bash
out=''
while [ $# -gt 0 ]; do [ "$1" = --test-output-dir ] && out=$2; shift; done
if [[ -n "$RETRY_FLOW" && "$out" == *"/$RETRY_FLOW" ]]; then
  mkdir -p "$out/run/takeScreenshot" && : > "$out/run/takeScreenshot/lesson_server_error_retry.png"
fi
[[ "$out" != *"/$FAIL_FLOW" || -z "$FAIL_FLOW" ]]
''',
                'python3': '''#!/bin/bash
if [[ "$2" == l10n && "$FAIL_L10N" == first-head && "$*" == *'/head/l10n'* && ! -f "$L10N_COUNT" ]]; then
  echo 1 > "$L10N_COUNT"
  exit 1
fi
if [[ "$2" == l10n && -n "$FAIL_L10N" && "$*" == *"/$FAIL_L10N/l10n"* ]]; then exit 1; fi
if [[ "$2" == l10n && "$*" == *'/head/l10n'* ]]; then
  n=$(cat "$L10N_COUNT" 2>/dev/null || echo 0)
  echo $((n+1)) > "$L10N_COUNT"
  if [[ "$FAIL_HEAD_L10N" == 1 && "$n" -gt 0 ]]; then exit 1; fi
fi
exit 0
''',
                'sleep': '#!/bin/bash\nexit 0\n',
            }
            for name, script in scripts.items():
                p = bins / name
                p.write_text(script)
                p.chmod(0o755)
            env = dict(os.environ, PATH=f'{bins}:{os.environ["PATH"]}',
                       E2E_APKS=str(root / 'apks'), E2E_OUT=str(root / 'out'),
                       FAIL_FLOW=fail_flow, RETRY_FLOW=retry_flow, FAIL_L10N=fail_l10n, FAIL_HEAD_L10N=str(int(fail_head_l10n)),
                       L10N_COUNT=str(root / 'l10n_count'))
            proc = subprocess.run(['bash', str(root / 'e2e/run.sh')], env=env,
                                  capture_output=True, text=True, timeout=15)
            rows = {}
            for line in (root / 'out/results.tsv').read_text().splitlines():
                lineage, name, rc, seconds, reason = line.split('\t')
                rows[lineage, name] = (rc, reason)
            return proc.returncode, rows, proc.stdout + proc.stderr

    def test_programs_runs_as_gate(self):
        rc, rows, _ = self.run_runner(fail_flow='09_programs')
        self.assertEqual(rows['fresh', '09_programs'], ('1', ''))
        self.assertEqual(rc, 1)
        self.assertEqual(rows['upgrade', '03_after_upgrade'][0], '0')

    def test_programs_passes(self):
        rc, rows, output = self.run_runner()
        self.assertEqual(rc, 0, output)
        self.assertEqual(rows['fresh', '09_programs'], ('0', ''))

    def test_programs_skips_when_fresh_onboarding_fails(self):
        rc, rows, _ = self.run_runner(fail_flow='01_onboarding')
        self.assertEqual(rc, 1)
        self.assertEqual(rows['fresh', '09_programs'], ('skip', 'onboarding failed'))
        self.assertEqual(rows['upgrade', '03_after_upgrade'][0], '0')

    def test_upgrade_selector_generation_failure_is_not_masked(self):
        rc, rows, output = self.run_runner(fail_head_l10n=True)
        self.assertEqual(rc, 1, output)
        for name in ('03_after_upgrade', '04_child_kept'):
            self.assertEqual(rows['upgrade', name], ('skip', 'head selector generation failed'))

    def test_baseline_onboarding_failure_blocks_upgrade(self):
        rc, rows, _ = self.run_runner(fail_flow='01_baseline_onboarding')
        self.assertEqual(rc, 1)
        self.assertEqual(rows['upgrade', '03_after_upgrade'], ('skip', 'baseline onboarding failed'))

    def test_failed_baseline_control_remains_informational(self):
        rc, rows, output = self.run_runner(fail_flow='02_baseline_restart')
        self.assertEqual(rc, 0, output)
        self.assertEqual(rows['upgrade', '02_baseline_restart'], ('1', 'informational'))
        self.assertEqual(rows['upgrade', '03_after_upgrade'][0], '0')
        self.assertEqual(rows['upgrade', '04_child_kept'][0], 'skip')

    def test_fresh_selector_generation_failure_fails_run(self):
        rc, rows, output = self.run_runner(fail_l10n='first-head')
        self.assertEqual(rc, 1, output)
        self.assertEqual(rows['fresh', '09_programs'][0], 'skip')

    def test_baseline_selector_generation_failure_fails_run(self):
        rc, rows, output = self.run_runner(fail_l10n='baseline')
        self.assertEqual(rc, 1, output)
        self.assertEqual(rows['upgrade', '03_after_upgrade'][0], 'skip')

    def test_a_retried_pass_is_announced(self):
        rc, rows, output = self.run_runner(retry_flow='02_today_lesson')
        self.assertEqual(rc, 0, output)
        self.assertEqual(rows['fresh', '02_today_lesson'], ('0', ''))
        self.assertIn('::warning title=E2E fresh/02_today_lesson::passed only after a retry', output)
        self.assertEqual(output.count('passed only after a retry'), 1)

    def test_gallery_shoots_are_informational(self):
        # A failed shoot is a warning and a missing cell in the gallery, never
        # a gate failure: the 13 gate journeys are the gate, the gallery is
        # the eyes (docs/NOOR_WAL_QANADIL_PLAN.md, Phase 0).
        rc, rows, output = self.run_runner(fail_flow='01_before_ar')
        self.assertEqual(rc, 0, output)
        # Every pass owns a fresh install + onboarding (gpass): the pass's
        # onboarding is a row of its own, and a failed SHOOT stays warning-only.
        self.assertEqual(rows['gallery', '01_before_ar_onboard'], ('0', 'informational'))
        self.assertEqual(rows['gallery', '01_before_ar'], ('1', 'informational'))
        self.assertEqual(rows['gallery', '04_after_ar'][0], '0')
        self.assertIn('::warning title=E2E gallery/01_before_ar::informational checkpoint failed', output)

    def test_gallery_pass_skips_when_its_own_onboarding_fails(self):
        # One pass's failed onboarding skips only that pass; the others (and
        # the two gate lineages) still run. In real CI the require-after
        # gallery gate is what turns a fully-blind gallery red.
        rc, rows, output = self.run_runner(fail_flow='01_before_ar_onboard')
        self.assertEqual(rc, 0, output)
        self.assertEqual(rows['gallery', '01_before_ar'], ('skip', 'install/onboarding failed'))
        self.assertEqual(rows['gallery', '04_after_ar'][0], '0')
        # The other two lineages are untouched by the gallery's failure.
        self.assertEqual(rows['fresh', '01_onboarding'], ('0', ''))
