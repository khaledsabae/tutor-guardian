#!/usr/bin/env python3
"""Publish the exact validated signed artifact at 100%; no build or signing."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_play_validate as validator

PACKAGE = validator.PACKAGE


def check_validation_receipt(receipt, report, notes_sha256):
    expected = {'schema': 'tg.play_validate_only/1', 'package': PACKAGE,
                'notes_sha256': notes_sha256}
    for key in ['source_sha', 'version', 'aab_sha256', 'upload_certificate_sha256',
                'unsigned_manifest_sha256']:
        expected[key] = report[key]
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError('validation receipt mismatch: ' + key)
    for key in ['play_upload_accepted', 'edits_validate_succeeded', 'own_edit_deleted']:
        if receipt.get(key) is not True:
            raise ValueError('validation receipt is incomplete: ' + key)
    if receipt.get('committed') is not False:
        raise ValueError('expected a validate-only receipt')


def publish_edit(service, media, version_code, notes, *, expected_aab_sha256, record):
    if not re.fullmatch(r'[0-9a-f]{64}', expected_aab_sha256):
        raise ValueError('invalid expected AAB SHA256')
    edits = service.edits()
    edit_id = edits.insert(packageName=PACKAGE, body={}).execute()['id']
    commit_attempted = False
    committed = False
    try:
        record({'stage': 'edit_created', 'edit_id': edit_id})
        existing = edits.bundles().list(packageName=PACKAGE, editId=edit_id).execute()
        matching = [bundle for bundle in existing.get('bundles', [])
                    if int(bundle.get('versionCode', -1)) == version_code]
        if matching:
            if len(matching) != 1 or matching[0].get('sha256') != expected_aab_sha256:
                raise ValueError('existing versionCode does not identify the validated AAB SHA256')
        else:
            response = edits.bundles().upload(packageName=PACKAGE, editId=edit_id, media_body=media).execute()
            if int(response.get('versionCode', -1)) != version_code or response.get('sha256') != expected_aab_sha256:
                raise ValueError('Play uploaded identity differs from validated artifact')
        edits.tracks().update(packageName=PACKAGE, editId=edit_id, track='production',
                              body={'releases': [{'versionCodes': [str(version_code)],
                                                  'status': 'completed', 'releaseNotes': notes}]}).execute()
        edits.validate(packageName=PACKAGE, editId=edit_id).execute()
        # Flush intent before the single irreversible request. If its response
        # is lost, stop for reconciliation rather than retrying or claiming live.
        record({'stage': 'commit_attempted', 'edit_id': edit_id})
        commit_attempted = True
        edits.commit(packageName=PACKAGE, editId=edit_id,
                     changesNotSentForReview=False).execute()
        committed = True
        record({'stage': 'committed', 'edit_id': edit_id})
        return {'committed': True, 'release_status': 'completed',
                'track': 'production', 'rollout_percent': 100,
                'availability_verified': False}
    except Exception:
        if commit_attempted and not committed:
            record({'stage': 'commit_outcome_unknown', 'edit_id': edit_id})
        raise
    finally:
        if not commit_attempted:
            edits.delete(packageName=PACKAGE, editId=edit_id).execute()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish-completed-production', action='store_true', required=True)
    for key in ['aab', 'signed-manifest', 'unsigned-map', 'bundletool', 'notes-file',
                'sa', 'validated-receipt', 'journal']:
        parser.add_argument('--' + key, type=Path, required=True)
    for key in ['source-sha', 'version', 'expected-aab-sha256', 'expected-upload-cert-sha256']:
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    state = {'schema': 'tg.play_publish/1', 'package': PACKAGE,
             'source_sha': args.source_sha, 'version': args.version,
             'aab_sha256': args.expected_aab_sha256, 'committed': False,
             'availability_verified': False, 'stage': 'preflight'}
    journal = None
    try:
        # Reserve the private journal before any remote action. Never overwrite
        # another attempt; a lost commit response requires reconciliation.
        journal = os.fdopen(os.open(args.journal, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600), 'w+')
        def record(update):
            state.update(update)
            if update.get('stage') == 'committed':
                state['committed'] = True
            journal.seek(0)
            journal.write(json.dumps(state, indent=2) + '\n')
            journal.truncate()
            journal.flush()
            os.fsync(journal.fileno())
        record({'stage': 'preflight'})
        original = json.loads(args.signed_manifest.read_text())
        validator.check_report(original, args.source_sha, args.version, args.expected_aab_sha256)
        with tempfile.TemporaryDirectory(prefix='tg-play-publish-') as temporary:
            root = Path(temporary)
            aab = root / 'verified.aab'
            unsigned = root / 'unsigned.json'
            notes_path = root / args.notes_file.name
            validation_path = root / 'validation.json'
            for source, destination in [(args.aab, aab), (args.unsigned_map, unsigned),
                                        (args.notes_file, notes_path), (args.validated_receipt, validation_path)]:
                shutil.copyfile(source, destination)
                destination.chmod(0o400)
            if validator.release_bundle.sha_file(aab) != args.expected_aab_sha256:
                raise ValueError('AAB does not match validated artifact SHA256')
            notes = validator.read_notes(notes_path, args.version)
            notes_sha = validator.release_bundle.sha_file(notes_path)
            inspect_args = argparse.Namespace(command='signed', aab=aab, bundletool=args.bundletool,
                                              source_sha=args.source_sha, version=args.version,
                                              unsigned_map=unsigned,
                                              expected_upload_cert_sha256=args.expected_upload_cert_sha256,
                                              expected_aab_sha256=args.expected_aab_sha256,
                                              output=root / 'verified.json')
            validator.release_bundle.inspect(inspect_args)
            report = json.loads(inspect_args.output.read_text())
            validator.check_report(report, args.source_sha, args.version, args.expected_aab_sha256)
            if report != original:
                raise ValueError('signed manifest differs from freshly inspected artifact')
            check_validation_receipt(json.loads(validation_path.read_text()), report, notes_sha)
            record({'stage': 'preflight_verified', 'notes_sha256': notes_sha,
                    'unsigned_manifest_sha256': report['unsigned_manifest_sha256'],
                    'upload_certificate_sha256': report['upload_certificate_sha256'],
                    'validation_receipt_sha256': validator.release_bundle.sha_file(validation_path)})
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            credentials = service_account.Credentials.from_service_account_file(
                str(args.sa), scopes=['https://www.googleapis.com/auth/androidpublisher'])
            service = build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)
            media = MediaFileUpload(str(aab), mimetype='application/octet-stream',
                                    resumable=True, chunksize=8 * 1024 * 1024)
            publish_edit(service, media, int(args.version.split('+')[1]), notes,
                         expected_aab_sha256=args.expected_aab_sha256, record=record)
        print('Exact validated bundle committed to production at 100%; Play review/availability must be checked separately.')
        return 0
    except Exception as exc:
        if journal is not None:
            # Keep ambiguous/confirmed commit stages intact if writing a later
            # receipt or printing failed; do not disguise them as safe to retry.
            if state['stage'] not in ['commit_attempted', 'commit_outcome_unknown', 'committed']:
                record({'stage': 'failed_before_commit'})
        print('Publication stopped (' + type(exc).__name__ + '); inspect private journal before any retry.', file=sys.stderr)
        return 1
    finally:
        if journal is not None:
            journal.close()


if __name__ == '__main__':
    sys.exit(main())
