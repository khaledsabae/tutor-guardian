#!/usr/bin/env python3
"""Validate a verified, locally signed AAB in our temporary Play edit. Never commits."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_bundle

PACKAGE = release_bundle.PACKAGE


def check_report(report, source_sha, version, aab_sha256):
    expected = {'schema': 'tg.release_bundle/1', 'source_sha': source_sha,
                'package': PACKAGE, 'version': version, 'aab_sha256': aab_sha256,
                'signing': 'verified-upload-certificate'}
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha) or not re.fullmatch(r'[0-9a-f]{64}', aab_sha256) or not re.fullmatch(r'\d+\.\d+\.\d+\+\d+', version):
        raise ValueError('invalid expected artifact identity')
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError('artifact manifest mismatch: '+key)
    if not re.fullmatch(r'[0-9a-f]{64}', report.get('upload_certificate_sha256', '')):
        raise ValueError('missing verified local upload certificate')


def validate_edit(service, media, version_code, notes, *, expected_aab_sha256):
    if not re.fullmatch(r'[0-9a-f]{64}', expected_aab_sha256):
        raise ValueError('invalid expected AAB SHA256')
    edits = service.edits()
    edit_id = edits.insert(packageName=PACKAGE, body={}).execute()['id']
    try:
        # Always upload this exact artifact; never trust dirty-root pubspec or
        # skip upload because another bundle happens to share its versionCode.
        response = edits.bundles().upload(packageName=PACKAGE, editId=edit_id, media_body=media).execute()
        if int(response.get('versionCode', -1)) != version_code:
            raise ValueError('Play returned a different uploaded version')
        if response.get('sha256') != expected_aab_sha256:
            raise ValueError('Play returned a different uploaded AAB SHA256')
        edits.tracks().update(packageName=PACKAGE, editId=edit_id, track='production',
                              body={'releases': [{'versionCodes': [str(version_code)],
                                                  'status': 'completed', 'releaseNotes': notes}]}).execute()
        edits.validate(packageName=PACKAGE, editId=edit_id).execute()
    finally:
        # No commit method exists in this tool. A failed cleanup is a failure,
        # not a green receipt; the exception remains visible to the operator.
        edits.delete(packageName=PACKAGE, editId=edit_id).execute()


def read_notes(path, version):
    if path.name != version+'.json':
        raise ValueError('release notes filename must match exact artifact version')
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or set(data) != {'ar', 'en-US'} or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in data.values()):
        raise ValueError('expected nonempty Arabic/English notes of at most 500 characters')
    return [{'language': k, 'text': v} for k, v in data.items()]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['aab', 'signed-manifest', 'unsigned-map', 'bundletool', 'notes-file', 'sa', 'receipt']:
        p.add_argument('--'+key, type=Path, required=True)
    for key in ['source-sha', 'version', 'expected-aab-sha256', 'expected-upload-cert-sha256']:
        p.add_argument('--'+key, required=True)
    args = p.parse_args()
    try:
        if args.receipt.exists():
            raise ValueError('receipt path already exists; choose a fresh output path')
        original_report = json.loads(args.signed_manifest.read_text())
        check_report(original_report, args.source_sha, args.version, args.expected_aab_sha256)
        with tempfile.TemporaryDirectory(prefix='tg-play-validate-') as temporary:
            copy = Path(temporary) / 'verified.aab'
            shutil.copyfile(args.aab, copy)
            copy.chmod(0o400)
            if release_bundle.sha_file(copy) != args.expected_aab_sha256:
                raise ValueError('AAB SHA256 does not match expected artifact')
            frozen_map = Path(temporary) / 'unsigned-map.json'
            frozen_notes = Path(temporary) / args.notes_file.name
            for source, destination in [(args.unsigned_map, frozen_map), (args.notes_file, frozen_notes)]:
                shutil.copyfile(source, destination)
                destination.chmod(0o400)
            notes = read_notes(frozen_notes, args.version)
            notes_sha256 = release_bundle.sha_file(frozen_notes)
            # Repeat structural, payload and certificate verification on the
            # private upload copy before creating any remote edit.
            inspect_args = argparse.Namespace(command='signed', aab=copy, bundletool=args.bundletool,
                                              source_sha=args.source_sha, version=args.version,
                                              unsigned_map=frozen_map,
                                              expected_upload_cert_sha256=args.expected_upload_cert_sha256,
                                              expected_aab_sha256=args.expected_aab_sha256,
                                              output=Path(temporary) / 'verified.json')
            release_bundle.inspect(inspect_args)
            report = json.loads(inspect_args.output.read_text())
            check_report(report, args.source_sha, args.version, args.expected_aab_sha256)
            if report != original_report:
                raise ValueError('signed manifest differs from reverified artifact report')
            # Existing user service account only, explicitly selected. No
            # credentials enter arguments to child processes or CI secrets.
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            credentials = service_account.Credentials.from_service_account_file(str(args.sa), scopes=['https://www.googleapis.com/auth/androidpublisher'])
            service = build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)
            media = MediaFileUpload(str(copy), mimetype='application/octet-stream', resumable=True, chunksize=8*1024*1024)
            validate_edit(service, media, int(args.version.split('+')[1]), notes,
                          expected_aab_sha256=args.expected_aab_sha256)
            receipt_data = {'schema': 'tg.play_validate_only/1', 'package': PACKAGE,
                            'version': args.version, 'source_sha': args.source_sha,
                            'aab_sha256': args.expected_aab_sha256,
                            'upload_certificate_sha256': report['upload_certificate_sha256'],
                            'play_upload_accepted': True, 'edits_validate_succeeded': True,
                            'own_edit_deleted': True, 'committed': False, 'notes_sha256': notes_sha256,
                            'unsigned_manifest_sha256': report['unsigned_manifest_sha256']}
            with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as receipt:
                receipt.write(json.dumps(receipt_data, indent=2)+'\n')
        print('Play accepted and validated this exact bundle; our edit deleted; nothing published.')
        return 0
    except Exception as exc:
        # API errors can carry response bodies. Expose the error class only;
        # never dump credentials, request bodies or raw private API logs.
        print('Validate-only failed ('+type(exc).__name__+'); no commit attempted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
