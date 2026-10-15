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
