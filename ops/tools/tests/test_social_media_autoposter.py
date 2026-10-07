"""Offline regression tests: importing/selecting/dry-running must never publish."""
import copy
import importlib.util
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('autoposter', ROOT / 'ops/tools/social_media_autoposter.py')
poster = importlib.util.module_from_spec(SPEC)
with patch.dict(os.environ):
    SPEC.loader.exec_module(poster)


class CuratedSocialTipsTests(unittest.TestCase):
    def test_reads_curated_ids_and_verbatim_text(self):
        expected = [json.loads(p.read_text()) for p in sorted((ROOT / 'knowledge_base/curriculum/daily_tips').glob('*.json'))]
        actual = poster.parse_tips()
        self.assertEqual([(t['id'], t['text']) for t in actual], [(t['id'], t['text']) for t in expected])
        self.assertEqual(len(actual), len({t['id'] for t in actual}))

    def test_age_groups_use_generic_graphics_never_legacy_cards(self):
        expected = {'0-3': 'social_announce_square.webp', '2-3': 'social_announce_square.webp',
                    '4-6': 'social_feature_ai.webp', '7-9': 'social_feature_ai.webp',
                    '10-12': 'social_feature_journey.webp', '13-15': 'social_feature_journey.webp',
                    '16-18': 'social_feature_journey.webp', 'prenatal-1': 'social_announce_square.webp'}
        for tip in poster.parse_tips():
            source = json.loads((ROOT / 'knowledge_base/curriculum/daily_tips' / (tip['id'] + '.json')).read_text())
            self.assertEqual(tip['image'], expected[source['age_group']])
            self.assertTrue((ROOT / 'docs/marketing/launch_graphics' / tip['image']).is_file())

    def test_legacy_state_unchanged_when_selecting_first_curated_tip(self):
        state = {'last_posted_id': 14, 'history': [{'tip_id': n} for n in list(range(1, 31)) + list(range(1, 15))]}
        before = copy.deepcopy(state)
        tips = poster.parse_tips()
        self.assertEqual(poster.select_next_tip(tips, state), tips[0])
        self.assertEqual(state, before)

    def test_missing_curated_cursor_skips_already_posted_curated_ids(self):
        tips = poster.parse_tips()
        state = {'last_posted_id': 14, 'history': [{'tip_id': 1}, {'tip_id': tips[0]['id']}, {'tip_id': tips[1]['id']}]}
        self.assertEqual(poster.select_next_tip(tips, state), tips[2])

    def test_curated_cursor_advances_and_wraps_by_stable_id(self):
        tips = poster.parse_tips()
        for position in (0, len(tips) - 1):
            state = {'last_posted_id': 14, 'curated_last_posted_id': tips[position]['id'], 'history': []}
            self.assertEqual(poster.select_next_tip(tips, state), tips[(position + 1) % len(tips)])

    def test_deleted_cursor_does_not_repost_history(self):
        tips = poster.parse_tips()
        state = {'last_posted_id': 14, 'curated_last_posted_id': 'tip_removed', 'history': [{'tip_id': tips[0]['id']}]}
        self.assertEqual(poster.select_next_tip(tips, state), tips[1])

    def test_empty_bank_has_no_next_tip(self):
        self.assertIsNone(poster.select_next_tip([], {'last_posted_id': 14, 'history': []}))

    def test_recording_curated_success_preserves_legacy_cursor_and_history(self):
        state = {'last_posted_id': 14, 'history': [{'tip_id': 14, 'posted_at': 'old'}]}
        poster.record_posted_tip(state, poster.parse_tips()[0], True, False)
        self.assertEqual(state['last_posted_id'], 14)
        self.assertEqual(state['history'][0], {'tip_id': 14, 'posted_at': 'old'})
        self.assertEqual(state['curated_last_posted_id'], poster.parse_tips()[0]['id'])
        self.assertEqual(state['history'][-1]['tip_id'], state['curated_last_posted_id'])

    def test_duplicate_curated_ids_fail_before_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ('a', 'b'):
                (path / (name + '.json')).write_text(json.dumps({'id': 'tip_7-9_001', 'age_group': '7-9', 'text': 'نصيحة'}))
            with patch.object(poster, 'TIPS_DIR', path, create=True), self.assertRaises(ValueError):
                poster.parse_tips()

    def test_missing_generic_image_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(poster, 'DOCS_DIR', Path(directory)):
            self.assertTrue(all(tip['image'] is None for tip in poster.parse_tips()))

    def test_explicit_drafts_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for number, published in ((1, False), (2, True)):
                (path / f'{number}.json').write_text(json.dumps({'id': f'tip_7-9_{number:03}', 'age_group': '7-9', 'text': 'نصيحة', 'is_published': published}))
            with patch.object(poster, 'TIPS_DIR', path):
                self.assertEqual([t['id'] for t in poster.parse_tips()], ['tip_7-9_002'])

    def test_corrupt_state_fails_closed_instead_of_restarting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{invalid')
            with patch.object(poster, 'STATE_FILE', path), self.assertRaises(ValueError):
                poster.load_state()

    def test_missing_image_dry_run_omits_url_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(poster, 'DOCS_DIR', Path(directory)), patch.object(poster.requests, 'post', side_effect=AssertionError('network forbidden')), patch.object(poster, 'save_state') as save, patch('sys.argv', ['autoposter', '--dry-run']):
            poster.main()
        save.assert_not_called()

    def test_dry_run_does_not_network_or_write_state(self):
        state = {'last_posted_id': 14, 'history': [{'tip_id': 14}]}
        with patch.object(poster, 'load_state', return_value=state), patch.object(poster, 'save_state') as save, patch.object(poster.requests, 'post', side_effect=AssertionError('network forbidden')), patch('sys.argv', ['autoposter', '--dry-run']):
            poster.main()
        save.assert_not_called()
        self.assertEqual(state, {'last_posted_id': 14, 'history': [{'tip_id': 14}]})

    def test_explicit_curated_id_dry_run(self):
        with patch.object(poster, 'load_state', return_value={'last_posted_id': 14, 'history': []}), patch.object(poster, 'save_state') as save, patch.object(poster.requests, 'post', side_effect=AssertionError('network forbidden')), patch('sys.argv', ['autoposter', '--post-id', 'tip_7-9_001', '--dry-run']):
            poster.main()
        save.assert_not_called()


class TelegramPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tokens = patch.multiple(poster, TG_BOT_TOKEN='test-token', TG_CHANNEL_ID='test-channel')
        self.tokens.start()
        self.addCleanup(self.tokens.stop)
        self.network = patch.object(poster.requests, 'post')
        self.post = self.network.start()
        self.addCleanup(self.network.stop)
        self.response = Mock()
        self.response.json.return_value = {'ok': True}
        self.post.return_value = self.response

    def assert_message(self, text):
        self.post.assert_called_once_with(
            'https://api.telegram.org/bottest-token/sendMessage',
            data={'chat_id': 'test-channel', 'text': text, 'parse_mode': 'HTML'}, timeout=15)

    def test_no_image_sends_exact_escaped_html_message(self):
        text = poster.format_post_text({'category': '<عمر>&', 'text': '<script> & نص'})
        self.assertIn('(&lt;عمر&gt;&amp;)', text)
        self.assertIn('&lt;script&gt; &amp; نص', text)
        self.assertTrue(poster.post_to_telegram(text, None))
        self.assert_message(text)

    def test_missing_image_sends_exact_message(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(poster.post_to_telegram('نصيحة', Path(directory) / 'missing.png'))
        self.assert_message('نصيحة')

    def test_photo_at_1024_has_exact_multipart_payload(self):
        # Entities and wrapper markup do not count toward Telegram's parsed limit.
        text = '<b>' + '&amp;' * 1024 + '</b>'
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'photo.png'
            image.write_bytes(b'image-bytes')
            def inspect(url, **kwargs):
                self.assertEqual(url, 'https://api.telegram.org/bottest-token/sendPhoto')
                self.assertEqual(set(kwargs), {'files', 'data', 'timeout'})
                self.assertEqual(kwargs['timeout'], 15)
                self.assertEqual(kwargs['data'], {'chat_id': 'test-channel', 'caption': text, 'parse_mode': 'HTML'})
                self.assertEqual(set(kwargs['files']), {'photo'})
                self.assertEqual(kwargs['files']['photo'].read(), b'image-bytes')
                return self.response
            self.post.side_effect = inspect
            self.assertTrue(poster.post_to_telegram(text, image))
        self.assertEqual(self.post.call_count, 1)

    def test_caption_over_1024_uses_message_without_truncation(self):
        text = 'ن' * 1025
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'photo.png'
            image.write_bytes(b'image')
            self.assertTrue(poster.post_to_telegram(text, image))
        self.assert_message(text)

    def test_message_at_4096_is_sent_intact(self):
        text = '<b>' + 'ن' * 4096 + '</b>'
        self.assertTrue(poster.post_to_telegram(text, None))
        self.assert_message(text)

    def test_message_over_4096_is_rejected_without_network(self):
        self.assertFalse(poster.post_to_telegram('ن' * 4097, None))
        self.post.assert_not_called()

    def test_astral_characters_use_conservative_utf16_limit(self):
        self.assertFalse(poster.post_to_telegram('🤍' * 2049, None))
        self.post.assert_not_called()

    def test_api_error_is_not_success(self):
        self.response.json.return_value = {'ok': False, 'description': 'rejected'}
        self.assertFalse(poster.post_to_telegram('نصيحة', None))

    def test_all_curated_formatted_captions_fit_telegram_photo_limit(self):
        # Independent calculation, including escaping, against the full real bank.
        import html
        lengths = [(t['id'], len(html.unescape(poster.format_post_text(t).replace('<b>', '').replace('</b>', '')).encode('utf-16-le')) // 2) for t in poster.parse_tips()]
        self.assertEqual(len(lengths), 220)
        self.assertLessEqual(max(n for _, n in lengths), 1024)


if __name__ == '__main__':
    unittest.main()
