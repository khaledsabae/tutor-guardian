"""Offline synthetic ZIP tests; never compile, sign, or contact Play."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('release_bundle', ROOT / 'scripts/release_bundle.py')
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.aab = Path(self.tmp.name) / 'test.aab'

    def bundle(self, extra=()):
        with zipfile.ZipFile(self.aab, 'w') as z:
            z.writestr('BundleConfig.pb', b'config')
            z.writestr('base/dex/classes.dex', b'payload')
            for name, body in extra:
                z.writestr(name, body)
        return self.aab

    def test_unsigned_payload_hashes(self):
        entries = self.tool.payload(self.bundle(), unsigned=True)
        self.assertEqual(set(entries), {'BundleConfig.pb', 'base/dex/classes.dex'})
        self.assertEqual(entries['base/dex/classes.dex']['size'], 7)

    def test_duplicate_payload_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.bundle([('base/dex/classes.dex', b'evil')])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.tool.payload(self.aab, unsigned=True)

    def test_unsigned_rejects_jar_signature_and_manifest(self):
        for name in ['META-INF/CERT.RSA', 'META-INF/CERT.SF', 'META-INF/MANIFEST.MF', 'META-INF/CERT.DSA', 'META-INF/CERT.EC', 'META-INF/SIG-CUSTOM']:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'signing metadata'):
                    self.tool.payload(self.bundle([(name, b'signature')]), unsigned=True)

    def test_signed_payload_excludes_only_direct_jar_metadata(self):
        entries = self.tool.payload(self.bundle([('META-INF/CERT.SF', b'sig'), ('META-INF/services/example', b'keep')]), unsigned=False)
        self.assertIn('META-INF/services/example', entries)
        self.assertNotIn('META-INF/CERT.SF', entries)

    def test_payload_mutation_or_extra_entry_rejected(self):
        expected = self.tool.payload(self.bundle(), unsigned=True)
        for entries in [[('extra', b'x')], [('base/dex/classes2.dex', b'x')]]:
            actual = self.tool.payload(self.bundle(entries), unsigned=False)
            with self.assertRaisesRegex(ValueError, 'payload'):
                self.tool.compare_payload(expected, actual)

    def manifest(self, attrs='', metadata=''):
        return '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.alsaba.almorabbi" android:versionCode="114" android:versionName="1.0.69"><uses-sdk android:minSdkVersion="23" android:targetSdkVersion="36"/><application '+attrs+'>'+metadata+'</application></manifest>'

    def test_package_version_and_production_flags(self):
        self.tool.check_manifest(self.manifest(), 'com.alsaba.almorabbi', '1.0.69+114')
        for xml in [self.manifest().replace('114', '113'), self.manifest().replace('com.alsaba.almorabbi', 'other'), self.manifest('android:debuggable="true"'), self.manifest(metadata='<meta-data android:name="firebase_analytics_collection_deactivated" android:value="true"/>')]:
            with self.subTest(xml=xml):
                with self.assertRaises(ValueError):
                    self.tool.check_manifest(xml, 'com.alsaba.almorabbi', '1.0.69+114')

    def test_source_sha_must_be_exact_current_commit(self):
        with self.assertRaisesRegex(ValueError, 'source SHA'):
            self.tool.check_source('a'*40, 'b'*40)
        with self.assertRaises(ValueError):
            self.tool.check_source('main', 'main')
        self.tool.check_source('a'*40, 'a'*40)

    def test_signature_verification_requires_matching_certificate(self):
        self.tool.check_certificate('SHA256: ' + ':'.join(['AA']*32), 'aa'*32)
        with self.assertRaisesRegex(ValueError, 'certificate'):
            self.tool.check_certificate('SHA256: ' + ':'.join(['AA']*32), 'bb'*32)
        with self.assertRaises(ValueError):
            self.tool.check_certificate('no certificate', 'aa'*32)

    def test_wrong_jar_verdict_is_rejected_even_with_successful_process(self):
        for verdict in ['jar is unsigned.', 'jar verified.\nThis jar contains unsigned entries which have not been integrity-checked.', 'not verified']:
            with self.subTest(verdict=verdict):
                with self.assertRaises(ValueError):
                    self.tool.check_jar_verdict(verdict)
        self.tool.check_jar_verdict('jar verified.\nThe signer certificate is self-signed.')

    def test_expected_bundle_digest_is_required_and_exact(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.tool.check_aab_sha256(self.bundle(), 'a'*64)
        with self.assertRaises(ValueError):
            self.tool.check_aab_sha256(self.aab, '')

    def test_sdk_and_test_only_flags_rejected(self):
        for xml in [self.manifest('android:testOnly="true"'), self.manifest().replace('114', '114').replace('targetSdkVersion="36"', 'targetSdkVersion="28"')]:
            with self.assertRaises(ValueError):
                self.tool.check_manifest(xml, 'com.alsaba.almorabbi', '1.0.69+114')

    def test_changed_existing_payload_hash_is_rejected(self):
        baseline = self.tool.payload(self.bundle(), unsigned=True)
        with zipfile.ZipFile(self.aab, 'w') as z:
            z.writestr('BundleConfig.pb', b'config')
            z.writestr('base/dex/classes.dex', b'changed')
        with self.assertRaisesRegex(ValueError, 'payload'):
            self.tool.compare_payload(baseline, self.tool.payload(self.aab, unsigned=False))

    def test_bundletool_checksum_is_checked_before_java(self):
        from unittest.mock import patch
        from argparse import Namespace
        jar = Path(self.tmp.name) / 'fake.jar'
        jar.write_bytes(b'wrong tool')
        args = Namespace(command='unsigned', bundletool=jar)
        with patch.object(self.tool, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'bundletool checksum'):
                self.tool.inspect(args)
            run.assert_not_called()

    def test_matching_debug_certificate_is_still_rejected(self):
        with self.assertRaisesRegex(ValueError, 'debug'):
            self.tool.check_certificate('Owner: CN=Android Debug,O=Android,C=US\nSHA256: ' + ':'.join(['AA']*32), 'aa'*32)

    def test_disabled_analytics_collection_is_rejected(self):
        xml = self.manifest(metadata='<meta-data android:name="firebase_analytics_collection_enabled" android:value="false"/>')
        with self.assertRaisesRegex(ValueError, 'Analytics'):
            self.tool.check_manifest(xml, 'com.alsaba.almorabbi', '1.0.69+114')

    def test_every_flutter_release_abi_is_required(self):
        entries = {f'base/lib/{abi}/{lib}': {'size': 7, 'sha256': 'a'*64}
                   for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64']
                   for lib in ['libapp.so', 'libflutter.so']}
        checker = getattr(self.tool, 'check_abis', None)
        self.assertIsNotNone(checker, 'must reject bundles missing production Flutter ABIs')
        checker(entries)
        for entry in entries:
            with self.subTest(entry=entry):
                incomplete = dict(entries)
                del incomplete[entry]
                with self.assertRaisesRegex(ValueError, 'ABI'):
                    checker(incomplete)

    def test_signed_inspection_rechecks_frozen_provenance_and_payload(self):
        from argparse import Namespace
        import hashlib
        import json
        from unittest.mock import patch
        libraries = [(f'base/lib/{abi}/{lib}', b'library')
                     for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64']
                     for lib in ['libapp.so', 'libflutter.so']]
        baseline = {'schema': 'tg.release_bundle/1', 'source_sha': 'a'*40,
                    'package': 'com.alsaba.almorabbi', 'version': '1.0.69+114',
                    'bundletool_version': self.tool.BUNDLETOOL_VERSION,
                    'bundletool_sha256': self.tool.BUNDLETOOL_SHA256,
                    'manifest_sha256': hashlib.sha256(self.manifest().encode()).hexdigest(),
                    'signing': 'unsigned', 'entries': self.tool.payload(self.bundle(libraries), unsigned=True)}
        self.bundle(libraries + [('META-INF/CERT.SF', b'fake signature envelope')])
        jar = Path(self.tmp.name)/'tool.jar'
        jar.write_bytes(b'fixture; never executed')
        unsigned_map = Path(self.tmp.name)/'unsigned.json'
        output = Path(self.tmp.name)/'signed.json'
        args = Namespace(command='signed', aab=self.aab, bundletool=jar,
                         source_sha='a'*40, version='1.0.69+114', unsigned_map=unsigned_map,
                         expected_aab_sha256=self.tool.sha_file(self.aab),
                         expected_upload_cert_sha256='aa'*32, output=output)
        sha_file = self.tool.sha_file
        def digest(path):
            return self.tool.BUNDLETOOL_SHA256 if path == jar else sha_file(path)
        def run(*command):
            if command[0] == 'java':
                return self.manifest() if 'dump' in command else ''
            if command[0] == 'jarsigner':
                return 'jar verified.'
            if command[0] == 'keytool':
                return 'Owner: CN=Upload\nSHA256: '+':'.join(['AA']*32)
            self.fail('signed inspection must not consult the local checkout')
        with patch.object(self.tool, 'sha_file', side_effect=digest), patch.object(self.tool, 'run', side_effect=run), patch('builtins.print'):
            unsigned_map.write_text(json.dumps(baseline))
            self.tool.inspect(args)
            signed = json.loads(output.read_text())
            self.assertEqual(signed['entries'], baseline['entries'])
            self.assertEqual(signed['unsigned_manifest_sha256'], sha_file(unsigned_map))
            for key, value in [('source_sha', 'b'*40), ('version', '1.0.68+113'),
                               ('package', 'evil'), ('bundletool_sha256', 'b'*64),
                               ('manifest_sha256', 'b'*64), ('signing', 'signed'),
                               ('entries', {})]:
                with self.subTest(key=key):
                    unsigned_map.write_text(json.dumps(dict(baseline, **{key: value})))
                    output.unlink(missing_ok=True)
                    with self.assertRaises(ValueError):
                        self.tool.inspect(args)
                    self.assertFalse(output.exists())

    def test_weak_signature_treated_as_unsigned_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'signature'):
            self.tool.check_jar_verdict('jar verified.\nThe jar will be treated as unsigned because of a disabled algorithm.')

    def test_same_size_tampering_renaming_removal_and_size_mismatch_rejected(self):
        baseline = self.tool.payload(self.bundle(), unsigned=True)
        cases = [
            dict(baseline, **{'base/dex/classes.dex': {'size': 7, 'sha256': 'a'*64}}),
            {('renamed' if name == 'base/dex/classes.dex' else name): value for name, value in baseline.items()},
            {'BundleConfig.pb': baseline['BundleConfig.pb']},
            dict(baseline, **{'base/dex/classes.dex': dict(baseline['base/dex/classes.dex'], size=8)}),
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, 'payload'):
                    self.tool.compare_payload(baseline, changed)


class WorkflowTests(unittest.TestCase):
    def test_dispatch_rejects_unapproved_or_dirty_source_before_build(self):
        import os
        import subprocess
        import yaml
        flow = yaml.safe_load((ROOT / '.github/workflows/build-release-unsigned.yml').read_text())
        guard = next(s for s in flow['jobs']['build']['steps'] if s.get('name') == 'Require an unmodified production source tree')
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['git', 'init', '-q', td], check=True, capture_output=True)
            path = Path(td) / 'source.txt'
            path.write_text('approved source')
            subprocess.run(['git', '-C', td, 'add', 'source.txt'], check=True)
            subprocess.run(['git', '-C', td, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            sha = subprocess.check_output(['git', '-C', td, 'rev-parse', 'HEAD'], text=True).strip()
            env = dict(os.environ, GITHUB_SHA=sha)
            for approved in ['a'*40, sha[:8], '', sha]:
                result = subprocess.run(['bash', '-e', '-c', guard['run']], cwd=td,
                                        env=dict(env, APPROVED_SOURCE_SHA=approved), capture_output=True)
                with self.subTest(approved=approved):
                    if approved == sha:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0, 'dispatch must reject an unapproved source SHA')
            for dirty in ['untracked', 'tracked']:
                (Path(td)/'unexpected.txt' if dirty == 'untracked' else path).write_text('modified')
                result = subprocess.run(['bash', '-e', '-c', guard['run']], cwd=td,
                                        env=dict(env, APPROVED_SOURCE_SHA=sha), capture_output=True)
                with self.subTest(dirty=dirty):
                    self.assertNotEqual(result.returncode, 0, 'source tree must be clean')
                if dirty == 'untracked':
                    (Path(td)/'unexpected.txt').unlink()

    def test_unsigned_flag_is_hosted_only_and_default_release_retains_signing(self):
        workflow = ROOT / '.github/workflows/build-release-unsigned.yml'
        self.assertTrue(workflow.is_file(), 'build-only workflow missing')
        text = workflow.read_text()
        self.assertNotIn('secrets.', text)
        self.assertNotIn('play_upload', text)
        self.assertNotIn('deactivate-analytics', text)
        self.assertIn('TG_CI_UNSIGNED_AAB', text)
        self.assertIn('GITHUB_ACTIONS', text)
        self.assertIn('flutter build appbundle --release', text)
        self.assertNotIn('--target-platform', text)
        gradle = (ROOT / 'mobile/android/app/build.gradle.kts').read_text()
        self.assertIn('TG_CI_UNSIGNED_AAB', gradle)
        self.assertRegex(gradle, r'signingConfig = if \(ciUnsignedAab\) \{\s+null')
        self.assertIn('GITHUB_ACTIONS', gradle)
        self.assertIn('signingConfigs.getByName("debug")', gradle)

    def test_workflow_is_bound_to_dispatch_sha_and_only_build_job_has_unsigned_flag(self):
        import yaml
        flow = yaml.safe_load((ROOT / '.github/workflows/build-release-unsigned.yml').read_text())
        build = flow['jobs']['build']
        self.assertEqual(build['runs-on'], 'ubuntu-latest')
        self.assertIn("github.ref == 'refs/heads/main'", build['if'])
        checkout = build['steps'][0]
        self.assertEqual(checkout['with']['ref'], '${{ github.sha }}')
        self.assertFalse(checkout['with']['persist-credentials'])
        commands = [step.get('run', '') for step in build['steps']]
        unsigned = [s for s in commands if 'TG_CI_UNSIGNED_AAB=true' in s]
        self.assertEqual(len(unsigned), 1)
        self.assertIn('flutter build appbundle --release', unsigned[0])
        for forbidden in ['--dart-define', '--target-platform', 'deactivate-analytics']:
            self.assertNotIn(forbidden, unsigned[0])
        normal = (ROOT / '.github/workflows/release-play.yml').read_text()
        self.assertNotIn('TG_CI_UNSIGNED_AAB', normal)
        gradle = (ROOT / 'mobile/android/app/build.gradle.kts').read_text()
        self.assertIn('isMinifyEnabled = true', gradle)
        self.assertIn('isShrinkResources = true', gradle)
        steps = '\n'.join(commands)
        self.assertIn('git rev-parse HEAD', steps)
        self.assertIn('--source-sha "$GITHUB_SHA"', steps)
        self.assertIn('sha256sum --check', steps)
