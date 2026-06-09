#!/usr/bin/env python3
import os
import json
import subprocess
import asyncio

# Configuration
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
SOURCE_ID = "e99a9c41-32ca-41e4-b4ed-f61af795642d" # age_4_6 - lesson_4-6_development_positive_parenting_01
OUTPUT_DIR = "/home/khalednew/projects/tutor-guardian/docs"

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

async def generate_podcast():
    print("Initiating Egyptian Arabic podcast generation in NotebookLM...")
    podcast_instruction = """تصرفوا كمقدمي بودكاست تربوي محترفين وودودين (رجل وامرأة)، يتناقشان بالعامية المصرية الراقية والسهلة.
شروط الحوار الصارمة:
- اعتمدوا بنسبة 100% وبشكل حصري على محتوى الدرس المحدد (المدح النوعي وبناء ثقة الطفل).
- ممنوع منعاً باتاً تقديم أي نصائح عامة أو فرضيات تربوية لم تذكر صراحة في المرجع.
- يجب على أحد المقدمين طرح المشكلة استناداً للموقف الموضح، ويقوم الآخر بسرد الحلول والخطوات التفصيلية من الدرس مع عزوها لمصدرها.
- قسّما النقاش إلى نصائح عملية قابلة للتطبيق الفوري اليوم في المنزل مستخلصة مباشرة من المرجع."""
    
    # Write instruction to temporary file
    inst_path = "/home/khalednew/projects/tutor-guardian/scripts/inst_lesson_01.txt"
    with open(inst_path, "w", encoding="utf-8") as f:
        f.write(podcast_instruction)
        
    cmd = [
        "./notebooklm_env/bin/notebooklm", "generate", "audio",
        "-n", NOTEBOOK_ID,
        "-s", SOURCE_ID,
        "--prompt-file", inst_path,
        "--language", "ar_eg",
        "--wait", "--json"
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    # Clean up temp file
    if os.path.exists(inst_path):
        os.remove(inst_path)
        
    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        print(f"Error initiating podcast generation: {error_msg}")
        return False
        
    try:
        res = json.loads(stdout.decode().strip())
        print(f"Podcast generation completed successfully! Status: {res.get('status')}")
        return True
    except Exception as e:
        print(f"Failed to parse podcast generation output: {e}")
        print(stdout.decode().strip())
        return False

async def download_podcast():
    print("Downloading the latest generated podcast...")
    output_path = os.path.join(OUTPUT_DIR, "lesson_01_podcast.mp3")
    cmd = [
        "./notebooklm_env/bin/notebooklm", "download", "audio",
        "-n", NOTEBOOK_ID,
        output_path,
        "--latest", "--force"
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        print(f"Error downloading podcast: {error_msg}")
        return False
        
    print(stdout.decode().strip())
    return True

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Text generation tasks
    summary = await run_query(SUMMARY_PROMPT, "Summary")
    flashcards = await run_query(FLASHCARDS_PROMPT, "Flashcards")
    slides = await run_query(SLIDES_PROMPT, "Slides")
    
    report = f"""# مخرجات الدرس الأول: المدح النوعي وبناء ثقة الطفل (فئة 4-6 سنوات)

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
    
    report_path = os.path.join(OUTPUT_DIR, "lesson_01_assets.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Textual assets saved to: {report_path}")
    
    # 2. Audio generation tasks
    success = await generate_podcast()
    if success:
        await download_podcast()

if __name__ == "__main__":
    asyncio.run(main())
