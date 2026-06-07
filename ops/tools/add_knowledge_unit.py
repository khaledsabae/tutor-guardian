#!/usr/bin/env python3
"""
Add a new knowledge unit interactively.
Prompts the user for all required fields, validates against the schema,
and saves to knowledge_base/data/.
"""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "knowledge_base" / "schema" / "knowledge_unit.schema.json"
DATA_DIR = PROJECT_ROOT / "knowledge_base" / "data"

# ── Enums ───────────────────────────────────────────────
DOMAINS = ["medical", "tarbiyah", "fiqh", "cyber"]
DOMAIN_LABELS = {
    "medical": "طبي / سلوكي",
    "tarbiyah": "تربوي",
    "fiqh": "شرعي",
    "cyber": "سيبراني",
}
AGE_GROUPS = ["0-3", "4-6", "7-9", "10-12", "13-15", "16-18"]
INTERVENTION_TYPES = ["وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"]
SEVERITIES = ["خفيف", "متوسط", "شديد", "طارئ"]
REFERENCE_TYPES = [
    "DSM-5", "كتاب_فقهي", "حديث", "كتاب_تربوي", "تقرير_سيبراني", "إرشاد_مهني",
]


def ask(prompt: str, default: str = "") -> str:
    """Ask for input with optional default."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result or default
    while True:
        result = input(f"{prompt}: ").strip()
        if result:
            return result
        print("  ⚠️  هذا الحقل مطلوب.")


def choose(options: list[str], labels: dict[str, str] | None = None, prompt: str = "اختر") -> str:
    """Present numbered options and return the chosen value."""
    print(f"\n{prompt}:")
    for i, opt in enumerate(options, 1):
        label = labels.get(opt, opt) if labels else opt
        print(f"  {i}. {label}")
    while True:
        try:
            choice = int(input("الرقم > ").strip())
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print(f"  ⚠️  اختر رقمًا من 1 إلى {len(options)}.")


def confirm(prompt: str) -> bool:
    result = input(f"{prompt} (نعم/لا) [نعم]: ").strip()
    return result.lower() in ("", "y", "yes", "نعم", "n", "naam")


def main():
    print("=" * 50)
    print("  ✍️  إضافة وحدة معرفة جديدة")
    print("=" * 50)

    # 1. Domain
    domain = choose(DOMAINS, DOMAIN_LABELS, "المجال")

    # 2. Age group
    age_group = choose(AGE_GROUPS, prompt="الفئة العمرية")

    # 3. Behavior type
    behavior_type = ask("نوع السلوك (مثال: فرط حركة، قلق، إدمان ألعاب)")

    # 4. Intervention type
    intervention_type = choose(INTERVENTION_TYPES, prompt="نوع التدخل")

    # 5. Severity
    severity = choose(SEVERITIES, prompt="شدة الحالة")

    # 6. Reference type
    ref_type = choose(REFERENCE_TYPES, prompt="نوع المرجع")

    # 7. Reference info
    ref_info = ask("تفاصيل المرجع (اسم الكتاب، الصفحة، المؤلف...)")

    # 8. Original text
    print("\n📝 النص الأصلي (اقتباس من المرجع):")
    print("  اكتب النص ثم اضغط Enter مرتين للإنهاء.")
    lines = []
    empty_count = 0
    while empty_count < 2:
        line = input()
        if line.strip():
            lines.append(line)
            empty_count = 0
        else:
            empty_count += 1
    text_original = "\n".join(lines).strip()
    if not text_original:
        print("  ⚠️  النص الأصلي مطلوب. إلغاء.")
        sys.exit(1)

    # 9. Simplified text
    print("\n📝 النص المبسط (موجه للأهل):")
    print("  اكتب النص ثم اضغط Enter مرتين للإنهاء.")
    lines = []
    empty_count = 0
    while empty_count < 2:
        line = input()
        if line.strip():
            lines.append(line)
            empty_count = 0
        else:
            empty_count += 1
    text_simplified = "\n".join(lines).strip()
    if not text_simplified:
        print("  ⚠️  النص المبسط مطلوب. إلغاء.")
        sys.exit(1)

    # 10. Labels (optional)
    labels_raw = ask("وسوم (مفصولة بفواصل، اختياري)", "")
    labels = [t.strip() for t in labels_raw.split(",") if t.strip()] if labels_raw else []

    # 11. Source meta (optional)
    add_source = confirm("هل تريد إضافة بيانات المصدر؟")
    source_meta = None
    if add_source:
        st = ask("عنوان المصدر", "")
        sa = ask("المؤلف أو الجهة", "")
        sy_raw = ask("سنة النشر (رقم)", "")
        su = ask("رابط المصدر (اختياري)", "")
        source_meta = {
            "source_title": st or None,
            "source_author": sa or None,
            "source_year": int(sy_raw) if sy_raw.isdigit() else None,
            "source_url": su or None,
        }
        source_meta = {k: v for k, v in source_meta.items() if v is not None}
        if not source_meta:
            source_meta = None

    # ── Build the unit ────────────────────────────────────
    uid = f"{domain[:3]}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    unit = {
        "id": uid,
        "domain": domain,
        "age_group": age_group,
        "behavior_type": behavior_type,
        "intervention_type": intervention_type,
        "severity": severity,
        "reference_type": ref_type,
        "reference_info": ref_info,
        "text_original": text_original,
        "text_simplified": text_simplified,
        "labels": labels,
        "created_at": now,
        "updated_at": now,
        "version": "1.0.0",
    }
    if source_meta:
        unit["source_meta"] = source_meta

    # ── Validate against schema ───────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{uid}.json"

    # Quick inline validation
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    from jsonschema import Draft202012Validator, ValidationError
    validator = Draft202012Validator(schema)
    try:
        validator.validate(unit)
    except ValidationError as e:
        print(f"\n❌ فشل التحقق: {e.message}")
        sys.exit(1)

    # ── Save ──────────────────────────────────────────────
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(unit, f, ensure_ascii=False, indent=2)

    print(f"\n✅ تم الحفظ: {out_path}")
    print(f"   ID: {uid}")
    print(f"   المجال: {DOMAIN_LABELS.get(domain, domain)}")
    print(f"   السلوك: {behavior_type}")
    print(f"   الفئة: {age_group} | الشدة: {severity}")
    print(f"   صالح وفقًا للمخطط ✓")


if __name__ == "__main__":
    main()
