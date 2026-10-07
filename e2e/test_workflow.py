"""Parse the workflow and execute its final verdict without builds or devices."""
import itertools
import json
import os
from pathlib import Path
import subprocess
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
