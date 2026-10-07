"""Execute only the upload shell with a fake python; never build or upload."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
NOTES_FILE = 'docs/release_notes/1.0.68+113.json'


class ReleasePlayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load((ROOT / '.github/workflows/release-play.yml').read_text())
        cls.upload = next(s for s in cls.workflow['jobs']['release']['steps']
                          if s['name'].startswith('Upload to Google Play'))

    def run_upload(self, notes):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake = temp / 'python3'
            fake.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                            'if sys.argv[1] == "scripts/play_upload.py":\n'
                            '    open(os.environ["CAPTURE"], "w").write(json.dumps(sys.argv[2:]))\n')
            fake.chmod(0o755)
            # Use synthetic credentials, never read repository secrets or user env.
            env = dict(PATH=f'{temp}:/usr/bin:/bin', RUNNER_TEMP=str(temp),
                       PLAY_SERVICE_ACCOUNT_JSON='{}', TRACK='internal',
                       ROLLOUT='1.0', NOTES=notes, CAPTURE=str(temp / 'args.json'))
            result = subprocess.run(['bash', '-e', '-c', self.upload['run']],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((ROOT / 'COPY_RELEASE_INJECTION').exists())
            return json.loads((temp / 'args.json').read_text())

    def test_dispatch_defaults_to_committed_bilingual_notes(self):
        dispatch = self.workflow.get('on', self.workflow.get(True))['workflow_dispatch']
        self.assertEqual(dispatch['inputs']['notes']['default'], '')
        args = self.run_upload('')
        self.assertIn('--notes-file', args)
        self.assertEqual(args[args.index('--notes-file') + 1], NOTES_FILE)
        self.assertNotIn('--notes', args)
        notes = json.loads((ROOT / NOTES_FILE).read_text())
        self.assertEqual(set(notes), {'ar', 'en-US'})
        self.assertTrue(all(notes.values()))

    def test_empty_notes_use_notes_file(self):
        args = self.run_upload('')
        self.assertIn('--notes-file', args)
        self.assertNotIn('--notes', args)

    def test_explicit_override_is_literal_and_keeps_legacy_notes(self):
        notes = 'ملاحظات "خاصة"\n$(touch COPY_RELEASE_INJECTION) `touch COPY_RELEASE_INJECTION` $HOME; *'
        args = self.run_upload(notes)
        self.assertEqual(args[args.index('--notes') + 1], notes)
        self.assertNotIn('--notes-file', args)
        self.assertEqual(args[args.index('--track') + 1], 'internal')
        self.assertEqual(args[args.index('--rollout') + 1], '1.0')

    def test_inputs_enter_shell_only_through_env(self):
        self.assertNotIn('${{', self.upload['run'])
        self.assertEqual(self.upload['env']['NOTES'], '${{ inputs.notes }}')
        subprocess.run(['bash', '-n'], input=self.upload['run'], text=True, check=True)
