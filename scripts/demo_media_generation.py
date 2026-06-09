#!/usr/bin/env python3
import os
import json
import subprocess
import asyncio
import argparse

# Configuration
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
SOURCE_ID = "e265bfe0-2602-4493-adb4-233c72505d9c" # lesson_16-18_medical_adult_transition_03
OUTPUT_DIR = "/home/khalednew/projects/tutor-guardian/docs"

SUMMARY_PROMPT = """قم بتلخيص الدرس المحدد بأسلوب "القراءة السريعة في دقيقة واحدة". للدرس، استخرج النقاط التالية بدقة بالغة وبأسلوب نقاط (Bullet points) جذاب:
1. **الخلاصة الكبرى**: الفكرة الأساسية للدرس في جملة واحدة مكثفة.
2. **المحفز السلوكي**: ما هي العلامة أو السلوك الذي يجب أن ينتبه إليه الأهل؟
3. **خطوات اليوم**: 3 إجراءات عملية يمكن للأب أو الأم البدء بها حالاً.
4. **منظور تربوي إسلامي**: لفتة تربوية أو خلق إسلامي يعززه هذا الدرس.
تجنب الحشو والعبارات الإنشائية الجافة، واجعل التنسيق متسقاً ومهيأً للقراءة المريحة على شاشات الموبايل الصغيرة."""

FLASHCARDS_PROMPT = """بناءً على الدرس المحدد في المساحة، قم بتوليد مجموعة من الفلاش كاردز (Flashcards) التفاعلية للأهل.
كل بطاقة يجب أن تتبع الهيكل التالي بدقة وتكتب بلغة عربية مبسطة وواضحة جداً:
- **المجال والفئة العمرية**
- **الوجه الأول (الموقف التربوي/السؤال)**: موقف واقعي محفز للتفكير أو سؤال مباشر يواجهه الأهل في الحياة اليومية.
- **الوجه الثاني (الإجراء السريع - Action Plan)**: 3 خطوات عملية مكتوبة باختصار شديد لتطبيق الحل فوراً.

صغ المخرجات في جدول Markdown نظيف ومقسم كالتالي:
| الفئة والمجال | الوجه الأول (السؤال/الموقف) | الوجه الثاني (الحل في 3 خطوات) |"""

SLIDES_PROMPT = """قم بتحويل الدرس المحدد إلى "حقيبة عرض عائلي تفاعلي" مقسمة كشرائح عروض تقديمية (Slides). 
لكل شريحة، حدد بوضوح:
- **عنوان الشريحة**: عنوان مشوق وجاذب للأبناء.
- **المحتوى البصري المقترح**: وصف لما يجب رسمه أو إظهاره في الشريحة.
- **الرسالة الأساسية**: الفكرة التي يشرحها الأب أو الأم بأسلوب شيق.
- **سؤال للنقاش العائلي**: سؤال مفتوح يوجه للأبناء لفتح باب الحوار والاستماع إليهم.
- **نشاط عملي جماعي**: لعبة أو نشاط حركي مدته 5 دقائق يرسخ قيمة الدرس في الجلسة."""

async def run_query(prompt, prompt_type):
    print(f"Generating {prompt_type} using NotebookLM ask...")
    cmd = [
        "./notebooklm_env/bin/notebooklm", "ask",
        "-n", NOTEBOOK_ID,
        "-s", SOURCE_ID,
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
        print(f"Error generating {prompt_type}: {error_msg}")
        return f"### Error generating {prompt_type}\n{error_msg}"
        
    return stdout.decode().strip()

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("Starting Demo Media Generation for Lesson...")
    
    # 1. Generate Summary
    summary = await run_query(SUMMARY_PROMPT, "Summary")
    
    # 2. Generate Flashcards
    flashcards = await run_query(FLASHCARDS_PROMPT, "Flashcards")
    
    # 3. Generate Slides
    slides = await run_query(SLIDES_PROMPT, "Slides")
    
    # Assemble the final markdown report
    report = f"""# مخرجات تجربة توليد الوسائط لدرس الانتقال الطبي لفئة 16-18 سنة

تم توليد هذه الوسائط تلقائياً باستخدام **Google NotebookLM** والـ Prompts المخصصة في خطة العمل.

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
    
    report_path = os.path.join(OUTPUT_DIR, "lesson_demo_assets.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"\nSaved all generated textual assets to: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
