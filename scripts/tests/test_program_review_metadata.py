"""Program reviewer metadata must describe model review without specialist approval."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = {
    'milestones': 'glm-5.2 (every item) + mistral-large-3 (first fasting, puberty)',
    'prayer_journey': 'glm-5.2 (every item)',
    'ramadan_family': 'glm-5.2 (every item) + deepseek-v4-pro (days 4–6, fasting ladder)',
}
REVIEW = ' + PR #23 software/model review of content safety (not human specialist approval)'


class ProgramReviewMetadataTests(unittest.TestCase):
    def test_review_is_explicitly_software_not_human_specialist_approval(self):
        checked = 0
        for language in ('programs', 'i18n/en/programs'):
            for program, models in PROGRAMS.items():
                path = ROOT / 'knowledge_base/curriculum' / language / f'{program}.json'
                with self.subTest(path=str(path.relative_to(ROOT))):
                    data = json.loads(path.read_text(encoding='utf-8'))
                    reviewer = data['generation']['reviewer_model']
                    self.assertEqual(reviewer, models + REVIEW)
                    self.assertNotIn('sharia/medical/child-safety review', reviewer)
                    checked += 1
        self.assertEqual(checked, 6)
