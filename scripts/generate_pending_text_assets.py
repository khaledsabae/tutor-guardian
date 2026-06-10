#!/usr/bin/env python3
import os
import json
import asyncio
import argparse

# Configuration
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
OUTPUT_DIR = "/home/khalednew/projects/tutor-guardian/docs"

# Remaining source IDs that need text assets generation
PENDING_SOURCES = [
    {"source_id": "5fb6588e-d31a-4cca-8e0c-052b364a72ac", "name": "cyber_digital_citizenship_02"},
    {"source_id": "440183bc-479c-49c1-bb07-fe35fa62295f", "name": "islamic_parenting_identity_01"},
    {"source_id": "55fb8fb3-2eed-4eb2-9940-0a1e07d3e951", "name": "islamic_parenting_identity_02"},
    {"source_id": "bc41f39f-97ae-4af2-80dd-b070907a80e4", "name": "islamic_parenting_identity_03"},
    {"source_id": "dab0fff1-8180-4a3f-99ae-6791b243d690", "name": "islamic_parenting_identity_04"},
    {"source_id": "42bc52b6-7d36-486f-aa79-e98ea5dcb4c9", "name": "medical_puberty_wellbeing_02"},
    {"source_id": "20e00eef-fa60-4165-9364-ef869223c0f6", "name": "medical_puberty_wellbeing_03"},
    {"source_id": "f7e6f02d-39fb-4888-ae4a-9e0644e75f5e", "name": "cyber_digital_maturity_03"},
    {"source_id": "4086896f-0dd6-4a28-bade-c8032b18e9d1", "name": "islamic_parenting_teen_identity_02"},
]

SUMMARY_PROMPT = """قم بتلخيص الدرس المحدد بأسلوب "القراءة السريعة في دقيقة واحدة". للدرس، استخرج النقاط التالية بدقة بالغة وبأسلوب نقاط (Bullet points) جذاب:
1. **الخلاصة الكبرى**: الفكرة الأساسية للدرس في جملة واحدة مكثفة.
2. **المحفز السلوكي/العلامة**: ما هي العلامة أو السلوك الذي يجب أن ينتبه إليه الأهل؟
3. **خطوات اليوم**: 3 إجراءات عملية يمكن للأب أو الأم البدء بها حالاً.
4. **شواهد التأصيل**: عبارة أو اقتباس مباشر من الدرس يؤكد هذه الاستراتيجية.
شروط التوليد الصارمة:
- اعتمد كلياً وحصرياً على الدرس المحدد ولا تضف أي فكرة خارجية أو نصيحة عامة."""

FLASHCARDS_PROMPT = """بناءً على الدرس المحدد حصرياً، قم بتوليد مجموعة من الفلاش كاردز (Flashcards) التفاعلية للأهل.
كل بطاقة يجب أن تتبع الهيكل التالي بدقة وتكتب بلغة عربية مبسطة وواضحة جداً:
- **المجال والفئة العمرية**
- **الوجه الأول (الموقف التربوي/السؤال)**: موقف واقعي محفز للتفكير أو سؤال مباشر يواجهه الأهل في الحياة اليومية.
- **الوجه الثاني (الإجراء السريع - Action Plan)**: 3 خطوات عملية مكتوبة باختصار شديد لتطبيق الحل فوراً.
شروط التوليد الصارمة:
- اعتمد كلياً وحصرياً على المرجع المحدد ولا تضف أي نصائح عامة.

صغ المخرجات في جدول Markdown نظيف ومقسم كالتالي:
| الفئة والمجال | الوجه الأول (السؤال/الموقف) | الوجه الثاني (الحل في 3 خطوات) |"""

SLIDES_PROMPT = """قم بتحويل الدرس المحدد إلى "حقيبة عرض عائلي تفاعلي" مقسمة كشرائح عروض تقديمية (Slides). 
لكل شريحة، حدد بوضوح:
- **عنوان الشريحة**: عنوان مشوق وجاذب للأبناء.
- **المحتوى البصري المقترح**: وصف لما يجب رسمه أو إظهاره في الشريحة.
- **الرسالة الأساسية**: الفكرة التي يشرحها الأب أو الأم بأسلوب مبسط.
- **سؤال للنقاش العائلي**: سؤال مفتوح يوجه للأبناء لفتح باب الحوار والاستماع إليهم.
- **نشاط عملي جماعي**: لعبة أو نشاط حركي مدته 5 دقائق يرسخ قيمة الدرس في الجلسة.
شروط التوليد الصارمة:
- اعتمد كلياً وحصرياً على المرجع المحدد ولا تضف أي نصائح عامة."""

async def run_query(prompt, prompt_type, source_id):
    print(f"  Generating {prompt_type} for source {source_id[:8]}...", end=" ", flush=True)
    cmd = [
        "./notebooklm_env/bin/notebooklm", "ask",
        "-n", NOTEBOOK_ID,
        "-s", source_id,
        "--new", "-y",
        prompt
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        print(f"❌ Error: {error_msg[:100]}")
        return f"### Error generating {prompt_type}\n{error_msg}"
    
    print("✅")
    return stdout.decode().strip()

async def generate_text_assets(source_info):
    source_id = source_info["source_id"]
    name = source_info["name"]
    
    print(f"\n{'='*60}")
    print(f"Processing: {name} (source: {source_id})")
    print(f"{'='*60}")
    
    # 1. Generate Summary
    summary = await run_query(SUMMARY_PROMPT, "Summary", source_id)
    
    # 2. Generate Flashcards
    flashcards = await run_query(FLASHCARDS_PROMPT, "Flashcards", source_id)
    
    # 3. Generate Slides
    slides = await run_query(SLIDES_PROMPT, "Slides", source_id)
    
    # Assemble report
    report = f"""# مخرجات الدرس: {name}

تم توليد هذه الأصول التربوية باستخدام **Google NotebookLM** بالتأصيل الصارم على مصادر الدرس.

---

## 📄 أولاً: ملخص القراءة السريعة (Quick Summary)

{summary}

---

## 🃏 ثانياً: الفلاش كاردز التفاعلية (Flashcards)

{flashcards}

---

## 📊 ثالثاً: شرائح الجلسات العائلية (Family Slides)

{slides}
"""
    
    # Save markdown report
    report_path = os.path.join(OUTPUT_DIR, f"{name}_assets.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 Saved textual assets to: {report_path}")
    
    return report_path

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"Starting text assets generation for {len(PENDING_SOURCES)} source IDs...")
    
    for source_info in PENDING_SOURCES:
        try:
            await generate_text_assets(source_info)
            # Small delay between requests to be respectful
            await asyncio.sleep(2)
        except Exception as e:
            print(f"❌ Failed for {source_info['name']}: {e}")
    
    print(f"\n✅ All text generation complete!")

if __name__ == "__main__":
    asyncio.run(main())