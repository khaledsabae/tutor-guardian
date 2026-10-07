"""Execute only the upload shell with a fake python; never build or upload."""
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT_VERSION = yaml.safe_load((ROOT / 'mobile/pubspec.yaml').read_text())['version']
NOTES_FILE = f'docs/release_notes/{CURRENT_VERSION}.json'


class ReleasePlayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load((ROOT / '.github/workflows/release-play.yml').read_text())
        cls.upload = next(s for s in cls.workflow['jobs']['release']['steps']
                          if s['name'].startswith('Upload to Google Play'))

    def run_upload(self, notes, *, version=None, matching_notes=False, expect_failure=False,
                   missing_current_notes=False):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            workspace = temp / 'repo'
            (workspace / 'mobile').mkdir(parents=True)
            (workspace / 'docs/release_notes').mkdir(parents=True)
            pubspec = (ROOT / 'mobile/pubspec.yaml').read_text()
            if version is not None:
                pubspec = '\n'.join('version: ' + version if line.startswith('version:') else line
                                    for line in pubspec.splitlines())
            (workspace / 'mobile/pubspec.yaml').write_text(pubspec)
            if missing_current_notes:
                previous_notes = [path for path in (ROOT / 'docs/release_notes').glob('*.json')
                                  if path.name != Path(NOTES_FILE).name]
                self.assertTrue(previous_notes, 'Negative case requires older committed notes')
                for path in previous_notes:
                    shutil.copy(path, workspace / 'docs/release_notes' / path.name)
                self.assertFalse((workspace / NOTES_FILE).exists())
            else:
                shutil.copy(ROOT / NOTES_FILE, workspace / NOTES_FILE)
            if matching_notes:
                (workspace / f'docs/release_notes/{version}.json').write_text(
                    json.dumps({'ar': 'جديد', 'en-US': 'New release'}))
            fake = temp / 'python3'
            fake.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                            'if sys.argv[1] == "-":\n'
                            '    os.execv("/usr/bin/python3", ["python3"] + sys.argv[1:])\n'
                            'if sys.argv[1] == "scripts/play_upload.py":\n'
                            '    open(os.environ["CAPTURE"], "w").write(json.dumps(sys.argv[2:]))\n')
            fake.chmod(0o755)
            # Use synthetic credentials, never read repository secrets or user env.
            env = dict(PATH=f'{temp}:/usr/bin:/bin', RUNNER_TEMP=str(temp),
                       PLAY_SERVICE_ACCOUNT_JSON='{}', TRACK='internal',
                       ROLLOUT='1.0', NOTES=notes, CAPTURE=str(temp / 'args.json'))
            result = subprocess.run(['bash', '-e', '-c', self.upload['run']],
                                    cwd=workspace, env=env, capture_output=True, text=True)
            if expect_failure:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'docs/release_notes/{version}.json', result.stderr)
                self.assertIn('Missing release notes', result.stderr)
                self.assertFalse((temp / 'args.json').exists())
                self.assertFalse((temp / 'play_sa.json').exists())
                return None
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((workspace / 'COPY_RELEASE_INJECTION').exists())
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

    def test_missing_current_notes_rejects_previous_release_fallback(self):
        self.run_upload('', version=CURRENT_VERSION, expect_failure=True,
                        missing_current_notes=True)

    def test_changed_pubspec_requires_matching_notes_not_stale_file(self):
        self.run_upload('', version='2.0.0+999', expect_failure=True)

    def test_changed_pubspec_selects_exact_matching_notes(self):
        args = self.run_upload('', version='2.0.0+999', matching_notes=True)
        self.assertEqual(args[args.index('--notes-file') + 1],
                         'docs/release_notes/2.0.0+999.json')

    def test_override_works_without_matching_version_notes(self):
        args = self.run_upload('Custom release', version='2.0.0+999')
        self.assertEqual(args[args.index('--notes') + 1], 'Custom release')
        self.assertNotIn('--notes-file', args)

    def test_inputs_enter_shell_only_through_env(self):
        self.assertNotIn('${{', self.upload['run'])
        self.assertEqual(self.upload['env']['NOTES'], '${{ inputs.notes }}')
        subprocess.run(['bash', '-n'], input=self.upload['run'], text=True, check=True)
