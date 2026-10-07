"""Validate-only lifecycle tests with a fake Play service; no network or keys."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Request:
    def __init__(self, value=None, error=None):
        self.value, self.error = value, error

    def execute(self):
        if self.error:
            raise self.error
        return self.value


class Play:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def edits(self):
        return self

    def bundles(self):
        return self

    def tracks(self):
        return self

    def request(self, name, value=None, **kwargs):
        self.calls.append((name, kwargs))
        return Request(value, RuntimeError(name) if self.fail_at == name else None)

    def insert(self, **kwargs):
        return self.request('insert', {'id': 'our-edit'}, **kwargs)

    def upload(self, **kwargs):
        return self.request('upload', {'versionCode': 114, 'sha256': 'b'*64}, **kwargs)

    def update(self, **kwargs):
        return self.request('update', {}, **kwargs)

    def validate(self, **kwargs):
        return self.request('validate', {}, **kwargs)

    def delete(self, **kwargs):
        return self.request('delete', {}, **kwargs)

    def commit(self, **kwargs):
        raise AssertionError('validate-only must never commit')


class ValidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('release_play_validate', ROOT / 'scripts/release_play_validate.py')
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def test_success_uploads_exact_artifact_validates_and_deletes_own_edit(self):
        play = Play()
        self.tool.validate_edit(play, object(), 114, [{'language': 'en-US', 'text': 'Verified notes'}], expected_aab_sha256='b'*64)
        self.assertEqual([name for name, _ in play.calls], ['insert', 'upload', 'update', 'validate', 'delete'])
        for name, kwargs in play.calls[1:]:
            self.assertEqual(kwargs['editId'], 'our-edit')
        body = play.calls[2][1]['body']['releases'][0]
        self.assertEqual(body['versionCodes'], ['114'])
        self.assertEqual(body['status'], 'completed')

    def test_failure_always_deletes_own_edit_and_never_commits(self):
        for fail in ['upload', 'update', 'validate']:
            with self.subTest(fail=fail):
                play = Play(fail)
                with self.assertRaises(RuntimeError):
                    self.tool.validate_edit(play, object(), 114, [], expected_aab_sha256='b'*64)
                self.assertEqual(play.calls[-1][0], 'delete')

    def test_wrong_uploaded_version_is_not_assigned_to_track(self):
        play = Play()
        play.upload = lambda **kwargs: play.request('upload', {'versionCode': 113}, **kwargs)
        with self.assertRaisesRegex(ValueError, 'version'):
            self.tool.validate_edit(play, object(), 114, [], expected_aab_sha256='b'*64)
        self.assertEqual([x[0] for x in play.calls], ['insert', 'upload', 'delete'])

    def test_missing_or_malformed_uploaded_digest_is_rejected_and_edit_deleted(self):
        for digest in [None, '', 'b'*63, 'not-a-hash', 'c'*64]:
            play = Play()
            play.upload = lambda **kwargs: play.request('upload', {'versionCode': 114, 'sha256': digest}, **kwargs)
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    self.tool.validate_edit(play, object(), 114, [], expected_aab_sha256='b'*64)
                self.assertEqual([x[0] for x in play.calls], ['insert', 'upload', 'delete'])

    def test_manifest_requires_exact_expected_sha_package_version_and_signed_status(self):
        report = {'schema': 'tg.release_bundle/1', 'source_sha': 'a'*40, 'package': 'com.alsaba.almorabbi', 'version': '1.0.69+114', 'aab_sha256': 'b'*64, 'signing': 'verified-upload-certificate', 'upload_certificate_sha256': 'c'*64}
        self.tool.check_report(report, 'a'*40, '1.0.69+114', 'b'*64)
        for key, value in [('source_sha', 'd'*40), ('package', 'evil'), ('version', '1.0.68+113'), ('aab_sha256', 'e'*64), ('signing', 'unsigned')]:
            changed = dict(report, **{key: value})
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.tool.check_report(changed, 'a'*40, '1.0.69+114', 'b'*64)

    def test_cleanup_failure_is_not_reported_as_success(self):
        with self.assertRaises(RuntimeError):
            self.tool.validate_edit(Play('delete'), object(), 114, [], expected_aab_sha256='b'*64)

    def test_notes_must_match_exact_artifact_version_and_length(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / '1.0.68+113.json'
            path.write_text(json.dumps({'ar': 'جديد', 'en-US': 'New'}))
            with self.assertRaisesRegex(ValueError, 'version'):
                self.tool.read_notes(path, '1.0.69+114')
            current = Path(td) / '1.0.69+114.json'
            path.rename(current)
            self.assertEqual(len(self.tool.read_notes(current, '1.0.69+114')), 2)
            current.write_text(json.dumps({'ar': 'جديد', 'en-US': 'x'*501}))
            with self.assertRaises(ValueError):
                self.tool.read_notes(current, '1.0.69+114')

    def run_main(self, *, tampered_report=False, bad_aab=False, existing_receipt=False, mutate_inputs=False, race_receipt=False):
        import hashlib
        import json
        import sys
        import types
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            aab = root/'signed.aab'
            aab.write_bytes(b'verified signed artifact fixture')
            digest = hashlib.sha256(aab.read_bytes()).hexdigest()
            unsigned_map = root/'unsigned.json'
            unsigned_map.write_text('{}')
            notes = root/'1.0.69+114.json'
            notes.write_text(json.dumps({'ar': 'جديد', 'en-US': 'New'}))
            frozen_notes_sha = self.tool.release_bundle.sha_file(notes)
            frozen_map_sha = self.tool.release_bundle.sha_file(unsigned_map)
            report = {'schema': 'tg.release_bundle/1', 'source_sha': 'a'*40,
                      'package': 'com.alsaba.almorabbi', 'version': '1.0.69+114',
                      'aab_sha256': digest, 'signing': 'verified-upload-certificate',
                      'upload_certificate_sha256': 'c'*64,
                      'unsigned_manifest_sha256': frozen_map_sha}
            signed_manifest = root/'signed.json'
            signed_manifest.write_text(json.dumps(dict(report, upload_certificate_sha256='d'*64) if tampered_report else report))
            receipt = root/'receipt.json'
            if existing_receipt:
                receipt.write_text('preserve')
            if bad_aab:
                aab.write_bytes(b'tampered artifact')
            play = Play()
            play.upload = lambda **kwargs: play.request('upload', {'versionCode': 114, 'sha256': digest}, **kwargs)
            media_paths = []
            def media_file(path, **kwargs):
                copied = Path(path)
                self.assertNotEqual(copied, aab)
                self.assertEqual(copied.stat().st_mode & 0o777, 0o400)
                self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), digest)
                media_paths.append(copied)
                if mutate_inputs:
                    aab.write_bytes(b'changed original after verification')
                    notes.write_text('changed original notes')
                    unsigned_map.write_text('changed original baseline')
                if race_receipt:
                    receipt.write_text('created concurrently; preserve')
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
            argv = ['release_play_validate.py', '--aab', str(aab), '--signed-manifest', str(signed_manifest),
                    '--unsigned-map', str(unsigned_map), '--bundletool', str(root/'tool.jar'),
                    '--notes-file', str(notes), '--sa', str(root/'NEVER_READ_KEY.json'), '--receipt', str(receipt),
                    '--source-sha', 'a'*40, '--version', '1.0.69+114', '--expected-aab-sha256', digest,
                    '--expected-upload-cert-sha256', 'c'*64]
            with patch.object(sys, 'argv', argv), patch.dict(sys.modules, modules), patch.object(self.tool.release_bundle, 'inspect', side_effect=inspect), patch('builtins.print'):
                code = self.tool.main()
            written = receipt.read_text() if receipt.exists() else None
            self.assertTrue(all(not p.exists() for p in media_paths), 'private copies must be removed')
            return code, play.calls, written, frozen_notes_sha, frozen_map_sha

    def test_cli_upload_copy_and_receipt_bind_the_actual_frozen_inputs(self):
        import json
        code, calls, written, notes_sha, map_sha = self.run_main(mutate_inputs=True)
        self.assertEqual(code, 0)
        self.assertEqual([x[0] for x in calls], ['insert', 'upload', 'update', 'validate', 'delete'])
        receipt = json.loads(written)
        self.assertEqual(receipt['notes_sha256'], notes_sha)
        self.assertEqual(receipt['unsigned_manifest_sha256'], map_sha)
        self.assertFalse(receipt['committed'])

    def test_cli_rejects_tampered_report_before_any_remote_edit(self):
        code, calls, receipt, _, _ = self.run_main(tampered_report=True)
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIsNone(receipt)

    def test_cli_rejects_bad_artifact_and_existing_receipt_without_play(self):
        for option in ['bad_aab', 'existing_receipt']:
            with self.subTest(option=option):
                code, calls, receipt, _, _ = self.run_main(**{option: True})
                self.assertEqual(code, 1)
                self.assertEqual(calls, [])
                self.assertEqual(receipt, 'preserve' if option == 'existing_receipt' else None)

    def test_receipt_created_during_upload_cannot_be_overwritten(self):
        code, calls, receipt, _, _ = self.run_main(race_receipt=True)
        self.assertEqual(code, 1)
        self.assertEqual(calls[-1][0], 'delete')
        self.assertEqual(receipt, 'created concurrently; preserve')
