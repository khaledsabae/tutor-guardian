#!/usr/bin/env python3
import asyncio
import os

async def run_query(prompt, source_id):
    cmd = [
        './notebooklm_env/bin/notebooklm', 'ask',
        '-n', '94f191e6-cfbc-4655-a0d7-c8f7ad0f2287',
        '-s', source_id,
        '--new', '-y',
        prompt
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    return stdout.decode().strip() if process.returncode == 0 else f'ERROR: {stderr.decode().strip()[:200]}'

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
- اعتد كلياً وحصرياً على المرجع المحدد ولا تضف أي نصائح عامة.
صغ المخرجات في جدول Markdown نظيف ومقسم كالتالي:
| الفئة والمجال | الوجه الأول (السؤال/الموقف) | الوجه الثاني (الحل في 3 خطوات) |"""

SLIDES_PROMPT = """قم بتحويل الدرس المحدد إلى "حقيبة عرض عائلي تفاعلي" مقسمة كشرائح عروض تقديمية (Slides). 
لكل شريحة، حدد بوضوح:
- **عنوان الشريحة**: عنوان مشوق وجاذب للأبناء.
- **المحتوى البصري المقترح**: وصف لما يجب رسمه أو إظهاره في الشريحة.
- **الرسالة الأساسية**: الفكرة التي يشرحها الأب أو الأم بأسلوب مبسط.
- **سؤال للنقاش العائلي": سؤال مفتوح يوجه للأبناء لفتح باب الحوار والاستماع إليهم.
- **نشاط عملي جماعي**: لعبة أو نشاط حركي مدته 5 دقائق يرسخ قيمة الدرس في الجلسة.
شروط التوليد الصارمة:
- اعتمد كلياً وحصرياً على المرجع المحدد ولا تضف أي نصائح عامة."""

async def get_all(source_id):
    s = await run_query(SUMMARY_PROMPT, source_id)
    f = await run_query(FLASHCARDS_PROMPT, source_id)
    sl = await run_query(SLIDES_PROMPT, source_id)
    return s, f, sl

def save_report(name, summary, flashcards, slides):
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
    path = f'/home/khalednew/projects/tutor-guardian/docs/{name}_assets.md'
    with open(path, 'w', encoding='utf-8') as ff:
        ff.write(report)
    print(f'Saved: {path}')

async def main():
    print('Fetching bc41f39f (islamic_parenting_identity_03)...')
    s1, f1, sl1 = await get_all('bc41f39f-97ae-4af2-80dd-b070907a80e4')
    save_report('islamic_parenting_identity_03', s1, f1, sl1)
    
    print('Fetching 55fb8fb3 (islamic_parenting_identity_02)...')
    s2, f2, sl2 = await get_all('55fb8fb3-2eed-4eb2-9940-0a1e07d3e951')
    save_report('islamic_parenting_identity_02', s2, f2, sl2)
    
    print('Fetching 20e00eef (medical_puberty_wellbeing_03)...')
    s3, f3, sl3 = await get_all('20e00eef-fa60-4165-9364-ef869223c0f6')
    save_report('medical_puberty_wellbeing_03', s3, f3, sl3)
    
    print('Done!')

asyncio.run(main())