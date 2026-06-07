#!/usr/bin/env python3
"""
Pipeline to ingest a source document (PDF or TXT) and convert to knowledge units.

Flow:
  1. Extract text (PDF→pdfplumber, TXT directly)
  2. Chunk by heading (## / --) or by ~500 tokens with 50 overlap
  3. Per chunk: call Ollama to generate text_simplified, behavior_type,
     suggested_age_group, suggested_severity, suggested_labels
  4. Present each unit for user approval: (a)ccept, (s)kip, (e)dit
  5. Accepted units saved to knowledge_base/data/
  6. Summary: X accepted, Y skipped

Requires: pip install pdfplumber (added to backend/requirements.txt)
"""
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "knowledge_base" / "data"
SCHEMA_PATH = PROJECT_ROOT / "knowledge_base" / "schema" / "knowledge_unit.schema.json"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:31b-cloud"

DOMAINS = ["medical", "tarbiyah", "fiqh", "cyber"]
DOMAIN_LABELS = {
    "medical": "طبي / سلوكي",
    "tarbiyah": "تربوي",
    "fiqh": "شرعي",
    "cyber": "سيبراني",
}

AGE_OPTIONS = ["0-3", "4-6", "7-9", "10-12", "13-15", "16-18"]
SEVERITY_OPTIONS = ["خفيف", "متوسط", "شديد", "طارئ"]

EXTRACTION_PROMPT = """أنت مساعد خبير في تحليل النصوص التربوية والطبية والشرعية.
للنص التالي عليك استخراج:
1. text_simplified: إعادة صياغة مبسطة بالعربية للأهل (ترجمة + تبسيط إن كان النص إنجليزي)
2. behavior_type: اسم السلوك أو المشكلة (مثال: فرط حركة، قلق، إدمان ألعاب)
3. suggested_age_group: الفئة العمرية المناسبة من {age_options}
4. suggested_severity: تقدير الشدة من {severity_options}
5. labels: وسوم مفصولة بفواصل (3-5 كلمات)

أجب بتنسيق JSON فقط:
{{
  "text_simplified": "...",
  "behavior_type": "...",
  "suggested_age_group": "...",
  "suggested_severity": "...",
  "labels": ["...", "..."]
}}"""

SYSTEM_PROMPT = "أنت خبير تربوي. ترد بصيغة JSON فقط. لا تعلق خارج JSON. جميع الحقول مطلوبة."


# ── Helpers ──────────────────────────────────────────────

def ask(prompt: str, default: str = "") -> str:
    result = input(f"{prompt} [{default}]: ").strip() if default else input(f"{prompt}: ").strip()
    return result or default


def choose(options: list[str], labels: dict | None = None, prompt: str = "اختر") -> str:
    print(f"\n{prompt}:")
    for i, opt in enumerate(options, 1):
        label = labels.get(opt, opt) if labels else opt
        print(f"  {i}. {label}")
    while True:
        try:
            c = int(input("الرقم > ").strip())
            if 1 <= c <= len(options):
                return options[c - 1]
        except ValueError:
            pass
        print(f"  ⚠️  1–{len(options)}")


def extract_pdf(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """Split by ##/-- boundaries first, then by ~500 tokens with overlap."""
    sections = re.split(r"\n(?=#{2,}|\-{3,})", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        words = section.split()
        if len(words) <= max_tokens + overlap:
            chunks.append(section)
        else:
            i = 0
            while i < len(words):
                chunk = " ".join(words[i:i + max_tokens])
                chunks.append(chunk)
                i += max_tokens - overlap
    return chunks


def call_ollama(messages: list[dict]) -> dict:
    payload = {"model": MODEL, "messages": messages, "stream": False,
               "options": {"temperature": 0.1, "num_predict": 800}}
    try:
        with httpx.Client(timeout=120) as client:
            r = client.post(OLLAMA_URL, json=payload)
            r.raise_for_status()
            content = r.json()["message"]["content"]
            # Strip markdown code fences if present
            content = re.sub(r"```(?:json)?\s*|```", "", content).strip()
            return json.loads(content)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠️  Ollama error: {e}")
        return {}


def validate_unit(unit: dict) -> bool:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    from jsonschema import Draft202012Validator, ValidationError
    try:
        Draft202012Validator(schema).validate(unit)
        return True
    except ValidationError as e:
        print(f"  ❌ Invalid: {e.message}")
        return False


# ── Main ─────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  📥  Ingest Source → Knowledge Units")
    print("=" * 60)

    # 1. Input
    path = input("مسار الملف (PDF أو TXT): ").strip()
    path = Path(path).expanduser().resolve()
    if not path.exists():
        print(f"❌ الملف غير موجود: {path}")
        sys.exit(1)

    is_pdf = path.suffix.lower() == ".pdf"
    text = extract_pdf(path) if is_pdf else extract_txt(path)
    print(f"✅ استُخرج {len(text)} حرف من {path.name}")

    domain = choose(DOMAINS, DOMAIN_LABELS, "المجال")
    ref_info = ask("المرجع (اسم المصدر، المؤلف، الصفحة...)")

    # 2. Chunk
    chunks = chunk_text(text)
    print(f"📦 {len(chunks)} chunks (max 500 tokens, overlap 50)")

    # 3. Process each chunk
    accepted = 0
    skipped = 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    user_prompt_template = EXTRACTION_PROMPT.format(
        age_options="/".join(AGE_OPTIONS),
        severity_options="/".join(SEVERITY_OPTIONS)
    )

    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'─' * 40}")
        print(f"  Chunk {i}/{len(chunks)} – {len(chunk)} chars")
        print(f"  Preview: {chunk[:120]}...")
        print()

        data = call_ollama([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt_template + "\n\nالنص:\n" + chunk}
        ])

        if not data:
            print("  ⚠️  فشل الاستخراج — تخطي")
            skipped += 1
            continue

        text_simplified = data.get("text_simplified", "")
        behavior_type = data.get("behavior_type", "عام")
        age = data.get("suggested_age_group", "10-12")
        severity = data.get("suggested_severity", "متوسط")
        labels = data.get("labels", [])

        print(f"  🏷️  السلوك: {behavior_type}")
        print(f"  📅  العمر: {age}  |  ⚡ الشدة: {severity}")
        print(f"  🏥  التبسيط: {text_simplified[:150]}...")
        print(f"  🏷️  وسوم: {', '.join(labels)}")

        choice = input("\n  (a) قبول  (s) تخطي  (e) تعديل > ").strip().lower()

        if choice == "s":
            skipped += 1
            continue

        if choice == "e":
            print("  تعديل كل حقل (Enter للإبقاء على المقترح):")
            text_simplified = input(f"  التبسيط: {text_simplified[:80]}... \n  > ") or text_simplified
            behavior_type = input(f"  السلوك [{behavior_type}]: ") or behavior_type
            age = input(f"  الفئة العمرية [{age}]: ") or age
            severity = input(f"  الشدة [{severity}]: ") or severity
            labels_raw = input(f"  وسوم [{','.join(labels)}]: ") or ",".join(labels)
            labels = [t.strip() for t in labels_raw.split(",") if t.strip()]
            if not labels:
                labels = ["عام"]

        uid = f"{domain[:3]}-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        unit = {
            "id": uid,
            "domain": domain,
            "age_group": age if age in AGE_OPTIONS else "10-12",
            "behavior_type": behavior_type,
            "intervention_type": "إرشادي",
            "severity": severity if severity in SEVERITY_OPTIONS else "متوسط",
            "reference_type": "كتاب_تربوي",
            "reference_info": ref_info,
            "text_original": chunk,
            "text_simplified": text_simplified,
            "labels": labels,
            "created_at": now,
            "updated_at": now,
            "version": "1.0.0",
            "source_meta": {
                "source_title": path.stem,
                "source_author": "",
                "source_year": None
            }
        }

        if validate_unit(unit):
            out_path = DATA_DIR / f"{uid}.json"
            out_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅  حُفظ: {out_path.name}")
            accepted += 1
        else:
            print("  ⚠️  فشل التحقق — تخطي")
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"  ✅  قُبل: {accepted}  |  ⏭️  تُخطّي: {skipped}")
    print(f"  📁  المخرجات: {DATA_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
