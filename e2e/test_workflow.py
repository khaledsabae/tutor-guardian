"""Parse the workflow and execute its final verdict without builds or devices."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


WORKFLOW = Path(__file__).resolve().parent.parent / '.github/workflows/mobile-e2e.yml'
MANDATORY = {'keystore', 'build', 'e2e'}


class DeliveryWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # BaseLoader preserves GitHub's `on` key (YAML 1.1 treats it as boolean).
        cls.workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    def gate(self):
        jobs = self.workflow['jobs']
        self.assertIn('delivery_gate', jobs, 'Every main PR needs a final delivery verdict')
        return jobs['delivery_gate']

    def test_every_main_pr_and_manual_dispatch_trigger(self):
        events = self.workflow['on']
        self.assertEqual(events['pull_request']['branches'], ['main'])
        for filter_name in ('paths', 'paths-ignore', 'types'):
            self.assertNotIn(filter_name, events['pull_request'])
        self.assertIn('baseline_ref', events['workflow_dispatch']['inputs'])

    def test_gate_has_stable_name_and_waits_for_all_mandatory_jobs(self):
        gate = self.gate()
        self.assertEqual(gate['name'], 'Mobile delivery gate')
        self.assertEqual(gate['if'], '${{ always() }}')
        self.assertEqual(set(gate['needs']), MANDATORY)
        self.assertTrue(MANDATORY.issubset(self.workflow['jobs']))
        self.assertEqual(self.workflow['jobs']['build']['needs'], 'keystore')
        self.assertEqual(self.workflow['jobs']['e2e']['needs'], 'build')

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

    def test_only_all_success_is_green(self):
        for statuses in itertools.product(('success', 'failure', 'cancelled', 'skipped'), repeat=3):
            results = {job: {'result': status} for job, status in zip(sorted(MANDATORY), statuses)}
            with self.subTest(statuses=statuses):
                proc = self.verdict(results)
                expected = 0 if all(s == 'success' for s in statuses) else 1
                self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)

    def test_missing_result_cannot_be_green(self):
        for job in sorted(MANDATORY):
            results = {name: {'result': 'success'} for name in MANDATORY}
            del results[job]
            with self.subTest(missing=job):
                self.assertEqual(self.verdict(results).returncode, 1)
            results[job] = {}
            with self.subTest(empty=job):
                self.assertEqual(self.verdict(results).returncode, 1)


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
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'test_e2e_tool', 'test_run'],
                              cwd=e2e, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        leaked = [l for l in (proc.stdout + proc.stderr).splitlines() if l.startswith('::')]
        self.assertEqual(leaked, [])
