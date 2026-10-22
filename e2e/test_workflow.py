"""Parse the workflow and execute its final verdict without builds or devices."""
import contextlib
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

import yaml


WORKFLOW = Path(__file__).resolve().parent.parent / '.github/workflows/mobile-e2e.yml'
HEAVY = {'keystore', 'build', 'build_rehearsal', 'e2e', 'rehearsal'}
APP_ONLY = {'build', 'e2e'}                                # the journeys' half
CANDIDATE = {'keystore', 'build_rehearsal', 'rehearsal'}   # the rehearsal's half
STATUSES = ('success', 'failure', 'cancelled', 'skipped')


def load_workflow():
    # BaseLoader preserves GitHub's `on` key (YAML 1.1 treats it as boolean).
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


class DeliveryWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = load_workflow()

    def gate(self):
        jobs = self.workflow['jobs']
        self.assertIn('delivery_gate', jobs, 'Every main PR needs a final delivery verdict')
        return jobs['delivery_gate']

    def test_every_main_pr_and_manual_dispatch_trigger(self):
        events = self.workflow['on']
        self.assertEqual(events['pull_request']['branches'], ['main'])
        # A workflow-level filter would leave the required gate pending forever;
        # what to run is decided inside, by job `changes`.
        for filter_name in ('paths', 'paths-ignore', 'types'):
            self.assertNotIn(filter_name, events['pull_request'])
        self.assertIn('baseline_ref', events['workflow_dispatch']['inputs'])

    def test_gate_has_stable_name_and_waits_for_every_job(self):
        gate = self.gate()
        self.assertEqual(gate['name'], 'Mobile delivery gate')
        self.assertEqual(gate['if'], '${{ always() }}')
        self.assertNotIn('needs.changes', gate['if'])
        self.assertEqual(set(gate['needs']), HEAVY | {'changes'})
        self.assertEqual(set(self.workflow['jobs']), HEAVY | {'changes', 'delivery_gate'})
        jobs = self.workflow['jobs']
        self.assertNotIn('needs', jobs['changes'])
        self.assertNotIn('if', jobs['changes'])
        self.assertEqual(jobs['keystore']['needs'], 'changes')
        self.assertEqual(jobs['build']['needs'], ['changes', 'keystore'])
        self.assertEqual(jobs['build_rehearsal']['needs'], ['changes', 'keystore'])
        self.assertEqual(jobs['e2e']['needs'], ['changes', 'build'])
        self.assertEqual(jobs['rehearsal']['needs'], ['changes', 'build_rehearsal'])

    def test_heavy_jobs_run_on_the_change_verdict_only(self):
        # No status function in these conditions: GitHub's implicit success()
        # still applies, so a failed dependency skips the job as before.
        jobs = self.workflow['jobs']
        for job in HEAVY:
            want = 'app' if job in APP_ONLY else 'candidate'
            self.assertEqual(jobs[job]['if'], f"needs.changes.outputs.{want} == 'true'", job)
        self.assertEqual(jobs['changes']['outputs'], {
            'app': '${{ steps.classify.outputs.app }}',
            'candidate': '${{ steps.classify.outputs.candidate }}',
        })

    def test_the_two_build_jobs_build_alike(self):
        jobs = self.workflow['jobs']
        build, rehearsal = jobs['build'], jobs['build_rehearsal']
        for key in ('name', 'runs-on', 'timeout-minutes', 'defaults', 'steps'):
            self.assertEqual(build[key], rehearsal[key], key)
        self.assertEqual(build['strategy']['fail-fast'], rehearsal['strategy']['fail-fast'])
        variants = lambda job: [m['variant'] for m in jobs[job]['strategy']['matrix']['include']]
        self.assertEqual(variants('build'), ['head', 'baseline'])
        self.assertEqual(variants('build_rehearsal'), ['rehearsal-head', 'rehearsal-baseline'])

    def test_jobs_are_hosted_and_failures_are_not_allowed(self):
        for job_id, job in self.workflow['jobs'].items():
            self.assertEqual(job['runs-on'], 'ubuntu-latest', job_id)
            self.assertNotEqual(job.get('continue-on-error'), 'true', job_id)
            for step in job['steps']:
                self.assertNotEqual(step.get('continue-on-error'), 'true', job_id)

    def verdict(self, results):
        gate = self.gate()
        self.assertEqual(len(gate['steps']), 1)
        step = gate['steps'][0]
        self.assertEqual(step['env']['NEEDS_JSON'], '${{ toJSON(needs) }}')
        self.assertNotIn('if', step)
        env = dict(os.environ, NEEDS_JSON=json.dumps(results))
        return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', step['run']],
                              env=env, capture_output=True, text=True, timeout=5)

    @staticmethod
    def needs(app, candidate, statuses):
        results = {'changes': {'result': 'success',
                               'outputs': {'app': app, 'candidate': candidate}}}
        results.update({job: {'result': s} for job, s in statuses.items()})
        return results

    def verdict_in_process(self, results):
        """The gate's Python, run here: 4^5 combinations × 4 verdicts through
        bash would take minutes. The bash path is checked on samples below."""
        run = self.gate()['steps'][0]['run']
        body = textwrap.dedent(run.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0])
        if not hasattr(self, '_gate_code'):
            self._gate_code = compile(body, 'delivery_gate', 'exec')
        saved = os.environ.get('NEEDS_JSON')
        os.environ['NEEDS_JSON'] = json.dumps(results)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(self._gate_code, {'__name__': '__main__'})
            return 0
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 1
        finally:
            if saved is None:
                os.environ.pop('NEEDS_JSON', None)
            else:
                os.environ['NEEDS_JSON'] = saved

    def assert_green_exactly_when(self, app, candidate, expected):
        """Every combination of the five jobs' results; green only for `expected`."""
        for combo in itertools.product(STATUSES, repeat=len(HEAVY)):
            statuses = dict(zip(sorted(HEAVY), combo))
            rc = self.verdict_in_process(self.needs(app, candidate, statuses))
            if rc != (0 if statuses == expected else 1):
                self.fail(f'app={app} candidate={candidate} {statuses}: exit {rc}')
        # The real step (bash + heredoc) agrees on the green case and its
        # nearest reds.
        samples = [expected] + [dict(expected, **{job: s}) for job in sorted(HEAVY)
                                for s in STATUSES if s != expected[job]][:6]
        for statuses in samples:
            with self.subTest(app=app, candidate=candidate, statuses=statuses):
                proc = self.verdict(self.needs(app, candidate, statuses))
                self.assertEqual(proc.returncode, 0 if statuses == expected else 1,
                                 proc.stdout + proc.stderr)

    def test_app_change_is_green_only_when_all_succeed(self):
        everything = {job: 'success' for job in HEAVY}
        self.assert_green_exactly_when('true', 'true', everything)
        # app=true implies the rehearsal half even if candidate said false.
        self.assert_green_exactly_when('true', 'false', everything)

    def test_backend_change_needs_the_rehearsal_and_skips_the_journeys(self):
        expected = {job: ('skipped' if job in APP_ONLY else 'success') for job in HEAVY}
        self.assert_green_exactly_when('false', 'true', expected)

    def test_untouched_app_is_green_only_when_everything_skipped(self):
        self.assert_green_exactly_when('false', 'false', {job: 'skipped' for job in HEAVY})

    def test_a_broken_change_detection_cannot_be_green(self):
        # All five skipped is green for "neither" — so the verdict itself must
        # be present, explicit and from a successful job.
        skipped = {job: {'result': 'skipped'} for job in HEAVY}
        success = {job: {'result': 'success'} for job in HEAVY}
        broken = [
            {'result': status, 'outputs': {'app': 'false', 'candidate': 'false'}}
            for status in ('failure', 'cancelled', 'skipped')
        ] + [
            {'result': 'success', 'outputs': {}},
            {'result': 'success', 'outputs': {'app': '', 'candidate': ''}},
            {'result': 'success', 'outputs': {'app': 'false'}},
            {'result': 'success', 'outputs': {'app': 'yes', 'candidate': 'false'}},
            {'result': 'success'},
            {},
            None,
        ]
        for changes in broken:
            for jobs in (skipped, success):
                results = dict(jobs)
                if changes is not None:
                    results['changes'] = changes
                with self.subTest(changes=changes, jobs=jobs['build']['result']):
                    self.assertEqual(self.verdict(results).returncode, 1)

    def test_missing_result_cannot_be_green(self):
        for app, candidate, expected in (('true', 'true', 'success'), ('false', 'false', 'skipped')):
            for job in sorted(HEAVY):
                results = self.needs(app, candidate, {name: expected for name in HEAVY})
                del results[job]
                with self.subTest(app=app, missing=job):
                    self.assertEqual(self.verdict(results).returncode, 1)
                results[job] = {}
                with self.subTest(app=app, empty=job):
                    self.assertEqual(self.verdict(results).returncode, 1)


class ChangeDetectionTest(unittest.TestCase):
    """Job `changes` executed on real file lists. Too narrow and an app change
    ships untested; too wide and every docs PR waits two hours."""

    @classmethod
    def setUpClass(cls):
        steps = load_workflow()['jobs']['changes']['steps']
        found = [s for s in steps if s.get('id') == 'classify']
        assert len(found) == 1, 'classify step not found'
        cls.script = found[0]['run']
        listing = [s for s in steps if s.get('name') == "List the PR's files"]
        assert len(listing) == 1, 'listing step not found'
        cls.listing = listing[0]

    def classify(self, files, event='pull_request'):
        with tempfile.TemporaryDirectory() as d:
            listed, out = Path(d, 'files.txt'), Path(d, 'out')
            if files is not None:
                listed.write_text(''.join(f + '\n' for f in files), encoding='utf-8')
            out.write_text('')
            env = {k: v for k, v in os.environ.items() if k != 'GITHUB_STEP_SUMMARY'}
            env.update(EVENT=event, FILES=str(listed), GITHUB_OUTPUT=str(out))
            proc = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.script],
                                  env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            got = dict(line.split('=', 1) for line in out.read_text().splitlines())
        self.assertEqual(set(got), {'app', 'candidate'})
        return got['app'], got['candidate']

    def assert_reaches(self, files, app, candidate, event='pull_request'):
        with self.subTest(files=files, event=event):
            want = ('true' if app else 'false', 'true' if candidate else 'false')
            self.assertEqual(self.classify(files, event), want)

    def test_the_app_and_its_tooling_run_everything(self):
        for path in ('mobile/lib/main.dart', 'mobile/pubspec.yaml', 'mobile/pubspec.lock',
                     'mobile/lib/l10n/app_ar.arb', 'mobile/assets/data/stories_en.json',
                     'mobile/android/app/build.gradle.kts', 'mobile/android/app/proguard-rules.pro',
                     'mobile/tool/story_art.py', 'e2e/run.sh', 'e2e/flows/01_onboarding.yaml',
                     'e2e/e2e_tool.py', 'frontend/icons/icon-512.png',
                     '.github/workflows/mobile-e2e.yml', '.github/workflows/e2e-avd-cache.yml'):
            self.assert_reaches([path], app=True, candidate=True)
        self.assert_reaches(['docs/README.md', 'mobile/lib/main.dart'], app=True, candidate=True)

    def test_what_the_candidate_image_serves_runs_the_rehearsal(self):
        for path in ('backend/app/main.py', 'backend/Dockerfile', 'backend/static/child_mode/index.html',
                     'knowledge_base/curriculum/programs/ramadan_family.json', 'docs/stories.json',
                     'docs/lesson_index.json', 'docs/privacy-policy.md', '.well-known/assetlinks.json',
                     '.github/ci/requirements-prod.lock', '.dockerignore'):
            self.assert_reaches([path], app=False, candidate=True)

    def test_recent_non_app_prs(self):
        # #160 (landing in English): backend code, so the rehearsal.
        self.assert_reaches(['backend/app/routers/web.py', 'backend/app/services/attribution.py',
                             'backend/tests/test_landing_language.py', 'frontend/cinematic.en.html',
                             'frontend/cinematic.html'], app=False, candidate=True)
        # #162 (preacher codes) and #163 (social links): nothing the app reaches.
        self.assert_reaches(['backend/tests/test_campaign_report.py', 'docs/marketing/campaign_codes.md',
                             'ops/scripts/campaign_report.py'], app=False, candidate=False)
        self.assert_reaches(['backend/tests/test_cinematic_landing.py', 'frontend/cinematic.html',
                             'docs/marketing/2027-01-ramadan-preachers/DA03_jasem_al_mutawa/infographic.png'],
                            app=False, candidate=False)

    def test_prefixes_are_whole_directories(self):
        for path in ('mobile.md', 'mobile-notes/x.dart', 'e2e.md', 'backend-notes.md', 'docsx/a.json',
                     'frontend/iconsets/a.png', 'scripts/build.sh', 'remotion-reels/src/a.tsx',
                     'knowledge_base_markdown/a.md', '.github/workflows/backend.yml', 'README.md'):
            self.assert_reaches([path], app=False, candidate=False)

    def test_a_rename_counts_both_names(self):
        # The listing step emits previous_filename too: moving a file out of
        # mobile/ changes the app.
        self.assertIn('previous_filename', self.listing['run'])
        self.assert_reaches(['docs/old_screen.dart', 'mobile/lib/old_screen.dart'], app=True, candidate=True)

    def test_doubt_runs_the_full_suite(self):
        self.assert_reaches([], app=True, candidate=True)
        self.assert_reaches([f'docs/marketing/{i}.md' for i in range(3000)], app=True, candidate=True)
        self.assert_reaches([f'docs/marketing/{i}.md' for i in range(2999)], app=False, candidate=False)
        for event in ('workflow_dispatch', 'push', 'schedule'):
            self.assert_reaches(None, app=True, candidate=True, event=event)

    def test_a_missing_list_fails_the_job(self):
        # A pull_request without its list must not read as "nothing changed".
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, EVENT='pull_request', FILES=str(Path(d, 'absent')),
                       GITHUB_OUTPUT=str(Path(d, 'out')))
            proc = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.script],
                                  env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(proc.returncode, 0)

    def test_the_listing_only_reads(self):
        job = load_workflow()['jobs']['changes']
        self.assertEqual(job['permissions'], {'contents': 'read', 'pull-requests': 'read'})
        self.assertEqual(self.listing['if'], "github.event_name == 'pull_request'")
        self.assertIn('--paginate', self.listing['run'])
        self.assertIn('exit 1', self.listing['run'])


class UnitTestStepTest(unittest.TestCase):
    """The tooling's tests must never annotate the E2E job: a test of the
    gate's "capture failed" path once put that error on every run, and it was
    read as a flaky logcat capture."""

    @classmethod
    def setUpClass(cls):
        workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        steps = [s for s in workflow['jobs']['e2e']['steps']
                 if s.get('name') == 'Unit-test the E2E tooling']
        assert len(steps) == 1, 'unit-test step not found'
        cls.script = steps[0]['run']

    def run_step(self, unittest_rc):
        """The step's script with python3 stubbed: the "tests" leak a command."""
        with tempfile.TemporaryDirectory() as d:
            stub = Path(d) / 'python3'
            stub.write_text('#!/bin/bash\n'
                            'if [ "$2" = unittest ]; then echo "::error::leaked by a test"; '
                            f'exit {unittest_rc}; fi\nexit 0\n')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}")
            return subprocess.run(['bash', '-e', '-c', self.script], env=env,
                                  capture_output=True, text=True, timeout=10)

    def test_commands_are_paused_around_the_tests(self):
        proc = self.run_step(0)
        lines = proc.stdout.splitlines()
        leak = lines.index('::error::leaked by a test')
        stops = [i for i, l in enumerate(lines) if l.startswith('::stop-commands::')]
        self.assertEqual(len(stops), 1, proc.stdout)
        token = lines[stops[0]].split('::stop-commands::', 1)[1]
        self.assertTrue(token)
        self.assertLess(stops[0], leak)
        self.assertIn(f'::{token}::', lines[leak + 1:], 'commands must resume after the tests')
        self.assertEqual(proc.returncode, 0)

    def test_failing_tests_still_fail_the_step(self):
        for rc in (1, 5):
            with self.subTest(rc=rc):
                proc = self.run_step(rc)
                self.assertEqual(proc.returncode, rc, proc.stdout + proc.stderr)
                self.assertTrue(proc.stdout.rstrip().splitlines()[-1].startswith('::e2e-unit-tests-'),
                                'commands must resume even when the tests fail')

    def test_the_tooling_tests_leak_no_workflow_command(self):
        # The pause is the backstop; the tests themselves should not need it.
        e2e = Path(__file__).resolve().parent
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'test_e2e_tool', 'test_run', 'test_rehearsal', 'test_install_system_image'],
                              cwd=e2e, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        leaked = [l for l in (proc.stdout + proc.stderr).splitlines() if l.startswith('::')]
        self.assertEqual(leaked, [])


class AvdCacheTest(unittest.TestCase):
    """The AVD cache mobile-e2e.yml restores must exist on main: a PR-scoped
    cache serves only its own PR, so every new PR missed it (2026-10-08)."""

    @classmethod
    def setUpClass(cls):
        load = lambda p: yaml.load(p.read_text(), Loader=yaml.BaseLoader)
        cls.e2e = load(WORKFLOW)
        cls.warm = load(WORKFLOW.parent / 'e2e-avd-cache.yml')

    @staticmethod
    def step(steps, name):
        found = [s for s in steps if s.get('name') == name]
        assert len(found) == 1, name
        return found[0]

    def test_same_key_and_image(self):
        for var in ('AVD_CACHE_KEY', 'SYSTEM_IMAGE'):
            self.assertEqual(self.warm['env'][var], self.e2e['env'][var], var)

    def test_warm_creates_exactly_the_avd_the_journeys_restore(self):
        e2e_steps, warm_steps = self.e2e['jobs']['e2e']['steps'], self.warm['jobs']['avd']['steps']
        name = 'Create the AVD and a boot snapshot'
        self.assertEqual(self.step(warm_steps, name)['with'], self.step(e2e_steps, name)['with'])
        restore = self.step(e2e_steps, 'Restore the AVD')['with']
        lookup = self.step(warm_steps, 'Is the AVD cached already?')['with']
        save = self.step(warm_steps, 'Save the AVD on main')['with']
        self.assertEqual(lookup['lookup-only'], 'true')
        for w in (lookup, save):
            self.assertEqual((w['path'], w['key']), (restore['path'], restore['key']))

    def test_warm_runs_on_main_and_never_saves_from_a_pr(self):
        on = self.warm['on']
        self.assertEqual(on['push']['branches'], ['main'])
        self.assertIn('.github/workflows/mobile-e2e.yml', on['push']['paths'])
        self.assertIn('schedule', on)
        self.assertIn('workflow_dispatch', on)
        save = self.step(self.warm['jobs']['avd']['steps'], 'Save the AVD on main')
        self.assertIn("github.event_name != 'pull_request'", save['if'])

    def test_system_image_is_installed_before_any_emulator_step(self):
        for workflow, job in ((self.e2e, 'e2e'), (self.warm, 'avd')):
            steps = workflow['jobs'][job]['steps']
            names = [s.get('name') or s.get('uses', '') for s in steps]
            install = names.index('Install the system image (retried, verified)')
            self.assertIn('e2e/install_system_image.sh "$SYSTEM_IMAGE"', steps[install]['run'])
            runners = [i for i, s in enumerate(steps)
                       if s.get('uses', '').startswith('reactivecircus/android-emulator-runner@')]
            self.assertTrue(runners)
            self.assertLess(install, min(runners), job)
        e2e_install = self.step(self.e2e['jobs']['e2e']['steps'], 'Install the system image (retried, verified)')
        self.assertNotIn('if', e2e_install, 'the journeys step needs the image on a cache hit too')


class GalleryArtifactTest(unittest.TestCase):
    """The معرض قبل/بعد must ship as one downloadable artifact, uploaded even
    from a red run (the shots are the evidence), and never gate anything."""

    @classmethod
    def setUpClass(cls):
        cls.e2e = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)['jobs']['e2e']

    def test_gallery_artifact_is_uploaded_always_and_warn_only(self):
        uploads = [s for s in self.e2e['steps']
                   if s.get('uses', '').startswith('actions/upload-artifact@')]
        gallery = [s for s in uploads if s['with'].get('name') == 'e2e-gallery']
        self.assertEqual(len(gallery), 1, 'exactly one e2e-gallery upload')
        step = gallery[0]
        self.assertEqual(step['if'], 'always()')
        self.assertEqual(step['with']['if-no-files-found'], 'warn',
                         'a run with no gallery shots still uploads the rest')
        self.assertEqual(step['with']['path'], '${{ env.E2E_OUT }}/gallery')
        self.assertGreaterEqual(int(step['with']['retention-days']), 14)

    def test_the_emulator_job_allows_the_gallery_lineage_time(self):
        # 75 covered the 13 journeys; the gallery lineage (a third onboarding
        # and six shoots) needs the headroom the workflow now grants.
        self.assertGreaterEqual(int(self.e2e['timeout-minutes']), 90)


class RehearsalJobTest(unittest.TestCase):
    """Job `rehearsal` (the Ramadan rehearsal, gate G2, and the sound ×
    recitation check) brings its own server: it must never point an APK at
    production, never ship its knobs in another build, and drive exactly the
    emulator the journeys drive."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        cls.job = cls.workflow['jobs']['rehearsal']
        cls.matrix = {m['variant']: m for job in ('build', 'build_rehearsal')
                      for m in cls.workflow['jobs'][job]['strategy']['matrix']['include']}

    def step(self, name):
        found = [s for s in self.job['steps'] if s.get('name') == name]
        self.assertEqual(len(found), 1, name)
        return found[0]

    def test_needs_the_builds_and_reads_packages_only(self):
        self.assertEqual(self.job['needs'], ['changes', 'build_rehearsal'])
        self.assertEqual(self.job['permissions'], {'contents': 'read', 'packages': 'read'})

    def test_the_journey_apks_carry_no_define_at_all(self):
        # head/baseline are the release gate: built exactly as for Play.
        for variant in ('head', 'baseline'):
            self.assertEqual(self.matrix[variant]['dart_defines'], '', variant)

    def test_the_rehearsal_apks_talk_to_the_runner_not_production(self):
        for variant in ('rehearsal-head', 'rehearsal-baseline'):
            defines = self.matrix[variant]['dart_defines'].split()
            self.assertIn('--dart-define=API_BASE_URL=http://10.0.2.2:8090', defines, variant)
        self.assertEqual(self.matrix['rehearsal-head']['ref'], self.matrix['head']['ref'])
        # The Play build (v1.0.72+117) unless a manual run names another.
        self.assertIn('c30870145dda59acffd63b68784ad6f9e0974ca5', self.matrix['rehearsal-baseline']['ref'])
        self.assertIn('inputs.rehearsal_baseline_ref', self.matrix['rehearsal-baseline']['ref'])
        downloaded = sorted(s['with']['name'] for s in self.job['steps']
                            if s.get('uses', '').startswith('actions/download-artifact@'))
        self.assertEqual(downloaded, ['e2e-apk-rehearsal-baseline', 'e2e-apk-rehearsal-head'])
        self.assertNotIn('tg-api.alsaba.cloud', WORKFLOW.read_text().split('  rehearsal:\n', 1)[1])

    def test_the_build_step_passes_the_matrix_defines(self):
        build = [s for s in self.workflow['jobs']['build']['steps']
                 if s.get('name', '').startswith('Build the release APK')][0]
        self.assertEqual(build['env']['DART_DEFINES'], '${{ matrix.dart_defines }}')
        self.assertTrue(build['run'].rstrip().endswith('$DART_DEFINES'))

    def test_the_key_probe_is_only_in_the_rehearsal_head(self):
        for variant, entry in self.matrix.items():
            has = 'E2E_PROBES' in entry['dart_defines']
            self.assertEqual(has, variant == 'rehearsal-head', variant)
        for wf in sorted(WORKFLOW.parent.glob('*.yml')):
            if wf != WORKFLOW:
                self.assertNotIn('E2E_PROBES', wf.read_text(), wf.name)

    def test_the_as_of_switch_lives_in_the_container_on_loopback(self):
        start = self.step('Start the candidate with PROGRAMS_AS_OF_ENABLED=1 (runner loopback only)')['run']
        self.assertIn('-p 127.0.0.1:8091:8000', start)
        self.assertIn('-e PROGRAMS_AS_OF_ENABLED', start)
        self.assertNotIn('--env-file', start)
        text = WORKFLOW.read_text()
        self.assertEqual(text.count('PROGRAMS_AS_OF_ENABLED=1 \\'), 1,
                         'the switch is set in exactly one place: the candidate container')
        self.assertNotIn('ssh ', text)

    def test_the_candidate_is_built_here_and_pushed_nowhere(self):
        run = self.step('Build the candidate — the PR head\'s backend image')['run']
        self.assertIn('--load -t tg-rehearsal:ci', run)
        self.assertNotIn('--push', run)
        self.assertNotIn('cache-to', run)
        self.assertIn('--password-stdin', run)

    def test_same_emulator_as_the_journeys(self):
        e2e = {s.get('name'): s for s in self.workflow['jobs']['e2e']['steps']}
        mine = {s.get('name'): s for s in self.job['steps']}
        self.assertEqual(mine['Create the AVD and a boot snapshot']['with'],
                         e2e['Create the AVD and a boot snapshot']['with'])
        self.assertEqual(mine['Restore the AVD']['with'], e2e['Restore the AVD']['with'])
        run, journeys = mine['Run the rehearsal and the sound check']['with'], e2e['Run the journeys']['with']
        self.assertEqual({k: v for k, v in run.items() if k != 'script'},
                         {k: v for k, v in journeys.items() if k != 'script'})
        self.assertEqual(run['script'], 'bash e2e/rehearsal.sh')
        names = [s.get('name') or s.get('uses', '') for s in self.job['steps']]
        install = names.index('Install the system image (retried, verified)')
        runners = [i for i, s in enumerate(self.job['steps'])
                   if s.get('uses', '').startswith('reactivecircus/android-emulator-runner@')]
        self.assertLess(install, min(runners))

    def test_evidence_is_uploaded_even_from_a_red_run(self):
        uploads = [s for s in self.job['steps'] if s.get('uses', '').startswith('actions/upload-artifact@')]
        self.assertEqual([s['with']['name'] for s in uploads], ['e2e-rehearsal'])
        self.assertEqual(uploads[0]['if'], 'always()')
        for part in ('/gallery', '/rehearsal', '/screens', '/logcat', '/summary.md'):
            self.assertIn(part, uploads[0]['with']['path'])
        self.assertEqual(self.step('Candidate backend log')['if'], 'always()')
