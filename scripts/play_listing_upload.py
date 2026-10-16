#!/usr/bin/env python3
"""Google Play — store-listing refresh (text + graphics) for المربّي.

One Play edit replaces, for each language in the listing folder:
  icon, featureGraphic, phoneScreenshots (all of them, in file order)
  and patches the listing text (title, shortDescription, fullDescription).

Two modes, one of them required:

  --validate-only   open an edit, upload everything, check Play's own image
                    hashes against the local files, run edits.validate, then
                    DELETE the edit. Nothing is published. Safe to repeat.
  --commit          the same, then edits.commit, then re-read the live listing
                    in a fresh (deleted) edit and compare it to the folder.
                    Run this at release time only, after the release edit has
                    been committed — committing one edit makes other open edits
                    for the app stale.

  python3 scripts/play_listing_upload.py --validate-only \\
      --sa ~/projects/tutor-guardian/scripts/play_service_account.json

Piping through tee/tail hides the exit code — check ${PIPESTATUS[0]}, not $?.

The folder (default docs/brand/store/listing_1.0.73/) holds listing.json and one
sub-folder per language:  ar/ → «ar»,  en/ → «en-US»  (LANG_DIRS below). Each has
icon.png, feature_graphic.png and phone_01*.png … phone_08*.png.

Credentials: the service-account JSON (PLAY_SERVICE_ACCOUNT or --sa; default
scripts/play_service_account.json, git-ignored, mode 600). Only its path is
handled here — its contents are never printed. API errors are reported as the
error class + HTTP status + Play's reason, never request bodies.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

PACKAGE = 'com.alsaba.almorabbi'
SCOPES = ['https://www.googleapis.com/auth/androidpublisher']
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / 'docs/brand/store/listing_1.0.73'
DEFAULT_SA = REPO_ROOT / 'scripts/play_service_account.json'
LANG_DIRS = {'ar': 'ar', 'en': 'en-US'}  # folder → Play language code

# Play Console limits (Store listing → graphics / text).
TITLE_MAX, SHORT_MAX, FULL_MAX = 30, 80, 4000
SHOT_MIN_SIDE, SHOT_MAX_SIDE, SHOT_MAX_BYTES = 320, 3840, 8 * 1024 * 1024
SHOTS_MIN, SHOTS_MAX = 2, 8
ICON_SIZE, ICON_MAX_BYTES = (512, 512), 1024 * 1024
FEATURE_SIZE, FEATURE_MAX_BYTES = (1024, 500), 15 * 1024 * 1024

PNG_SIG = b'\x89PNG\r\n\x1a\n'
# PNG colour types: 2 = RGB (24-bit), 6 = RGBA (32-bit).
PNG_RGB, PNG_RGBA = 2, 6


class ListingError(ValueError):
    """The local listing folder breaks a Play rule — caught before any API call."""


# ── local checks ──────────────────────────────────────────────────────────────
def png_info(path):
    """(width, height, colour_type, bit_depth) from the PNG header — no Pillow needed."""
    with open(path, 'rb') as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != PNG_SIG or head[12:16] != b'IHDR':
        raise ListingError(f'{path.name}: not a PNG file')
    width, height, depth, colour = struct.unpack('>IIBB', head[16:26])
    return width, height, colour, depth


def check_text(lang, listing):
    for key in ('title', 'shortDescription', 'fullDescription'):
        if not isinstance(listing.get(key), str) or not listing[key].strip():
            raise ListingError(f'{lang}: {key} is missing or empty')
    for key, limit in (('title', TITLE_MAX), ('shortDescription', SHORT_MAX), ('fullDescription', FULL_MAX)):
        if len(listing[key]) > limit:
            raise ListingError(f'{lang}: {key} is {len(listing[key])} characters — Play allows {limit}')
    if '\n' in listing['title'] or '\n' in listing['shortDescription']:
        raise ListingError(f'{lang}: title and short description must be one line')


def check_screenshot(path):
    w, h, colour, depth = png_info(path)
    if colour != PNG_RGB or depth != 8:
        raise ListingError(f'{path.name}: screenshots must be 24-bit PNG without alpha')
    if not (SHOT_MIN_SIDE <= min(w, h) and max(w, h) <= SHOT_MAX_SIDE):
        raise ListingError(f'{path.name}: {w}x{h} — each side must be {SHOT_MIN_SIDE}–{SHOT_MAX_SIDE} px')
    if w * 16 != h * 9 and h * 16 != w * 9:
        raise ListingError(f'{path.name}: {w}x{h} is not 9:16 or 16:9')
    if path.stat().st_size > SHOT_MAX_BYTES:
        raise ListingError(f'{path.name}: larger than 8 MB')


def check_icon(path):
    w, h, colour, depth = png_info(path)
    if (w, h) != ICON_SIZE or colour != PNG_RGBA or depth != 8:
        raise ListingError(f'{path.name}: the icon must be a 512x512 32-bit PNG')
    if path.stat().st_size > ICON_MAX_BYTES:
        raise ListingError(f'{path.name}: the icon is larger than 1 MB')


def check_feature(path):
    w, h, colour, depth = png_info(path)
    if (w, h) != FEATURE_SIZE or colour != PNG_RGB or depth != 8:
        raise ListingError(f'{path.name}: the feature graphic must be a 1024x500 24-bit PNG without alpha')
    if path.stat().st_size > FEATURE_MAX_BYTES:
        raise ListingError(f'{path.name}: the feature graphic is too large')


def load_listing(folder):
    """Read and check the whole folder. Returns {play_lang: {...}} — raises ListingError."""
    folder = Path(folder)
    try:
        text = json.loads((folder / 'listing.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ListingError(f'cannot read {folder / "listing.json"}: {type(exc).__name__}') from None
    out = {}
    for sub, lang in LANG_DIRS.items():
        if lang not in text:
            raise ListingError(f'listing.json has no «{lang}» entry')
        listing = {k: text[lang].get(k) for k in ('title', 'shortDescription', 'fullDescription')}
        check_text(lang, listing)
        d = folder / sub
        icon, feature = d / 'icon.png', d / 'feature_graphic.png'
        shots = sorted(d.glob('phone_*.png'))
        if not icon.exists() or not feature.exists():
            raise ListingError(f'{sub}/: icon.png and feature_graphic.png are both required')
        check_icon(icon)
        check_feature(feature)
        if not SHOTS_MIN <= len(shots) <= SHOTS_MAX:
            raise ListingError(f'{sub}/: {len(shots)} phone screenshots — Play takes {SHOTS_MIN}–{SHOTS_MAX}')
        for s in shots:
            check_screenshot(s)
        out[lang] = {'text': listing, 'images': {'icon': [icon], 'featureGraphic': [feature],
                                                 'phoneScreenshots': shots}}
    extra = set(text) - set(LANG_DIRS.values())
    if extra:
        raise ListingError(f'listing.json has languages without a folder: {sorted(extra)}')
    return out


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── Play edit ─────────────────────────────────────────────────────────────────
def _upload_media(path):
    from googleapiclient.http import MediaFileUpload
    return MediaFileUpload(str(path), mimetype='image/png', resumable=False)


def stage(edits, edit_id, listings, media=None, log=print):
    """Upload text and graphics into the open edit and prove Play holds exactly them."""
    media = media or _upload_media
    have = {x['language'] for x in edits.listings().list(packageName=PACKAGE, editId=edit_id)
            .execute().get('listings', [])}
    missing = set(listings) - have
    if missing:
        # A language not on the store yet would be created silently — refuse instead.
        raise ListingError(f'Play listing has no {sorted(missing)} (has {sorted(have)})')
    for lang, data in listings.items():
        t = data['text']
        # patch, not update: update is a PUT that would clear the promo video.
        edits.listings().patch(packageName=PACKAGE, editId=edit_id, language=lang,
                               body={'language': lang, **t}).execute()
        log(f'  {lang}: text — title {len(t["title"])}/{TITLE_MAX}, short {len(t["shortDescription"])}'
            f'/{SHORT_MAX}, full {len(t["fullDescription"])}/{FULL_MAX}')
        for kind, files in data['images'].items():
            edits.images().deleteall(packageName=PACKAGE, editId=edit_id, language=lang,
                                     imageType=kind).execute()
            for f in files:
                edits.images().upload(packageName=PACKAGE, editId=edit_id, language=lang,
                                      imageType=kind, media_body=media(f)).execute()
            got = [i.get('sha256') for i in edits.images().list(
                packageName=PACKAGE, editId=edit_id, language=lang, imageType=kind).execute().get('images', [])]
            want = [sha256(f) for f in files]
            if got != want:
                raise ListingError(f'{lang}/{kind}: Play holds {len(got)} image(s) that do not match the '
                                   f'{len(want)} local file(s) in order')
            log(f'  {lang}: {kind} ×{len(files)} — Play hashes match')


def verify_live(edits, listings, log=print):
    """After commit: read the live listing through a throw-away edit and compare."""
    edit_id = edits.insert(packageName=PACKAGE, body={}).execute()['id']
    try:
        for lang, data in listings.items():
            live = edits.listings().get(packageName=PACKAGE, editId=edit_id, language=lang).execute()
            for key, value in data['text'].items():
                if live.get(key) != value:
                    raise ListingError(f'{lang}: live {key} differs from listing.json after commit')
            for kind, files in data['images'].items():
                got = [i.get('sha256') for i in edits.images().list(
                    packageName=PACKAGE, editId=edit_id, language=lang, imageType=kind).execute().get('images', [])]
                if got != [sha256(f) for f in files]:
                    raise ListingError(f'{lang}/{kind}: live images differ from the folder after commit')
            log(f'  {lang}: live listing matches the folder')
    finally:
        edits.delete(packageName=PACKAGE, editId=edit_id).execute()


def run(service, listings, *, commit, media=None, log=print):
    """Returns a receipt dict. Never commits unless commit=True; always deletes an uncommitted edit."""
    edits = service.edits()
    edit_id = edits.insert(packageName=PACKAGE, body={}).execute()['id']
    committed = False
    try:
        stage(edits, edit_id, listings, media=media, log=log)
        edits.validate(packageName=PACKAGE, editId=edit_id).execute()
        log('  edits.validate: OK')
        if commit:
            edits.commit(packageName=PACKAGE, editId=edit_id).execute()
            committed = True
            log('  edits.commit: OK')
    finally:
        if not committed:
            # A failed cleanup is a failure, not a green receipt.
            edits.delete(packageName=PACKAGE, editId=edit_id).execute()
            log('  edit deleted — nothing published')
    if committed:
        verify_live(edits, listings, log=log)
    return {'package': PACKAGE, 'languages': sorted(listings), 'validated': True,
            'committed': committed, 'edit_deleted': not committed}


def _describe(exc):
    status = getattr(getattr(exc, 'resp', None), 'status', None)
    reason = getattr(exc, 'reason', None) or (str(exc) if isinstance(exc, ListingError) else '')
    return ' '.join(str(x) for x in (type(exc).__name__, status, reason[:300] if reason else None) if x)


def build_service(sa_path):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    if not Path(sa_path).is_file():
        raise ListingError(f'service-account file not found: {sa_path}')
    creds = service_account.Credentials.from_service_account_file(str(sa_path), scopes=SCOPES)
    return build('androidpublisher', 'v3', credentials=creds, cache_discovery=False)


def main(argv=None, service_factory=build_service):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--validate-only', action='store_true', help='validate in Play, then delete the edit')
    mode.add_argument('--commit', action='store_true', help='validate, commit, then verify the live listing')
    p.add_argument('--dir', type=Path, default=DEFAULT_DIR, help=f'listing folder (default: {DEFAULT_DIR})')
    p.add_argument('--sa', type=Path, default=Path(os.environ.get('PLAY_SERVICE_ACCOUNT', DEFAULT_SA)),
                   help='service-account JSON path (env PLAY_SERVICE_ACCOUNT)')
    args = p.parse_args(argv)
    try:
        listings = load_listing(args.dir)
        counts = ', '.join(f'{lang} ({len(v["images"]["phoneScreenshots"])} shots)' for lang, v in listings.items())
        print(f'Local checks OK: {counts}')
        receipt = run(service_factory(args.sa), listings, commit=args.commit)
    except Exception as exc:  # noqa: BLE001 — report class/status/reason only
        print(f'FAILED: {_describe(exc)}' + ('' if args.commit else ' — nothing committed'), file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
