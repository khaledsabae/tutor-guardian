#!/usr/bin/env python3
"""
يسحب وحدات معرفة من ملف Tarbiya_Al_Awlad_Alwan.txt
- ينظف OCR (يزيل الأسطر القصيرة والرموز)
- يقسم حسب العناوين (الباب، الفصل، إلخ) مع fallback لـ 250 كلمة
- يستهدف 30 وحدة فقط
- domain = "islamic_parenting"
- يستخدم qwen2.5:3b محلياً
- يدعم الاستئناف (resume) عبر ingest_tarbiya_alwan_progress.json
"""
import json
import os
import re
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNITS_DIR = PROJECT_ROOT / "knowledge_base" / "units"
PROGRESS_FILE = PROJECT_ROOT / "ops" / "tools" / "ingest_tarbiya_alwan_progress.json"
SOURCE_FILE = PROJECT_ROOT / "knowledge_base" / "raw_sources" / "islamic_parenting" / "Tarbiya_Al_Awlad_Alwan.txt"

_LOCAL_BASE = os.environ.get("OLLAMA_LOCAL_BASE_URL", "http://100.109.163.64:11434")
OLLAMA_URL = f"{_LOCAL_BASE.rstrip('/')}/api/generate"
MODEL = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")
TARGET_UNITS = 30

PROMPT_TEMPLATE = """أنت مساعد تربوي خبير. حلل النص التالي واستخرج وحدة معرفة بصيغة JSON فقط (بدون أي نص خارج الأقواس {{}}).
الحقول المطلوبة:
- text_simplified: ملخص واضح ومبسط للأهل (جملتان إلى 4 جمل بالعربية الفصحى).
- behavior_type: نوع السلوك أو الموضوع الرئيسي (مثال: اختيار الزوجة، التأديب، الحوار).
- age_group: اختر واحداً فقط: 0-3, 4-6, 7-9, 10-12, 13-15, 16-18, unspecified.
- severity: اختر واحداً: خفيف, متوسط, شديد, طارئ.
- intervention_type: اختر واحداً: وقائي, إرشادي, علاجي, إحالة_لطبيب.
- labels: قائمة بـ 3 وسوم عربية قصيرة.

النص:
{chunk}"""


def clean_ocr_text(text: str) -> str:
    """ينظف النص من ضوضاء OCR."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 20:
            continue
        # حساب نسبة الحروف العربية لتصفية الأسطر المليئة بالأرقام/الرموز
        arabic_chars = sum(1 for c in line if '\u0600' <= c <= '\u06FF')
        if arabic_chars < len(line) * 0.3:
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def chunk_text(text: str) -> list[str]:
    """يقسم النص حسب العناوين، ثم يقطع الأجزاء الكبيرة إلى 250 كلمة مع تداخل 50 كلمة."""
    # تقسيم استباقي حسب العناوين الشائعة
    sections = re.split(r'(?=\n?(?:الباب|الفصل|الجزء|المبحث|المقدمة|الخاتمة|أولاً|ثانياً|ثالثاً))', text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        words = section.split()
        if len(words) <= 250:
            chunks.append(section)
        else:
            # تقسيم إلى 250 كلمة مع تداخل 50 كلمة (step = 200)
            for i in range(0, len(words), 200):
                chunk_words = words[i:i+250]
                chunks.append(" ".join(chunk_words))
    return chunks


def load_progress() -> int:
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            return data.get("last_chunk_index", 0)
        except Exception:
            pass
    return 0


def save_progress(index: int):
    PROGRESS_FILE.write_text(json.dumps({"last_chunk_index": index}, ensure_ascii=False, indent=2), encoding="utf-8")


def call_ollama(chunk: str) -> dict | None:
    prompt = PROMPT_TEMPLATE.format(chunk=chunk)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 500}
    }
    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(OLLAMA_URL, json=payload)
            r.raise_for_status()
            raw = r.json().get("response", "")
            # تنظيف مخرجات markdown
            raw = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
            return json.loads(raw)
    except Exception as e:
        print(f"  ⚠️ خطأ Ollama: {e}")
        return None


def main():
    print("=" * 60)
    print("  📥 معالجة Tarbiya_Al_Awlad_Alwan.txt → وحدات معرفة")
    print("=" * 60)

    if not SOURCE_FILE.exists():
        print(f"❌ الملف غير موجود: {SOURCE_FILE}")
        return

    print("📖 جاري قراءة الملف وتنظيف OCR...")
    raw_text = SOURCE_FILE.read_text(encoding="utf-8")
    clean_text = clean_ocr_text(raw_text)
    print(f"✅ تم التنظيف: {len(raw_text)} حرف → {len(clean_text)} حرف")

    print("✂️ جاري تقسيم النص...")
    all_chunks = chunk_text(clean_text)
    print(f"📦 إجمالي الأجزاء بعد التقسيم: {len(all_chunks)}")

    # اختيار أفضل 30 جزء (الأطول والأكثر احتواءً على محتوى مفيد)
    # نفلتر الأجزاء القصيرة جداً (< 50 كلمة) ثم نأخذ أول 30
    valid_chunks = [c for c in all_chunks if len(c.split()) >= 50]
    target_chunks = valid_chunks[:TARGET_UNITS]
    print(f"🎯 تم اختيار {len(target_chunks)} جزء للمعالجة (الهدف: {TARGET_UNITS})")

    UNITS_DIR.mkdir(parents=True, exist_ok=True)
    start_idx = load_progress()
    print(f"▶️  الاستئناف من الجزء رقم: {start_idx}")

    processed = 0
    skipped = 0

    for i in range(start_idx, len(target_chunks)):
        chunk = target_chunks[i]
        print(f"\n[{i+1}/{len(target_chunks)}] جاري المعالجة...", flush=True)
        print(f"  مقتطف: {chunk[:80]}...", flush=True)

        data = call_ollama(chunk)
        if not data:
            print("  ⚠️ فشل الاستدعاء — تخطي", flush=True)
            skipped += 1
            save_progress(i + 1)
            time.sleep(2)
            continue

        # بناء وحدة المعرفة
        unit_id = f"isl-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        unit = {
            "id": unit_id,
            "domain": "islamic_parenting",
            "age_group": data.get("age_group", "unspecified"),
            "behavior_type": data.get("behavior_type", "عام"),
            "intervention_type": data.get("intervention_type", "إرشادي"),
            "severity": data.get("severity", "خفيف"),
            "reference_type": "كتاب_تربوي",
            "reference_info": "تربية الأولاد في الإسلام - علوان",
            "text_original": chunk,
            "text_simplified": data.get("text_simplified", ""),
            "labels": data.get("labels", []),
            "created_at": now,
            "updated_at": now,
            "version": "1.0.0",
            "source_meta": {
                "source_title": "تربية الأولاد في الإسلام",
                "source_author": "عبد الله ناصح علوان"
            }
        }

        out_path = UNITS_DIR / f"{unit_id}.json"
        out_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ حُفظ: {unit_id}.json | السلوك: {unit['behavior_type']} | العمر: {unit['age_group']}", flush=True)
        
        processed += 1
        save_progress(i + 1)
        time.sleep(1)  # معدل آمن لـ qwen2.5:3b المحلي

    print("\n" + "=" * 60)
    print(f"  ✅ انتهت المعالجة: {processed} وحدة جديدة")
    print(f"  ⏭️  تُخطّي: {skipped}")
    print(f"  📁 المخرجات: {UNITS_DIR}")
    # مسح ملف التقدم عند الانتهاء بنجاح
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    print("=" * 60)


if __name__ == "__main__":
    main()