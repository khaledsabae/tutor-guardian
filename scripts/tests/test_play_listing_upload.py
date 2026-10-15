"""Store-listing refresh; fake Play client, no network, no credentials."""
import contextlib
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]


def load_tool():
    spec = importlib.util.spec_from_file_location('play_listing_upload', ROOT / 'scripts/play_listing_upload.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def png(path, w, h, colour=2, seed=0):
    """A real, tiny-bodied PNG with the given header (2=RGB, 6=RGBA)."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    ihdr = struct.pack('>IIBBBBB', w, h, 8, colour, 0, 0, 0)
    body = zlib.compress(bytes([seed % 256]) * 16)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', body) + chunk(b'IEND', b''))


TEXT = {'ar': {'title': 'المربّي', 'shortDescription': 'مجاني 100%', 'fullDescription': 'مجاني 100% — بلا إعلانات ولا اشتراكات'},
        'en-US': {'title': 'Al-Morabbi', 'shortDescription': '100% free', 'fullDescription': '100% free — no ads'}}


def make_folder(root, shots=8, text=TEXT):
    (root / 'listing.json').write_text(json.dumps(text, ensure_ascii=False), encoding='utf-8')
    for sub in ('ar', 'en'):
        d = root / sub
        d.mkdir()
        png(d / 'icon.png', 512, 512, colour=6, seed=1)
        png(d / 'feature_graphic.png', 1024, 500, seed=2)
        for i in range(shots):
            png(d / f'phone_{i + 1:02d}_screen.png', 1080, 1920, seed=10 + i + (100 if sub == 'en' else 0))
    return root


class Request:
    def __init__(self, play, name, kwargs, value):
        self.play, self.name, self.kwargs, self.value = play, name, kwargs, value

    def execute(self):
        self.play.calls.append((self.name, self.kwargs))
        if self.play.fail_at == self.name:
            raise RuntimeError(self.name)
        return self.value() if callable(self.value) else self.value


class Play:
    """Just enough of androidpublisher v3 edits(): it stores uploads like Play does."""

    def __init__(self, languages=('ar', 'en-US'), fail_at=None, tamper=False):
        self.calls, self.fail_at, self.tamper = [], fail_at, tamper
        self.languages = list(languages)
        self.stored = {}   # (lang, kind) -> [sha256]
        self.text = {}

    # resource accessors
    def edits(self):
        return self

    def listings(self):
        return self

    def images(self):
        return self

    def _r(self, name, kwargs, value=None):
        return Request(self, name, kwargs, value if value is not None else {})

    # edits
    def insert(self, **kw):
        return self._r('insert', kw, {'id': 'our-edit'})

    def validate(self, **kw):
        return self._r('validate', kw)

    def commit(self, **kw):
        return self._r('commit', kw)

    def delete(self, **kw):
        return self._r('delete', kw)

    # listings — `list` is shared with images, told apart by imageType
    def list(self, **kw):
        if 'imageType' in kw:
            key = (kw['language'], kw['imageType'])
            return self._r('images.list', kw, lambda: {'images': [{'sha256': s} for s in self.stored.get(key, [])]})
        return self._r('listings.list', kw, {'listings': [{'language': x} for x in self.languages]})

    def patch(self, **kw):
        def apply():
            self.text[kw['language']] = kw['body']
            return kw['body']
        return self._r('listings.patch', kw, apply)

    def get(self, **kw):
        return self._r('listings.get', kw, lambda: self.text.get(kw['language'], {}))

    def update(self, **kw):
        raise AssertionError('listings.update is a PUT that clears the promo video — use patch')

    def deleteall(self, **kw):
        def apply():
            self.stored[(kw['language'], kw['imageType'])] = []
            return {}
        return self._r('images.deleteall', kw, apply)

    def upload(self, **kw):
        def apply():
            digest = hashlib.sha256(Path(kw['media_body']).read_bytes()).hexdigest()
            if self.tamper:
                digest = '0' * 64
            self.stored.setdefault((kw['language'], kw['imageType']), []).append(digest)
            return {'image': {'sha256': digest}}
        return self._r('images.upload', kw, apply)


class LocalChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_folder_loads_both_languages(self):
        listings = self.tool.load_listing(make_folder(self.root))
        self.assertEqual(sorted(listings), ['ar', 'en-US'])
        self.assertEqual(len(listings['ar']['images']['phoneScreenshots']), 8)

    def test_text_limits_are_enforced(self):
        for key, limit in (('title', 30), ('shortDescription', 80), ('fullDescription', 4000)):
            text = json.loads(json.dumps(TEXT))
            text['ar'][key] = 'م' * (limit + 1)
            with tempfile.TemporaryDirectory() as t:
                with self.assertRaisesRegex(self.tool.ListingError, key):
                    self.tool.load_listing(make_folder(Path(t), text=text))

    def test_text_at_the_limit_passes(self):
        text = json.loads(json.dumps(TEXT))
        text['ar'].update(title='م' * 30, shortDescription='م' * 80, fullDescription='م' * 4000)
        self.tool.load_listing(make_folder(self.root, text=text))

    def test_screenshot_must_be_9_16_without_alpha(self):
        make_folder(self.root)
        png(self.root / 'ar' / 'phone_03_screen.png', 1080, 2400)
        with self.assertRaisesRegex(self.tool.ListingError, '9:16'):
            self.tool.load_listing(self.root)
        png(self.root / 'ar' / 'phone_03_screen.png', 1080, 1920, colour=6)
        with self.assertRaisesRegex(self.tool.ListingError, 'alpha'):
            self.tool.load_listing(self.root)

    def test_screenshot_side_limits(self):
        make_folder(self.root)
        for w, h in ((2250, 4000), (180, 320)):  # both exactly 9:16, one side out of range
            png(self.root / 'en' / 'phone_01_screen.png', w, h)
            with self.assertRaisesRegex(self.tool.ListingError, '320–3840'):
                self.tool.load_listing(self.root)

    def test_more_than_eight_screenshots_is_refused(self):
        make_folder(self.root, shots=9)
        with self.assertRaisesRegex(self.tool.ListingError, '9 phone screenshots'):
            self.tool.load_listing(self.root)

    def test_icon_and_feature_graphic_formats(self):
        make_folder(self.root)
        png(self.root / 'ar' / 'icon.png', 512, 512, colour=2)
        with self.assertRaisesRegex(self.tool.ListingError, 'icon'):
            self.tool.load_listing(self.root)
        root2 = Path(tempfile.mkdtemp(dir=self.tmp.name))
        make_folder(root2)
        png(root2 / 'en' / 'feature_graphic.png', 1024, 500, colour=6)
        with self.assertRaisesRegex(self.tool.ListingError, 'feature graphic'):
            self.tool.load_listing(root2)


class EditFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.listings = self.tool.load_listing(make_folder(Path(self.tmp.name)))
        self.log = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, play, commit):
        return self.tool.run(play, self.listings, commit=commit, media=lambda p: p, log=self.log.append)

    def names(self, play):
        return [c[0] for c in play.calls]

    def test_validate_only_validates_then_deletes_and_never_commits(self):
        play = Play()
        receipt = self.run_tool(play, commit=False)
        names = self.names(play)
        self.assertNotIn('commit', names)
        self.assertEqual(names[0], 'insert')
        self.assertEqual(names[-2:], ['validate', 'delete'])
        self.assertEqual(receipt, {'package': 'com.alsaba.almorabbi', 'languages': ['ar', 'en-US'],
                                   'validated': True, 'committed': False, 'edit_deleted': True})

    def test_every_call_targets_our_package_and_edit(self):
        play = Play()
        self.run_tool(play, commit=False)
        for name, kw in play.calls:
            self.assertEqual(kw.get('packageName'), 'com.alsaba.almorabbi', name)
            if name != 'insert':
                self.assertEqual(kw.get('editId'), 'our-edit', name)

    def test_all_three_image_kinds_replaced_for_both_languages_in_order(self):
        play = Play()
        play.stored[('ar', 'phoneScreenshots')] = ['old'] * 5
        self.run_tool(play, commit=False)
        for lang in ('ar', 'en-US'):
            for kind in ('icon', 'featureGraphic', 'phoneScreenshots'):
                files = self.listings[lang]['images'][kind]
                self.assertEqual(play.stored[(lang, kind)], [self.tool.sha256(f) for f in files], (lang, kind))
        deletes = [(kw['language'], kw['imageType']) for n, kw in play.calls if n == 'images.deleteall']
        self.assertEqual(len(deletes), 6)
        self.assertEqual(len(set(deletes)), 6)

    def test_text_patched_not_put_for_both_languages(self):
        play = Play()
        self.run_tool(play, commit=False)
        for lang in ('ar', 'en-US'):
            self.assertEqual({k: play.text[lang][k] for k in TEXT[lang]}, TEXT[lang])
            self.assertEqual(play.text[lang]['language'], lang)

    def test_missing_store_language_is_refused_and_edit_deleted(self):
        play = Play(languages=('ar',))
        with self.assertRaisesRegex(self.tool.ListingError, 'en-US'):
            self.run_tool(play, commit=False)
        self.assertNotIn('listings.patch', self.names(play))
        self.assertEqual(self.names(play)[-1], 'delete')

    def test_hash_mismatch_fails_before_validate_and_deletes(self):
        play = Play(tamper=True)
        with self.assertRaisesRegex(self.tool.ListingError, 'do not match'):
            self.run_tool(play, commit=True)
        names = self.names(play)
        self.assertNotIn('validate', names)
        self.assertNotIn('commit', names)
        self.assertEqual(names[-1], 'delete')

    def test_validate_failure_deletes_and_never_commits(self):
        play = Play(fail_at='validate')
        with self.assertRaises(RuntimeError):
            self.run_tool(play, commit=True)
        self.assertNotIn('commit', self.names(play))
        self.assertEqual(self.names(play)[-1], 'delete')

    def test_failed_cleanup_is_not_a_green_receipt(self):
        play = Play(fail_at='delete')
        with self.assertRaisesRegex(RuntimeError, 'delete'):
            self.run_tool(play, commit=False)

    def test_commit_then_live_listing_is_reread_and_compared(self):
        play = Play()
        receipt = self.run_tool(play, commit=True)
        names = self.names(play)
        self.assertEqual(names.count('commit'), 1)
        after = names[names.index('commit') + 1:]
        # a fresh read-only edit, compared, then deleted; the committed edit is never deleted
        self.assertEqual(after[0], 'insert')
        self.assertIn('listings.get', after)
        self.assertEqual(after[-1], 'delete')
        self.assertEqual(names[:names.index('commit')].count('delete'), 0)
        self.assertTrue(receipt['committed'])
        self.assertFalse(receipt['edit_deleted'])


class Cli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_a_mode_is_required(self):
        with self.assertRaises(SystemExit):
            self.tool.main([], service_factory=lambda sa: Play())

    def test_modes_are_exclusive(self):
        with self.assertRaises(SystemExit):
            self.tool.main(['--validate-only', '--commit'], service_factory=lambda sa: Play())

    def test_bad_folder_fails_before_any_api_call(self):
        made = []
        with tempfile.TemporaryDirectory() as t:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = self.tool.main(['--validate-only', '--dir', t], service_factory=lambda sa: made.append(sa) or Play())
        self.assertEqual(rc, 1)
        self.assertIn('nothing committed', err.getvalue())
        self.assertEqual(made, [])

    def test_validate_only_exit_zero_and_no_commit(self):
        play = Play()
        with tempfile.TemporaryDirectory() as t:
            make_folder(Path(t))
            orig = self.tool._upload_media
            self.tool._upload_media = lambda p: p
            try:
                rc = self.tool.main(['--validate-only', '--dir', t, '--sa', '/nonexistent'],
                                    service_factory=lambda sa: play)
            finally:
                self.tool._upload_media = orig
        self.assertEqual(rc, 0)
        self.assertNotIn('commit', [c[0] for c in play.calls])

    def test_the_real_folder_passes_local_checks(self):
        folder = ROOT / 'docs/brand/store/listing_1.0.73'
        if not folder.exists():
            self.skipTest('listing folder not generated yet')
        listings = self.tool.load_listing(folder)
        self.assertEqual({lang: len(v['images']['phoneScreenshots']) for lang, v in listings.items()},
                         {'ar': 8, 'en-US': 8})
        self.assertTrue(listings['ar']['text']['fullDescription'].startswith('مجاني 100% — بلا إعلانات ولا اشتراكات'))


if __name__ == '__main__':
    unittest.main()
