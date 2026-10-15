"""Exercise the real rehearsal runner (e2e/rehearsal.sh) with fake device,
CLI and tool boundaries; no builds, no emulator, no server."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

STAGES = ['before', 'day1', 'day15', 'day27', 'eid', 'after']

FAKES = {
    # adb and maestro both read stdin, like the real ones: a runner loop fed
    # from a file would lose its remaining lines to them.
    'adb': '''#!/bin/bash
cat > /dev/null
echo "$*" >> "$ADB_LOG"
case "$*" in
  'shell dumpsys package '*) echo 'versionCode=120 minSdk=24'; echo 'firstInstallTime=2026-10-15 10:00:00'; echo 'userId=10190' ;;
  'shell cmd package list packages -U '*) echo 'package:com.alsaba.almorabbi uid:10190' ;;
  'shell dumpsys audio') echo 'players:' ;;
esac
exit 0
''',
    'maestro': '''#!/bin/bash
cat > /dev/null
out=''; envs=''
while [ $# -gt 0 ]; do
  case "$1" in
    --test-output-dir) out=$2; shift ;;
    -e) envs="$envs|$2"; shift ;;
  esac
  shift
done
echo "$(basename "$out")$envs" >> "$MAESTRO_LOG"
[[ -z "$FAIL_FLOW" || "$out" != *"/$FAIL_FLOW" ]]
''',
    'python3': '''#!/bin/bash
cmd=$2
case "$cmd" in
  as-of-preflight)
    [ "${PREFLIGHT_RC:-0}" = 0 ] || exit 1
    while [ $# -gt 0 ]; do
      if [ "$1" = --stages-out ]; then
        printf 'before\\t2027-01-09\\t0\\nday1\\t2027-02-08\\t1\\nday15\\t2027-02-22\\t15\\nday27\\t2027-03-06\\t27\\neid\\t2027-03-10\\t0\\nafter\\t2027-03-15\\t0\\n' > "$2"
      fi
      shift
    done
    exit 0 ;;
  audio-focus) exit "${AUDIO_RC:-0}" ;;
  as-of-report) exit "${REPORT_RC:-0}" ;;
esac
exit 0
''',
    'curl': '#!/bin/bash\nexit 0\n',
    'sleep': '#!/bin/bash\nexit 0\n',
}


class RehearsalRunnerTest(unittest.TestCase):
    def run_runner(self, **env_extra):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'e2e').mkdir()
            shutil.copy(Path(__file__).with_name('rehearsal.sh'), root / 'e2e/rehearsal.sh')
            bins = root / 'bin'
            bins.mkdir()
            for name, script in FAKES.items():
                p = bins / name
                p.write_text(script)
                p.chmod(0o755)
            log = root / 'maestro.log'
            env = dict(os.environ, PATH=f'{bins}:{os.environ["PATH"]}',
                       E2E_APKS=str(root / 'apks'), E2E_OUT=str(root / 'out'),
                       MAESTRO_LOG=str(log), ADB_LOG=str(root / 'adb.log'), FAIL_FLOW='')
            env.update(env_extra)
            proc = subprocess.run(['bash', str(root / 'e2e/rehearsal.sh')], env=env,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
            rows = {}
            results = root / 'out/results.tsv'
            for line in (results.read_text().splitlines() if results.exists() else []):
                lineage, name, rc, _seconds, reason = line.split('\t')
                rows[lineage, name] = (rc, reason)
            calls = {}
            for line in (log.read_text().splitlines() if log.exists() else []):
                name, *envs = line.split('|')
                calls[name] = dict(e.split('=', 1) for e in envs)
            expected = root / 'out/rehearsal/expected_stages.txt'
            stages = expected.read_text().split() if expected.exists() else []
            adb = root / 'adb.log'
            self.adb_calls = adb.read_text().splitlines() if adb.exists() else []
            return proc.returncode, rows, calls, stages, proc.stdout + proc.stderr

    def test_the_whole_walk(self):
        rc, rows, calls, expected, output = self.run_runner()
        self.assertEqual(rc, 0, output)
        self.assertEqual(rows['rehearsal', '00_baseline_onboarding'], ('0', ''))
        for s in STAGES:
            # Every stage of every pass ran — none lost to a stdin reader.
            self.assertEqual(rows['rehearsal', f'b_{s}'], ('0', 'informational'))
            for p in ('ar', 'en', 'dk'):
                self.assertEqual(rows['rehearsal', f'{p}_{s}'], ('0', ''), f'{p}_{s}')
        self.assertEqual(rows['sound', '01_recitation'], ('0', ''))
        self.assertEqual(rows['sound', 'audio_focus'], ('0', ''))
        self.assertEqual(rows['sound', '02_still_reciting'], ('0', ''))
        # Only the head's passes are held to «every stage carried its as_of».
        self.assertEqual(expected, [f'{p}_{s}' for p in ('ar', 'en', 'dk') for s in STAGES])

    def test_who_ticks_what(self):
        _, _, calls, _, _ = self.run_runner()
        self.assertEqual(calls['b_day1']['MARK'], 'challenge')
        self.assertEqual(calls['b_day15']['MARK'], 'none')
        self.assertEqual((calls['ar_day1']['MARK'], calls['ar_day15']['MARK'], calls['ar_day27']['MARK']),
                         ('challenge', 'challenge', 'all'))
        for p in ('en', 'dk'):
            for s in STAGES:
                self.assertEqual(calls[f'{p}_{s}']['MARK'], 'none', f'{p}_{s}')
        self.assertEqual(calls['ar_day15']['DAY'], '15')
        self.assertEqual(calls['en_eid']['TAG'], 'after')
        self.assertEqual(calls['dk_after']['VARIANT'], 'ar_dark')
        self.assertEqual(calls['en_before']['UI_LANG'], 'en')
        self.assertEqual(calls['b_day27']['TAG'], 'before')
        # The Play build's tick must still be there after the upgrade.
        self.assertEqual(calls['ar_day1']['EXPECT_BASELINE_MARK'], 'true')
        self.assertEqual(calls['en_day1']['EXPECT_BASELINE_MARK'], 'false')

    def test_the_ticks_sound_between_the_dumps_and_dark_mode_is_undone(self):
        self.run_runner()
        dumps = [i for i, c in enumerate(self.adb_calls) if c == 'shell dumpsys audio']
        self.assertEqual(len(dumps), 4)  # one before, three after
        night = [self.adb_calls.index(c) for c in ('shell cmd uimode night yes', 'shell cmd uimode night no')]
        self.assertTrue(dumps[0] < night[0] < night[1] < dumps[1], self.adb_calls[dumps[0]:dumps[1] + 1])
        self.assertIn('shell input keyevent KEYCODE_F12', self.adb_calls[dumps[0]:dumps[1]])

    def test_no_play_build_tick_no_expectation(self):
        rc, rows, calls, _, output = self.run_runner(FAIL_FLOW='b_day1')
        self.assertEqual(rc, 0, output)  # the Play build's walk is informational
        self.assertEqual(rows['rehearsal', 'b_day1'], ('1', 'informational'))
        self.assertEqual(calls['ar_day1']['EXPECT_BASELINE_MARK'], 'false')

    def test_a_head_stage_fails_the_run_and_the_walk_goes_on(self):
        rc, rows, _, _, output = self.run_runner(FAIL_FLOW='en_eid')
        self.assertEqual(rc, 1)
        self.assertEqual(rows['rehearsal', 'en_eid'], ('1', ''))
        self.assertEqual(rows['rehearsal', 'en_after'], ('0', ''))
        self.assertIn('::error title=Rehearsal rehearsal/en_eid::', output)

    def test_no_as_of_no_emulator(self):
        rc, rows, calls, _, output = self.run_runner(PREFLIGHT_RC='1')
        self.assertEqual(rc, 1)
        self.assertEqual(calls, {})
        self.assertIn('the candidate does not honour as_of', output)

    def test_an_inconclusive_sound_check_is_not_a_pass(self):
        rc, rows, _, _, _ = self.run_runner(AUDIO_RC='2')
        self.assertEqual(rc, 1)
        self.assertEqual(rows['sound', 'audio_focus'], ('2', ''))

    def test_a_stage_without_its_as_of_fails(self):
        rc, _, _, _, _ = self.run_runner(REPORT_RC='1')
        self.assertEqual(rc, 1)

    def test_no_play_build_still_runs_the_sound_check_on_a_fresh_head(self):
        rc, rows, calls, expected, _ = self.run_runner(FAIL_FLOW='00_baseline_onboarding')
        self.assertEqual(rc, 1)
        for p in ('b_', 'ar_', 'en_', 'dk_'):
            self.assertEqual(rows['rehearsal', f'{p}stages'], ('skip', 'Play-build onboarding failed'))
        self.assertEqual(rows['sound', '00_head_onboarding'], ('0', ''))
        self.assertEqual(rows['sound', 'audio_focus'], ('0', ''))
        self.assertEqual(expected, [])


if __name__ == '__main__':
    unittest.main()
