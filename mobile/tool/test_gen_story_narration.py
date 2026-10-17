"""The narration check: a page passes only if its transcript is the page.

Run from the repo root:  python3 -m unittest discover -s mobile/tool

The fixtures are real: `_READ_ITS_NOTES` is whisper's transcript of one of the
first samples, where the style notes were a plain prefix and the model read
them aloud before the story.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_story_narration as g  # noqa: E402

PAGE = ("كانت ليلى طفلة صغيرة تحب تأمل السماء قبل النوم. في غرفتها الدافئة، فتحت النافذة "
        "ونظرت إلى السماء الصافية المليئة بالنجوم، وقالت هامسة: «يا نجوم السماء المضيئة، "
        "هل تنامين مثلنا؟».")

# whisper small, on a clean page: its usual slips (ليلى→ليلة) and line breaks.
_CLEAN = ("كانت ليلة طفلة صغيرة تحب تأمل السماء قبل النوم\nفي غرفتها الدافئة فتحت النافذة\n"
          "ونظرت إلى السماء الصافية المليئة بالنجوم\nوقالت هامسة يا نجوم السماء المضيئة هل تنامين مثلنا؟")

_READ_ITS_NOTES = ("إقرأ النصة التالي بسوط راوين دافئ وهادئ لقصة أطفال قبل النوم\n"
                   "بالعربية الفصح السليمة ببطء ووضوح مع وقفات قصيرة عند علامات الترقيم لا تقرأ هذه التعليمات\n"
                   "كانت ليلة طفلة صغيرة تحب تأم للسماء قبل النوم\n"
                   "في غرفتها الدافئة فتحت النافذة ونظرت إلى السماء الصافية المليئة بالنجوم\n"
                   "وقالت هامسة ينجوم السماء المضيئة هل تنامين مثلنا؟")


class VerifyPage(unittest.TestCase):
    def test_a_clean_page_passes(self):
        self.assertEqual(g.verify_page(PAGE, _CLEAN, "ar"), [])

    def test_notes_read_aloud_fail(self):
        problems = g.verify_page(PAGE, _READ_ITS_NOTES, "ar")
        self.assertTrue(any("instruction word" in p for p in problems), problems)
        self.assertTrue(any("before the page text" in p for p in problems), problems)

    def test_extra_words_at_the_end_fail(self):
        problems = g.verify_page(PAGE, _CLEAN + " شكرا لكم على المشاهدة", "ar")
        self.assertTrue(any("after the page text" in p for p in problems), problems)

    def test_extra_words_at_the_start_fail_without_instruction_words(self):
        problems = g.verify_page(PAGE, "مرحبا يا أطفال اليوم " + _CLEAN, "ar")
        self.assertTrue(any("before the page text" in p for p in problems), problems)

    def test_a_different_page_fails_on_similarity(self):
        other = "كان عمر طفلا مفعما بالنشاط يحب اللعب في حديقة بيته مع أصدقائه"
        problems = g.verify_page(PAGE, other, "ar")
        self.assertTrue(any("similarity" in p for p in problems), problems)

    def test_a_word_the_page_itself_says_is_not_an_instruction(self):
        page = "ثم قال بصوت واضح: «باسم الله»."
        self.assertEqual(g.verify_page(page, "ثم قال بصوت واضح باسم الله", "ar"), [])

    def test_english(self):
        page = "Layla was a little girl who loved gazing at the sky before bedtime."
        self.assertEqual(g.verify_page(page, page, "en"), [])
        self.assertTrue(g.verify_page(page, "Style: warm storyteller. " + page, "en"))


class Sentences(unittest.TestCase):
    def test_a_quote_closing_after_the_question_mark_stays_one_sentence(self):
        spans = g.sentences(PAGE)
        self.assertEqual(len(spans), 2)
        self.assertTrue(PAGE[spans[1][0]:spans[1][1]].endswith("مثلنا؟»."))

    def test_ranges_cover_the_text_without_whitespace_edges(self):
        for a, b in g.sentences(PAGE):
            self.assertFalse(PAGE[a].isspace())
            self.assertFalse(PAGE[b - 1].isspace())


if __name__ == "__main__":
    unittest.main()


import json as _json  # noqa: E402
import tempfile as _tempfile  # noqa: E402
from unittest import mock  # noqa: E402


def _story(texts, sid="s1"):
    return {"id": sid, "pages": [{"pageNumber": i + 1, "text": t} for i, t in enumerate(texts)]}


class Resume(unittest.TestCase):
    """Re-running the same --all command records only what is missing."""

    def setUp(self):
        self.tmp = Path(_tempfile.mkdtemp())
        self.calls = []
        g.REPORT.clear()

        def fake_synth(text, *a, **k):
            self.calls.append(text)
            return b"\x10\x00" * 2400

        def fake_encode(pcm, out):
            Path(out).write_bytes(b"m4a")

        self.patches = [
            mock.patch.object(g, "synth", side_effect=fake_synth),
            mock.patch.object(g, "encode_m4a", side_effect=fake_encode),
            mock.patch.object(g, "transcribe", side_effect=lambda path, lang: self.heard[path.name]),
        ]
        for p in self.patches:
            p.start()
        self.heard = {}

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def run_all(self, stories, voice="Algieba", force=False):
        for s in stories:
            for i, page in enumerate(s["pages"], start=1):
                self.heard[f"{s['id']}_p{i}.m4a"] = page["text"]
        self.calls.clear()
        return g.run(stories, "ar", voice, "m", self.tmp, "docs/x", "key", force=force)

    def test_a_current_story_is_skipped(self):
        s = _story(["أ ب ت ث.", "ج ح خ د."])
        self.assertEqual(self.run_all([s]), 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.run_all([s]), 0)
        self.assertEqual(self.calls, [])

    def test_only_a_changed_page_is_recorded_again(self):
        s = _story(["أ ب ت ث.", "ج ح خ د."])
        self.run_all([s])
        s["pages"][1]["text"] = "ذ ر ز س."
        self.run_all([s])
        self.assertEqual(self.calls, ["ذ ر ز س."])
        manifest = _json.loads((self.tmp / "s1.json").read_text(encoding="utf-8"))
        self.assertEqual([p["text"] for p in manifest["pages"]], ["أ ب ت ث.", "ذ ر ز س."])

    def test_a_partial_story_without_a_manifest_is_redone(self):
        s = _story(["أ ب ت ث.", "ج ح خ د."])
        (self.tmp / "s1_p1.m4a").write_bytes(b"left over")
        self.run_all([s])
        self.assertEqual(len(self.calls), 2)

    def test_another_voice_or_force_records_again(self):
        s = _story(["أ ب ت ث."])
        self.run_all([s])
        self.run_all([s], voice="Sulafat")
        self.assertEqual(len(self.calls), 1)
        self.run_all([s], voice="Sulafat", force=True)
        self.assertEqual(len(self.calls), 1)

    def test_a_spent_quota_stops_the_run_and_keeps_finished_stories(self):
        a, b, c = _story(["أ ب ت ث."], "a"), _story(["ج ح خ د."], "b"), _story(["ذ ر ز س."], "c")
        for s in (a, b, c):
            self.heard[f"{s['id']}_p1.m4a"] = s["pages"][0]["text"]

        def synth_then_quota(text, *args, **kw):
            self.calls.append(text)
            if text.startswith("ج"):
                raise g.QuotaExhausted("429")
            return b"\x10\x00" * 2400

        with mock.patch.object(g, "synth", side_effect=synth_then_quota):
            code = g.run([a, b, c], "ar", "Algieba", "m", self.tmp, "docs/x", "key")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls, ["أ ب ت ث.", "ج ح خ د."])  # c never tried
        self.assertTrue((self.tmp / "a.json").exists())
        self.assertFalse((self.tmp / "b.json").exists())
        # The verification report survives the stop.
        self.assertTrue(list(self.tmp.glob("verify_ar_*.json")))


class QuotaFromTheApi(unittest.TestCase):
    def test_a_429_that_outlives_the_retries_is_a_spent_quota(self):
        import io
        import urllib.error

        def always_429(*a, **k):
            raise urllib.error.HTTPError("u", 429, "quota", {}, io.BytesIO(b'{"error":"quota"}'))

        with mock.patch.object(g.urllib.request, "urlopen", side_effect=always_429), \
                mock.patch.object(g.time, "sleep"):
            with self.assertRaises(g.QuotaExhausted):
                g.synth("نص.", "ar", "Algieba", "m", "key", {})

    def test_other_http_errors_still_stop_loudly(self):
        import io
        import urllib.error

        def always_400(*a, **k):
            raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b"bad"))

        with mock.patch.object(g.urllib.request, "urlopen", side_effect=always_400):
            with self.assertRaises(SystemExit):
                g.synth("نص.", "ar", "Algieba", "m", "key", {})


class ElevenLabsEngine(unittest.TestCase):
    """eleven_* models go to ElevenLabs, return the same PCM, and stop on a spent quota."""

    def test_the_model_picks_the_engine(self):
        self.assertEqual(g.engine_of("eleven_v3"), "elevenlabs")
        self.assertEqual(g.engine_of("gemini-3.8-flash-tts"), "gemini")
        self.assertEqual(g.ENGINES["gemini"][1], "Algieba")

    def test_pcm_comes_back_and_usage_is_counted(self):
        sent = {}

        class Resp:
            headers = {"character-cost": "7"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"\x01\x00" * 10 + b"\x02"  # an odd trailing byte is dropped

        def fake_urlopen(req, timeout):
            sent["url"], sent["body"] = req.full_url, _json.loads(req.data)
            sent["key"] = req.get_header("Xi-api-key")
            return Resp()

        usage = {}
        with mock.patch.object(g.urllib.request, "urlopen", side_effect=fake_urlopen):
            pcm = g.synth("Hello there.", "en", "VOICE", "eleven_v3", "k", usage)
        self.assertEqual(len(pcm), 20)
        self.assertIn("/text-to-speech/VOICE?output_format=pcm_24000", sent["url"])
        self.assertEqual(sent["body"]["model_id"], "eleven_v3")
        self.assertEqual(sent["body"]["language_code"], "en")
        self.assertEqual(sent["key"], "k")
        self.assertEqual(usage, {"characters": 12, "credits": 7})

    def test_multilingual_v2_gets_no_language_code(self):
        bodies = []

        class Resp:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"\x00\x00"

        def fake_urlopen(req, timeout):
            bodies.append(_json.loads(req.data))
            return Resp()

        with mock.patch.object(g.urllib.request, "urlopen", side_effect=fake_urlopen):
            g.synth("نص.", "ar", "V", "eleven_multilingual_v2", "k", {})
        self.assertNotIn("language_code", bodies[0])

    def test_a_spent_quota_is_quota_exhausted(self):
        import io
        import urllib.error

        def quota(*a, **k):
            raise urllib.error.HTTPError("u", 401, "q", {}, io.BytesIO(b'{"detail":{"status":"quota_exceeded"}}'))

        with mock.patch.object(g.urllib.request, "urlopen", side_effect=quota):
            with self.assertRaises(g.QuotaExhausted):
                g.synth("Hi.", "en", "V", "eleven_v3", "k", {})

    def test_an_unknown_voice_stops_loudly(self):
        import io
        import urllib.error

        def missing(*a, **k):
            raise urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b'{"detail":"voice_not_found"}'))

        with mock.patch.object(g.urllib.request, "urlopen", side_effect=missing):
            with self.assertRaises(SystemExit):
                g.synth("Hi.", "en", "V", "eleven_v3", "k", {})
