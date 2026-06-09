#!/usr/bin/env python3
import os
import asyncio

NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
PDF_SOURCE_ID = "050f2c4a-85df-4aa8-aa5e-a852545a0f3b" # parents-guide-learning-disabilities.pdf
OUTPUT_DIR = "/home/khalednew/projects/tutor-guardian/docs"

GROUNDED_SUMMARY_PROMPT = """قم بتلخيص فصل أو استراتيجية هامة من الكتاب المرجعي المرفق بأسلوب "ملخص دقيقة واحدة".
شروط التوليد الصارمة:
- اعتمد كلياً وحصرياً على الكتاب المرجعي (دليل صعوبات التعلم للوالدين) ولا تضف أي فكرة خارجية أو نصيحة عامة.
- استخرج النقاط التالية بدقة بالغة وبأسلوب نقاط جذاب مع الاستشهاد بالقسم أو رقم الصفحة بين معقوفين:
1. **الخلاصة الكبرى**: الفكرة الأساسية في جملة واحدة مكثفة.
2. **المحفز السلوكي/العلامة**: السلوك أو الصعوبة الفعلية التي تشير إليها صفحات الكتاب.
3. **خطوات التدخل**: 3 إجراءات عملية منصوص عليها في هذا الفصل للتعامل مع الموقف ومساعدة الطفل.
4. **شواهد التأصيل**: عبارة أو اقتباس مباشر من المرجع يؤكد هذه الاستراتيجية."""

GROUNDED_FLASHCARDS_PROMPT = """بناءً على ملف الكتاب المرجعي المحدد (دليل صعوبات التعلم للوالدين) حصرياً، قم بتوليد مجموعة من الفلاش كاردز (Flashcards) التفاعلية للأهل.
شروط التوليد الصارمة:
- استخرج مواقف حقيقية أو صعوبات سلوكية/تعليمية معينة مذكورة في المرجع.
- يجب أن تكون الحلول في الوجه الثاني مطابقة تماماً للتوجيهات والخطوات الموصى بها في هذا الدليل دون تعديل أو إضافة خارجية.
- ممنوع استخدام أي معرفة عامة.

صغ المخرجات في جدول Markdown نظيف ومقسم كالتالي:
| المرجع والقسم المستند إليه | الوجه الأول (الموقف/الصعوبة من الكتاب) | الوجه الثاني (الحل المعتمد من الكتاب في 3 خطوات) |"""

async def run_query(prompt, prompt_type):
    print(f"Generating Grounded {prompt_type} from PDF book...")
    cmd = [
        "./notebooklm_env/bin/notebooklm", "ask",
        "-n", NOTEBOOK_ID,
        "-s", PDF_SOURCE_ID,
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
    
    summary = await run_query(GROUNDED_SUMMARY_PROMPT, "Grounded Summary")
    flashcards = await run_query(GROUNDED_FLASHCARDS_PROMPT, "Grounded Flashcards")
    
    report = f"""# مخرجات تجربة التوليد المؤصل كلياً من كتاب صعوبات التعلم (PDF)

تم توليد هذه الوسائط بالاعتماد **الحصري والصارم** على المرجع المرفوع: `parents-guide-learning-disabilities.pdf`.

---

## 📄 أولاً: ملخص القراءة السريعة المؤصل (Grounded Summary)

{summary}

---

## 🃏 ثانياً: الفلاش كاردز المؤصلة (Grounded Flashcards)

{flashcards}
"""
    
    report_path = os.path.join(OUTPUT_DIR, "grounded_demo_assets.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"\nSaved grounded assets to: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
