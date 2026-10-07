"""Exact-artifact production publication; fake Play transport, no signing/network."""
import importlib.util
from pathlib import Path
import sys
import hashlib
import json
import tempfile
import types
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from test_release_play_validate import Play as BasePlay


class Play(BasePlay):
    def __init__(self, existing=None, fail_at=None):
        super().__init__(fail_at)
        self.existing = existing or []

    def list(self, **kwargs):
        return self.request('list', {'bundles': self.existing}, **kwargs)

    def commit(self, **kwargs):
        return self.request('commit', {'id': 'our-edit'}, **kwargs)


class PublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'scripts/release_play_publish.py'
        spec = importlib.util.spec_from_file_location('release_play_publish', path)
        cls.tool = importlib.util.module_from_spec(spec)
        if path.exists():
            spec.loader.exec_module(cls.tool)

    def publish(self, play, events=None):
        self.assertTrue(callable(getattr(self.tool, 'publish_edit', None)), 'exact-artifact publisher is not implemented')
        return self.tool.publish_edit(play, object(), 114,
                                      [{'language': 'ar', 'text': 'جديد'}, {'language': 'en-US', 'text': 'New'}],
                                      expected_aab_sha256='b' * 64,
                                      record=(events if events is not None else []).append)

    def test_exact_new_bundle_validated_before_completed_full_release_commit(self):
        play, events = Play(), []
        result = self.publish(play, events)
        self.assertEqual([c[0] for c in play.calls], ['insert', 'list', 'upload', 'update', 'validate', 'commit'])
        release = next(c[1]['body']['releases'][0] for c in play.calls if c[0] == 'update')
        self.assertEqual(release['versionCodes'], ['114'])
        self.assertEqual(release['status'], 'completed')
        self.assertNotIn('userFraction', release)
        self.assertFalse(play.calls[-1][1]['changesNotSentForReview'])
        self.assertEqual(result['committed'], True)
        self.assertEqual(events[-2]['stage'], 'commit_attempted')
        self.assertEqual(events[-1]['stage'], 'committed')

    def test_only_matching_version_and_digest_can_reuse_already_validated_bundle(self):
        play = Play([{'versionCode': 114, 'sha256': 'b' * 64}])
        self.publish(play)
        self.assertNotIn('upload', [c[0] for c in play.calls])
        for digest in [None, '', 'c' * 64]:
            with self.subTest(digest=digest):
                play = Play([{'versionCode': 114, 'sha256': digest}])
                with self.assertRaises(ValueError):
                    self.publish(play)
                self.assertEqual([c[0] for c in play.calls], ['insert', 'list', 'delete'])

    def test_mismatched_upload_or_validate_failure_never_commits_and_deletes_own_edit(self):
        for fail in ['upload', 'update', 'validate']:
            with self.subTest(fail=fail):
                play = Play(fail_at=fail)
                with self.assertRaises(RuntimeError):
                    self.publish(play)
                self.assertEqual(play.calls[-1][0], 'delete')
                self.assertNotIn('commit', [c[0] for c in play.calls])
        play = Play()
        play.upload = lambda **kw: play.request('upload', {'versionCode': 114, 'sha256': 'c' * 64}, **kw)
        with self.assertRaises(ValueError):
            self.publish(play)
        self.assertEqual(play.calls[-1][0], 'delete')
        self.assertNotIn('update', [c[0] for c in play.calls])

    def test_ambiguous_commit_is_recorded_and_never_retried_or_claimed_success(self):
        play, events = Play(fail_at='commit'), []
        with self.assertRaises(RuntimeError):
            self.publish(play, events)
        self.assertEqual(sum(c[0] == 'commit' for c in play.calls), 1)
        self.assertEqual(events[-1]['stage'], 'commit_outcome_unknown')
        self.assertNotIn('delete', [c[0] for c in play.calls])

    def test_invalid_validation_receipt_is_rejected_before_any_play_request(self):
        self.assertTrue(callable(getattr(self.tool, 'check_validation_receipt', None)), 'validation receipt binding is not implemented')
        receipt = {'schema': 'tg.play_validate_only/1', 'package': 'com.alsaba.almorabbi',
                   'source_sha': 'a' * 40, 'version': '1.0.69+114', 'aab_sha256': 'b' * 64,
                   'upload_certificate_sha256': 'c' * 64, 'unsigned_manifest_sha256': 'd' * 64,
                   'notes_sha256': 'e' * 64, 'play_upload_accepted': True,
                   'edits_validate_succeeded': True, 'own_edit_deleted': True, 'committed': False}
        report = {'source_sha': 'a' * 40, 'version': '1.0.69+114', 'aab_sha256': 'b' * 64,
                  'upload_certificate_sha256': 'c' * 64, 'unsigned_manifest_sha256': 'd' * 64}
        self.tool.check_validation_receipt(receipt, report, 'e' * 64)
        for key, value in [('aab_sha256', 'f' * 64), ('notes_sha256', 'f' * 64),
                           ('source_sha', 'f' * 40), ('own_edit_deleted', False),
                           ('play_upload_accepted', 'true'), ('committed', True)]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.tool.check_validation_receipt(dict(receipt, **{key: value}), report, 'e' * 64)

    def run_cli(self, tamper=None, mutate_originals=False):
        self.assertTrue(callable(getattr(self.tool, 'main', None)), 'verified publication CLI is not implemented')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            aab = root / 'signed.aab'
            aab.write_bytes(b'verified signed artifact fixture')
            digest = hashlib.sha256(aab.read_bytes()).hexdigest()
            unsigned = root / 'unsigned.json'
            unsigned.write_text('{}')
            notes = root / '1.0.69+114.json'
            notes.write_text(json.dumps({'ar': 'جديد', 'en-US': 'New'}))
            report = {'schema': 'tg.release_bundle/1', 'source_sha': 'a' * 40,
                      'package': 'com.alsaba.almorabbi', 'version': '1.0.69+114',
                      'aab_sha256': digest, 'signing': 'verified-upload-certificate',
                      'upload_certificate_sha256': 'c' * 64,
                      'unsigned_manifest_sha256': hashlib.sha256(unsigned.read_bytes()).hexdigest()}
            signed = root / 'signed.json'
            signed.write_text(json.dumps(report))
            receipt_data = dict(report, schema='tg.play_validate_only/1',
                                play_upload_accepted=True, edits_validate_succeeded=True,
                                own_edit_deleted=True, committed=False,
                                notes_sha256=hashlib.sha256(notes.read_bytes()).hexdigest())
            validation = root / 'validated.json'
            if tamper == 'validation':
                receipt_data['aab_sha256'] = 'f' * 64
            validation.write_text(json.dumps(receipt_data))
            if tamper == 'aab':
                aab.write_bytes(b'tampered')
            journal = root / 'publication.json'
            if tamper == 'journal':
                journal.write_text('preserve')
                original_journal_mode = journal.stat().st_mode & 0o777
            play = Play()
            play.upload = lambda **kw: play.request('upload', {'versionCode': 114, 'sha256': digest}, **kw)
            media_paths = []
            def media_file(path, **kwargs):
                copy = Path(path)
                self.assertNotEqual(copy, aab)
                self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), digest)
                self.assertEqual(copy.stat().st_mode & 0o777, 0o400)
                media_paths.append(copy)
                if mutate_originals:
                    aab.write_bytes(b'changed original after verification')
                    notes.write_text('changed notes after verification')
                    validation.write_text('changed receipt after verification')
                return object()
            def inspect(args):
                self.assertEqual(hashlib.sha256(args.aab.read_bytes()).hexdigest(), digest)
                args.output.write_text(json.dumps(report))
            account = types.ModuleType('google.oauth2.service_account')
            account.Credentials = types.SimpleNamespace(from_service_account_file=lambda *a, **kw: object())
            oauth = types.ModuleType('google.oauth2')
            oauth.service_account = account
            discovery = types.ModuleType('googleapiclient.discovery')
            discovery.build = lambda *a, **kw: play
            http = types.ModuleType('googleapiclient.http')
            http.MediaFileUpload = media_file
            modules = {'google': types.ModuleType('google'), 'google.oauth2': oauth,
                       'google.oauth2.service_account': account,
                       'googleapiclient': types.ModuleType('googleapiclient'),
                       'googleapiclient.discovery': discovery, 'googleapiclient.http': http}
            argv = ['publisher', '--publish-completed-production', '--aab', str(aab),
                    '--signed-manifest', str(signed), '--unsigned-map', str(unsigned),
                    '--bundletool', str(root / 'tool.jar'), '--notes-file', str(notes),
                    '--sa', str(root / 'NEVER_READ_KEY.json'), '--validated-receipt', str(validation),
                    '--journal', str(journal), '--source-sha', 'a' * 40,
                    '--version', '1.0.69+114', '--expected-aab-sha256', digest,
                    '--expected-upload-cert-sha256', 'c' * 64]
            with patch.object(sys, 'argv', argv), patch.dict(sys.modules, modules), \
                    patch.object(self.tool.validator.release_bundle, 'inspect', side_effect=inspect), patch('builtins.print'):
                code = self.tool.main()
            written = journal.read_text() if journal.exists() else None
            self.assertTrue(all(not p.exists() for p in media_paths))
            if journal.exists():
                self.assertEqual(journal.stat().st_mode & 0o777, 0o600 if tamper != 'journal' else original_journal_mode)
            return code, play.calls, written, receipt_data['notes_sha256']

    def test_cli_reverifies_private_copy_and_receipt_before_publish(self):
        code, calls, written, notes_sha = self.run_cli(mutate_originals=True)
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in calls], ['insert', 'list', 'upload', 'update', 'validate', 'commit'])
        self.assertEqual(next(c[1]['body']['releases'][0]['releaseNotes'] for c in calls if c[0] == 'update'),
                         [{'language': 'ar', 'text': 'جديد'}, {'language': 'en-US', 'text': 'New'}])
        journal = json.loads(written)
        self.assertEqual(journal['stage'], 'committed')
        self.assertTrue(journal['committed'])
        self.assertFalse(journal['availability_verified'])
        self.assertEqual(journal['notes_sha256'], notes_sha)

    def test_cli_tampering_and_preexisting_journal_fail_before_any_play_request(self):
        for tamper in ['validation', 'aab', 'journal']:
            with self.subTest(tamper=tamper):
                code, calls, written, _ = self.run_cli(tamper=tamper)
                self.assertEqual(code, 1)
                self.assertEqual(calls, [])
                if tamper == 'journal':
                    self.assertEqual(written, 'preserve')


if __name__ == '__main__':
    unittest.main()
