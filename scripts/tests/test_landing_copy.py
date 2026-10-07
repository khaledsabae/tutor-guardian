"""Focused copy guards; no server startup or external services."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LandingCopyTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / 'frontend/cinematic.html').read_text()

    def test_guidance_does_not_claim_device_protection(self):
        for claim in ('يحمي أجهزتهم', 'حماية شاملة', 'حماية سيبرانية',
                      'درع الحماية الرقمية', 'الاطمئنان التام'):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, self.html)
        self.assertIn('إرشاد تربوي', self.html)
        self.assertIn('يساعدك', self.html)

    def test_screen_time_visual_is_a_family_example(self):
        self.assertIn('مثال لاتفاق أسري على وقت الشاشة', self.html)
        self.assertNotIn('وقت الشاشة المنظم اليوم', self.html)

    def test_visual_structure_and_removed_3d_stay_intact(self):
        for present in ('hero-canvas-section', 'hero-canvas', 'trust-carousel',
                        'bento-features', 'mountHeroCanvasScrubber', 'screen-stat-bar'):
            self.assertIn(present, self.html)
        for removed in ('model-3d-section', 'model-viewer', 'guardian_shield', 'مجسم'):
            self.assertNotIn(removed, self.html)
        ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        anchors = set(re.findall(r'href="#([^"]+)"', self.html))
        self.assertTrue(anchors)
        self.assertLessEqual(anchors, ids)
