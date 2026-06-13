#!/usr/bin/env python3
import os
import json
import asyncio
import re

NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
INDEX_PATH = "docs/lesson_index.json"
MAP_PATH = "/tmp/lesson_source_map.json"

# Defining 4 lessons for age group 2-3 with the corresponding source PDFs
TODDLER_LESSONS = [
    {
        "lesson_id": "lesson_2-3_development_independence_01",
        "title_ar": "التدريب على استخدام المرحاض والاعتماد على النفس",
        "topic_path": "development_early_moments",
        "source_id": "7f442885-f7b8-4c8d-bd1f-c0c19a9332bf", # kayfa-turabbi-waladan-saliman.pdf
        "source_title": "kayfa-turabbi-waladan-saliman.pdf"
    },
    {
        "lesson_id": "lesson_2-3_cyber_routine_02",
        "title_ar": "تنظيم النوم والتعامل الصحي مع الشاشات",
        "topic_path": "cyber_screen_foundations",
        "source_id": "77faf382-1cf8-4100-b6c8-52b86cc741d4", # WHO_Sleep_Physical_Activity_Under5.pdf
        "source_title": "WHO_Sleep_Physical_Activity_Under5.pdf"
    },
    {
        "lesson_id": "lesson_2-3_development_language_03",
        "title_ar": "التطور اللغوي والمعرفي من خلال اللعب التخيلي",
        "topic_path": "development_early_moments",
        "source_id": "fd6d2b2e-eebb-424a-84eb-c22501a24d5e", # early-social-communication-toddlers.pdf
        "source_title": "early-social-communication-toddlers.pdf"
    },
    {
        "lesson_id": "lesson_2-3_islamic_tantrums_04",
        "title_ar": "الرابطة الآمنة والتعامل مع نوبات الغضب برفق",
        "topic_path": "islamic_parenting_attachment",
        "source_id": "050f2c4a-85df-4d6d-8cc7-e32049d5bf1c", # parents-guide-limit-setting.pdf
        "source_title": "parents-guide-limit-setting.pdf"
    }
]

FLASHCARDS_PROMPT_TEMPLATE = """بناءً على هذا المرجع، قم بتوليد 5 بطاقات تعليمية (Flashcards) تفاعلية للآباء باللغة العربية حول موضوع: {title}
كل بطاقة يجب أن تحتوي على:
1. الوجه الأول: سؤال أو موقف تربوي يواجهه الأب/الأم.
2. الوجه الثاني: الإجراء العملي السريع المعتمد على المرجع.
صغ الناتج كـ JSON فقط بالصيغة التالية (بدون أي نصوص إضافية أو علامات markdown):
{{
  "title": "{title} — بطاقات",
  "cards": [
    {{
      "front": "السؤال هنا؟",
      "back": "الحل هنا"
    }}
  ]
}}"""

QUIZ_PROMPT_TEMPLATE = """بناءً على هذا المرجع، قم بتوليد اختبار تفاعلي (Quiz) من 3 أسئلة اختيار من متعدد باللغة العربية حول موضوع: {title}
كل سؤال يجب أن يحتوي على:
1. نص السؤال.
2. 3 خيارات إجابة (مع تحديد الخيار الصحيح بـ true والباقي false).
3. تفسير (rationale) لكل إجابة.
4. تلميح (hint) للسؤال.
صغ الناتج كـ JSON فقط بالصيغة التالية (بدون أي نصوص إضافية أو علامات markdown):
{{
  "title": "{title} — اختبار",
  "questions": [
    {{
      "question": "السؤال هنا؟",
      "answerOptions": [
        {{
          "text": "الخيار 1",
          "isCorrect": true,
          "rationale": "التفسير هنا"
        }},
        {{
          "text": "الخيار 2",
          "isCorrect": false,
          "rationale": "التفسير هنا"
        }}
      ],
      "hint": "تلميح"
    }}
  ]
}}"""

async def ask_notebooklm(prompt):
    cmd = [
        "./notebooklm_env/bin/notebooklm", "ask",
        "-n", NOTEBOOK_ID,
        "--new", "-y",
        prompt
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        return stdout.decode().strip()
    return ""

def clean_json_string(raw_str):
    # Find the outer-most curly braces to extract JSON object
    start_idx = raw_str.find('{')
    end_idx = raw_str.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = raw_str[start_idx:end_idx+1]
    else:
        cleaned = raw_str
    return cleaned.strip()

async def generate_lesson_assets(lesson):
    lesson_id = lesson["lesson_id"]
    title = lesson["title_ar"]
    source_id = lesson["source_id"]
    
    print(f"Generating assets for {lesson_id} ('{title}')...")
    
    # 1. Flashcards
    fc_prompt = FLASHCARDS_PROMPT_TEMPLATE.format(title=title)
    fc_raw = await ask_notebooklm(fc_prompt)
    fc_clean = clean_json_string(fc_raw)
    
    fc_path = f"docs/lesson_assets/flashcards/gen_{lesson_id}_fc.json"
    os.makedirs(os.path.dirname(fc_path), exist_ok=True)
    try:
        fc_data = json.loads(fc_clean, strict=False)
        with open(fc_path, "w", encoding="utf-8") as f:
            json.dump(fc_data, f, indent=2, ensure_ascii=False)
        print(f" -> Saved Flashcards to {fc_path}")
    except Exception as e:
        print(f" -> Failed to parse flashcards JSON: {e}. Raw response: {fc_clean[:200]}")
        # Save raw backup
        with open(fc_path, "w", encoding="utf-8") as f:
            f.write(fc_clean)
            
    # 2. Quiz
    qz_prompt = QUIZ_PROMPT_TEMPLATE.format(title=title)
    qz_raw = await ask_notebooklm(qz_prompt)
    qz_clean = clean_json_string(qz_raw)
    
    qz_path = f"docs/lesson_assets/quizzes/gen_{lesson_id}_qz.json"
    os.makedirs(os.path.dirname(qz_path), exist_ok=True)
    try:
        qz_data = json.loads(qz_clean, strict=False)
        with open(qz_path, "w", encoding="utf-8") as f:
            json.dump(qz_data, f, indent=2, ensure_ascii=False)
        print(f" -> Saved Quiz to {qz_path}")
    except Exception as e:
        print(f" -> Failed to parse quiz JSON: {e}. Raw response: {qz_clean[:200]}")
        with open(qz_path, "w", encoding="utf-8") as f:
            f.write(qz_clean)

    return fc_path, qz_path

async def main():
    # Generate all assets
    for lesson in TODDLER_LESSONS:
        await generate_lesson_assets(lesson)
        await asyncio.sleep(2)
        
    # Append to lesson_index.json
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            
        existing_ids = {l["lesson_id"] for l in index_data.get("lessons", [])}
        
        added_count = 0
        for lesson in TODDLER_LESSONS:
            lesson_id = lesson["lesson_id"]
            if lesson_id in existing_ids:
                print(f"Lesson {lesson_id} already exists in index. skipping.")
                continue
                
            new_lesson_entry = {
                "lesson_id": lesson_id,
                "age_group": "2-3",
                "topic_path": lesson["topic_path"],
                "source_id": lesson["source_id"],
                "title_ar": lesson["title_ar"],
                "assets": {
                    "flashcards": [
                        {
                            "id": f"gen_{lesson_id}_fc",
                            "file": f"docs/lesson_assets/flashcards/gen_{lesson_id}_fc.json",
                            "title": f"{lesson['title_ar']} — بطاقات",
                            "item_count": 5
                        }
                    ],
                    "quizzes": [
                        {
                            "id": f"gen_{lesson_id}_qz",
                            "file": f"docs/lesson_assets/quizzes/gen_{lesson_id}_qz.json",
                            "title": f"{lesson['title_ar']} — اختبار",
                            "item_count": 3
                        }
                    ],
                    "reports": [],
                    "data_tables": [],
                    "infographics": [],
                    "podcasts": []
                }
            }
            index_data["lessons"].append(new_lesson_entry)
            added_count += 1
            
        if added_count > 0:
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            print(f"Added {added_count} new toddler lessons to {INDEX_PATH}.")
            
    # Append mapping to /tmp/lesson_source_map.json
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            map_data = json.load(f)
            
        existing_map_ids = {item["lesson_id"] for item in map_data}
        added_map = 0
        for lesson in TODDLER_LESSONS:
            lesson_id = lesson["lesson_id"]
            if lesson_id in existing_map_ids:
                continue
            map_data.append({
                "lesson_id": lesson_id,
                "age_group": "2-3",
                "topic_path": lesson["topic_path"],
                "source_id": lesson["source_id"],
                "source_title": lesson["source_title"]
            })
            added_map += 1
            
        if added_map > 0:
            with open(MAP_PATH, "w", encoding="utf-8") as f:
                json.dump(map_data, f, indent=2, ensure_ascii=False)
            print(f"Added {added_map} toddler mappings to {MAP_PATH}.")

if __name__ == "__main__":
    asyncio.run(main())
