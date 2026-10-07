#!/usr/bin/env python3
"""Inspect unsigned hosted AABs and locally signed copies. Never signs or uploads."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

BUNDLETOOL_VERSION = '1.18.3'
BUNDLETOOL_SHA256 = 'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29'
PACKAGE = 'com.alsaba.almorabbi'
ANDROID = '{http://schemas.android.com/apk/res/android}'
SIGNATURE = re.compile(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)', re.I)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def payload(path, *, unsigned):
    result = {}
    with zipfile.ZipFile(path) as archive:
        names = [i.filename for i in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP entry')
        for item in archive.infolist():
            if item.is_dir():
                continue
            if SIGNATURE.fullmatch(item.filename):
                if unsigned:
                    raise ValueError('unsigned bundle contains signing metadata')
                continue
            h = hashlib.sha256()
            with archive.open(item) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            result[item.filename] = {'size': item.file_size, 'sha256': h.hexdigest()}
    return result


def compare_payload(expected, actual):
    if not expected or expected != actual:
        raise ValueError('signed bundle payload differs from frozen unsigned payload')


def check_source(source, actual):
    if not re.fullmatch(r'[0-9a-f]{40}', source) or source != actual:
        raise ValueError('source SHA must equal the exact checked-out commit')


def check_manifest(xml, package, version):
    match = re.fullmatch(r'(\d+\.\d+\.\d+)\+(\d+)', version)
    if not match:
        raise ValueError('invalid release version')
    root = ET.fromstring(xml)
    if root.get('package') != package or root.get(ANDROID+'versionName') != match[1] or root.get(ANDROID+'versionCode') != match[2]:
        raise ValueError('bundle package/version mismatch')
    sdk = root.findall('uses-sdk')
    if len(sdk) != 1 or not sdk[0].get(ANDROID+'targetSdkVersion', '').isdigit() or int(sdk[0].get(ANDROID+'targetSdkVersion')) < 35:
        raise ValueError('bundle must retain a production target SDK of at least 35')
    apps = root.findall('application')
    if len(apps) != 1 or apps[0].get(ANDROID+'debuggable', 'false') != 'false' or apps[0].get(ANDROID+'testOnly', 'false') != 'false':
        raise ValueError('bundle must retain production release flags')
    for item in apps[0].findall('meta-data'):
        if (item.get(ANDROID+'name') == 'firebase_analytics_collection_deactivated'
                or (item.get(ANDROID+'name') == 'firebase_analytics_collection_enabled'
                    and item.get(ANDROID+'value') != 'true')):
            raise ValueError('CI E2E Analytics deactivation must not enter production bundle')
    return {'target_sdk': int(sdk[0].get(ANDROID+'targetSdkVersion')), 'min_sdk': sdk[0].get(ANDROID+'minSdkVersion'), 'debuggable': False, 'test_only': False, 'e2e_analytics_deactivated': False}


def check_abis(entries):
    for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64']:
        for library in ['libapp.so', 'libflutter.so']:
            entry = entries.get(f'base/lib/{abi}/{library}')
            if not entry or entry['size'] <= 0:
                raise ValueError('bundle missing production Flutter ABI: '+abi+'/'+library)


def check_certificate(output, expected):
    if re.search(r'Owner:.*CN\s*=\s*Android Debug(?:[,\n]|$)', output, re.I):
        raise ValueError('debug certificate cannot sign a production bundle')
    wanted = expected.replace(':', '').lower()
    found = {x.replace(':', '').lower() for x in re.findall(r'SHA256:\s*([0-9A-Fa-f:]+)', output)}
    if not re.fullmatch(r'[0-9a-f]{64}', wanted) or found != {wanted}:
        raise ValueError('bundle signer certificate does not match expected Play upload certificate')


def check_jar_verdict(verdict):
    if (not re.search(r'^jar verified\.$', verdict, re.M)
            or any(warning in verdict.lower() for warning in
                   ['unsigned entries', 'jar is unsigned', 'treated as unsigned'])):
        raise ValueError('bundle JAR signature verification failed')


def check_aab_sha256(path, expected):
    if not re.fullmatch(r'[0-9a-f]{64}', expected) or sha_file(path) != expected:
        raise ValueError('AAB SHA256 does not match expected artifact')


def run(*command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)


def inspect(args):
    if args.command == 'signed':
        check_aab_sha256(args.aab, args.expected_aab_sha256)
    if sha_file(args.bundletool) != BUNDLETOOL_SHA256:
        raise ValueError('bundletool checksum mismatch')
    if args.command == 'unsigned':
        check_source(args.source_sha, run('git', 'rev-parse', 'HEAD').strip())
        pubspec = Path('mobile/pubspec.yaml').read_text()
        versions = re.findall(r'^version:\s*([^\s#]+)', pubspec, re.M)
        if versions != [args.version]:
            raise ValueError('pubspec version must match requested artifact version')
    elif not re.fullmatch(r'[0-9a-f]{40}', args.source_sha):
        raise ValueError('invalid frozen source SHA')
    run('java', '-jar', str(args.bundletool), 'validate', '--bundle='+str(args.aab))
    xml = run('java', '-jar', str(args.bundletool), 'dump', 'manifest', '--module=base', '--bundle='+str(args.aab))
    flags = check_manifest(xml, PACKAGE, args.version)
    entries = payload(args.aab, unsigned=args.command == 'unsigned')
    check_abis(entries)
    metadata = {'schema': 'tg.release_bundle/1', 'source_sha': args.source_sha, 'package': PACKAGE, 'version': args.version, 'bundletool_version': BUNDLETOOL_VERSION, 'bundletool_sha256': BUNDLETOOL_SHA256, 'aab_sha256': sha_file(args.aab), 'manifest_sha256': hashlib.sha256(xml.encode()).hexdigest(), 'manifest_flags': flags, 'entries': entries}
    if args.command == 'signed':
        baseline = json.loads(args.unsigned_map.read_text())
        for key in ['schema', 'source_sha', 'package', 'version', 'bundletool_version', 'bundletool_sha256', 'manifest_sha256']:
            if baseline.get(key) != metadata[key]:
                raise ValueError('unsigned provenance mismatch: '+key)
        if baseline.get('signing') != 'unsigned':
            raise ValueError('baseline must be the frozen unsigned artifact map')
        compare_payload(baseline['entries'], entries)
        # jarsigner exit0 alone may mean an unsigned JAR. Require its success
        # verdict and reject unsigned entries, then independently pin the cert.
        verdict = run('jarsigner', '-J-Duser.language=en', '-verify', '-verbose', '-certs', str(args.aab))
        check_jar_verdict(verdict)
        cert = run('keytool', '-J-Duser.language=en', '-printcert', '-jarfile', str(args.aab))
        check_certificate(cert, args.expected_upload_cert_sha256)
        metadata['unsigned_manifest_sha256'] = sha_file(args.unsigned_map)
        metadata['build'] = baseline.get('build')
        metadata['signing'] = 'verified-upload-certificate'
        metadata['upload_certificate_sha256'] = args.expected_upload_cert_sha256.replace(':', '').lower()
    else:
        metadata['signing'] = 'unsigned'
        metadata['build'] = {'command': 'flutter build appbundle --release', 'flutter_version': '3.44.1', 'abi_override': None, 'api_config_source_sha256': sha_file('mobile/lib/config/app_config.dart'), 'api_default': 'https://tg-api.alsaba.cloud', 'production_manifest_source_sha256': sha_file('mobile/android/app/src/main/AndroidManifest.xml'), 'gradle_source_sha256': sha_file('mobile/android/app/build.gradle.kts')}
    args.output.write_text(json.dumps(metadata, indent=2, sort_keys=True)+'\n')
    print('Verified '+metadata['signing']+' bundle: '+args.version+' source '+args.source_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['unsigned', 'signed']:
        p = sub.add_parser(name)
        for key in ['aab', 'bundletool', 'output']:
            p.add_argument('--'+key, type=Path, required=True)
        p.add_argument('--source-sha', required=True)
        p.add_argument('--version', required=True)
        if name == 'signed':
            p.add_argument('--expected-aab-sha256', required=True)
            p.add_argument('--unsigned-map', type=Path, required=True)
            p.add_argument('--expected-upload-cert-sha256', required=True)
    try:
        inspect(parser.parse_args())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError, subprocess.CalledProcessError) as exc:
        # No credentials are read by this tool. Do not print subprocess output.
        print('Bundle verification failed: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
