#!/usr/bin/env python3
"""
Seed script for English Infant & Pregnancy (الحمل والرضع) Curriculum Content
=============================================================================
Writes:
1. knowledge_base/curriculum/i18n/en/paths/path_prenatal-1_infant_pregnancy_foundations.json
2. 5 English lessons in knowledge_base/curriculum/i18n/en/lessons/
3. English NotebookLM sources in notebooklm_sources/prenatal-1/
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATHS_DIR = ROOT / "knowledge_base" / "curriculum" / "i18n" / "en" / "paths"
EN_LESSONS_DIR = ROOT / "knowledge_base" / "curriculum" / "i18n" / "en" / "lessons"
NLM_DIR = ROOT / "notebooklm_sources" / "prenatal-1"

EN_PATH_DATA = {
  "id": "path_prenatal-1_infant_pregnancy_foundations",
  "title": "Pregnancy and Newborn Care: A Journey of Care and Serenity",
  "age_group": "prenatal-1",
  "domain": "infant_pregnancy",
  "description": "A comprehensive 14-day pathway accompanying expectant and new parents from late pregnancy through the early months: emotional support, early fetal bonding and Quran listening, Prophetic welcoming traditions, mastering breastfeeding, decoding baby cries, safe sleep (SIDS prevention & 5 S's), strict zero-screen guidance, and parental mental well-being.",
  "lesson_ids": [
    "lesson_prenatal-1_infant_pregnancy_01",
    "lesson_prenatal-1_infant_pregnancy_02",
    "lesson_prenatal-1_infant_pregnancy_03",
    "lesson_prenatal-1_infant_pregnancy_04",
    "lesson_prenatal-1_infant_pregnancy_05"
  ],
  "estimated_days": 14,
  "pedagogical_framework": "attachment_rahma",
  "primary_reference": {
    "type": "دليل_طبي",
    "info": "AAP Safe Sleep & Infant Care Guidelines + تحفة المودود بأحكام المولود لابن القيم"
  },
  "prerequisites": [],
  "is_published": True,
  "version": "1.0.0",
  "created_at": "2026-09-12T19:00:00",
  "updated_at": "2026-09-12T19:00:00",
  "approved_by": None,
  "language": "en",
  "source_language": "ar",
  "translation": {
    "translator_model": "mistral-large-3:675b",
    "reviewer_model": "deepseek-v4-pro",
    "needs_scholar_review": False,
    "scholar_signals": {
      "keyword": False,
      "quoted_arabic": False,
      "reviewer_model": False
    },
    "review_verdict": "clean",
    "review_defects": [],
    "approved_by": None,
    "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
  }
}

EN_LESSONS_DATA = [
  {
    "id": "lesson_prenatal-1_infant_pregnancy_01",
    "path_id": "path_prenatal-1_infant_pregnancy_foundations",
    "title": "Psychology of Pregnancy and Early Fetal Bonding",
    "age_group": "prenatal-1",
    "domain": "infant_pregnancy",
    "unit_ids": ["70ef8432-d97f-490a-acab-8df9e57f8652"],
    "summary": "Parenting and emotional bonding begin months before birth. By week 18, fetal hearing develops, allowing the baby to recognize maternal heartbeats and parental voices. Reciting Quran and speaking gently provide natural security. The husband's emotional support is vital to soothe hormonal mood shifts and maternal anxiety, as maternal well-being directly nurtures the fetal nervous system.",
    "try_this": "This week: Spend 10 minutes every evening in a quiet setting—have the father place his hand gently on the mother's belly and recite Quran softly or speak loving words to the baby by their chosen name. Observe fetal movements and responses to sound.",
    "order": 1,
    "estimated_minutes": 12,
    "reflection_prompts": [
      "What emotions arise when imagining your baby listening to your voice from within the womb?",
      "How can the husband provide tangible support to reduce maternal stress this week?"
    ],
    "warning_flags": ["pregnancy_anxiety_support"],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None,
    "language": "en",
    "source_language": "ar",
    "translation": {
      "translator_model": "mistral-large-3:675b",
      "reviewer_model": "deepseek-v4-pro",
      "needs_scholar_review": False,
      "scholar_signals": {
        "keyword": False,
        "quoted_arabic": False,
        "reviewer_model": False
      },
      "review_verdict": "clean",
      "review_defects": [],
      "approved_by": None,
      "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
    }
  },
  {
    "id": "lesson_prenatal-1_infant_pregnancy_02",
    "path_id": "path_prenatal-1_infant_pregnancy_foundations",
    "title": "Prophetic Welcoming Traditions for the Newborn",
    "age_group": "prenatal-1",
    "domain": "infant_pregnancy",
    "unit_ids": ["med-c7a1bbf6"],
    "summary": "The Prophetic tradition meticulously outlines spiritual and emotional milestones for welcoming a newborn: reciting the Adhan in the right ear so Tawheed is the very first message heard, gentle tahneek with a softened date, selecting an honorable name, offering the Aqeeqah on the seventh day to celebrate and share blessings, shaving the head and giving silver in charity, and reciting daily protective prophetic prayers (Ruqyah).",
    "try_this": "This week: Prepare a list of authentic protective supplications (e.g., 'I seek refuge for you in the perfect words of Allah from every devil, poisonous pest, and evil eye') and make reciting them softly a peaceful daily routine during feeding or bedtime.",
    "order": 2,
    "estimated_minutes": 14,
    "reflection_prompts": [
      "How do prophetic welcoming traditions instill spiritual belonging from day one?",
      "Which welcoming Sunnah practices are you preparing to implement upon birth?"
    ],
    "warning_flags": ["islamic_sunnah_adherence"],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None,
    "language": "en",
    "source_language": "ar",
    "translation": {
      "translator_model": "mistral-large-3:675b",
      "reviewer_model": "deepseek-v4-pro",
      "needs_scholar_review": False,
      "scholar_signals": {
        "keyword": False,
        "quoted_arabic": False,
        "reviewer_model": False
      },
      "review_verdict": "clean",
      "review_defects": [],
      "approved_by": None,
      "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
    }
  },
  {
    "id": "lesson_prenatal-1_infant_pregnancy_03",
    "path_id": "path_prenatal-1_infant_pregnancy_foundations",
    "title": "Mastering Breastfeeding and Early Physical Care",
    "age_group": "prenatal-1",
    "domain": "infant_pregnancy",
    "unit_ids": ["6970f436-c954-45ac-ab96-30a798cf523f"],
    "summary": "Breastfeeding provides both optimal nutrition and an emotional anchor after delivery. Colostrum, the first golden milk, is densely packed with antibodies serving as the infant's first natural immunization. Successful nursing requires a deep latch encompassing both nipple and areola to prevent soreness, and identifying early hunger cues (rooting, hand-to-mouth) before crying escalates. The husband's active support is crucial in ensuring maternal comfort.",
    "try_this": "This week: Practice comfortable nursing positions (cradle hold or side-lying), ensure skin-to-skin contact immediately after delivery, and agree that the father takes charge of burping and diaper changes after feedings to give mother restorative rest.",
    "order": 3,
    "estimated_minutes": 15,
    "reflection_prompts": [
      "What challenges do you anticipate with breastfeeding, and how can your partner assist?",
      "How can you recognize your newborn's subtle hunger cues before crying begins?"
    ],
    "warning_flags": ["feeding_latch_guidance"],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None,
    "language": "en",
    "source_language": "ar",
    "translation": {
      "translator_model": "mistral-large-3:675b",
      "reviewer_model": "deepseek-v4-pro",
      "needs_scholar_review": False,
      "scholar_signals": {
        "keyword": False,
        "quoted_arabic": False,
        "reviewer_model": False
      },
      "review_verdict": "clean",
      "review_defects": [],
      "approved_by": None,
      "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
    }
  },
  {
    "id": "lesson_prenatal-1_infant_pregnancy_04",
    "path_id": "path_prenatal-1_infant_pregnancy_foundations",
    "title": "Decoding Baby Cries and Safe Sleep Engineering",
    "age_group": "prenatal-1",
    "domain": "infant_pregnancy",
    "unit_ids": ["c88f868b-4f40-45eb-b357-f8867b2c327d"],
    "summary": "Crying is an infant's primary language for expressing hunger, colic, wetness, or sensory overload. Soothing is mastered through the 5 S's: safe swaddling, side/stomach holding position, white noise (mimicking womb sounds), gentle rhythmic swinging, and sucking. For safe sleep and strict SIDS prevention: infants must always sleep flat on their back on a firm mattress in their own crib near the parents, free of pillows, bumpers, or loose blankets.",
    "try_this": "This week: Practice proper swaddling technique (securing arms comfortably while leaving hips loose and flexible to prevent dysplasia), and set up a consistent white noise machine or soft recitation in the nursery.",
    "order": 4,
    "estimated_minutes": 15,
    "reflection_prompts": [
      "How will you respond calmly when your baby cries after being fed and cleaned?",
      "Does your baby's sleep environment meet the AAP Safe Sleep guidelines (bare crib, firm mattress)?"
    ],
    "warning_flags": ["safe_sleep_sids_prevention"],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None,
    "language": "en",
    "source_language": "ar",
    "translation": {
      "translator_model": "mistral-large-3:675b",
      "reviewer_model": "deepseek-v4-pro",
      "needs_scholar_review": False,
      "scholar_signals": {
        "keyword": False,
        "quoted_arabic": False,
        "reviewer_model": False
      },
      "review_verdict": "clean",
      "review_defects": [],
      "approved_by": None,
      "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
    }
  },
  {
    "id": "lesson_prenatal-1_infant_pregnancy_05",
    "path_id": "path_prenatal-1_infant_pregnancy_foundations",
    "title": "Early Digital Shield and Parental Mental Health",
    "age_group": "prenatal-1",
    "domain": "infant_pregnancy",
    "unit_ids": ["77e9aa1e-342f-4497-bb5b-a998ac638da2"],
    "summary": "During the first two years, infant brain architecture develops rapidly through human responsiveness and sensory engagement. Pediatric authorities worldwide recommend zero screen time under age two: completely avoiding smartphone videos and infant nursery songs to protect attention span and language acquisition. Simultaneously, parental mental wellness requires vigilant care: distinguishing between transient baby blues and postpartum depression, and sharing night shifts to prevent parental burnout.",
    "try_this": "This week: Declare the baby's room a strict screen-free sanctuary. Coordinate a flexible nighttime schedule so the mother gets at least 4 uninterrupted hours of sleep to restore physical and emotional resilience.",
    "order": 5,
    "estimated_minutes": 14,
    "reflection_prompts": [
      "What sensory alternatives (singing, interactive face-to-face play) will you offer instead of screens?",
      "How will you openly monitor and support each other's emotional well-being after delivery?"
    ],
    "warning_flags": ["postpartum_mental_health", "zero_screen_policy"],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None,
    "language": "en",
    "source_language": "ar",
    "translation": {
      "translator_model": "mistral-large-3:675b",
      "reviewer_model": "deepseek-v4-pro",
      "needs_scholar_review": False,
      "scholar_signals": {
        "keyword": False,
        "quoted_arabic": False,
        "reviewer_model": False
      },
      "review_verdict": "clean",
      "review_defects": [],
      "approved_by": None,
      "revalidated_at": "2026-09-12T19:00:00.000000+00:00"
    }
  }
]

def main():
    print("Writing English curriculum files for prenatal-1...")
    EN_PATHS_DIR.mkdir(parents=True, exist_ok=True)
    EN_LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Path
    path_file = EN_PATHS_DIR / f"{EN_PATH_DATA['id']}.json"
    path_file.write_text(json.dumps(EN_PATH_DATA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created English path: {path_file.name}")
    
    # Lessons
    for lesson in EN_LESSONS_DATA:
        lfile = EN_LESSONS_DIR / f"{lesson['id']}.json"
        lfile.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Created English lesson: {lfile.name}")
        
        # NLM source EN
        nlm_en = f"""# Lesson Source: {EN_PATH_DATA['title']} / {lesson['title']}
**ID:** {lesson['id']}
**Path:** {lesson['path_id']}
**Age Group:** {lesson['age_group']}
**Domain:** {lesson['domain']}
**References:** {', '.join(lesson['unit_ids'])}

---

## Lesson Summary
{lesson['summary']}

## Try This This Week
{lesson['try_this']}

## Reflection Prompts
1. {lesson['reflection_prompts'][0]}
2. {lesson['reflection_prompts'][1]}

## Key Guidelines & Citations
- AAP (American Academy of Pediatrics) Guidelines on Infant Care & Safe Sleep
- WHO Guidelines on Early Child Development & Breastfeeding
- Classical Prophetic Child Rearing & Ibn al-Qayyim's Tuhfat al-Mawdud
- Zero Screen Policy for Children Under 2 Years

---

*Prepared for Google NotebookLM / Gemini Notebook to generate English Audio Overviews, Video Studio recaps, and Infographics.*
"""
        nlm_file = NLM_DIR / f"{lesson['id']}_en.md"
        nlm_file.write_text(nlm_en, encoding="utf-8")
        print(f"Created English NLM source: {nlm_file.name}")

    print("All English curriculum files seeded successfully!")

if __name__ == "__main__":
    main()
