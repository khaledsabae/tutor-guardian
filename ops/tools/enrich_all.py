import requests, json, time
from pathlib import Path

units_dir = Path("knowledge_base/units/")
backup_dir = Path("knowledge_base/units_backup/")
backup_dir.mkdir(exist_ok=True)

def needs_enrichment(unit):
    return (
        unit.get("age_group", "unspecified") in ("unspecified", "all", "")
        or not unit.get("text_simplified", "").strip()
        or unit.get("text_simplified", "").startswith(("ملف إرشادي", "مرجع تربوي", "دليل أمان", "مرجع نمو"))
        or unit.get("severity") is None
        or unit.get("intervention_type") is None
    )

def enrich_unit(unit):
    prompt = f"""أنت محرر متخصص في قاعدة معرفة تربوية للأهل العرب المسلمين.

النص الأصلي:
{str(unit.get('text_original', ''))[:2000]}

المجال: {unit.get('domain', '')}
behavior_type: {unit.get('behavior_type', '')}

أعطني JSON فقط بهذه الحقول، بدون أي نص خارج الـ JSON:
{{
  "text_simplified": "شرح عربي واضح للأهل في 3-5 جمل بدون مصطلحات طبية معقدة يذكر الأعراض والتعامل العملي",
  "age_group": "اختر واحداً فقط: 0-3 أو 4-6 أو 7-9 أو 10-12 أو 13-15 أو 16-18 أو unspecified",
  "severity": "اختر واحداً: خفيف أو متوسط أو شديد أو طارئ",
  "intervention_type": "اختر واحداً: وقائي أو إرشادي أو علاجي أو إحالة_لطبيب",
  "reference_info": "اسم المصدر الرسمي والسنة إن وجدت",
  "keywords": ["كلمة1", "كلمة2", "كلمة3"]
}}"""

    models = ["kimi-k2.6:cloud", "gemma4:31b-cloud"]
    last_err = None
    for model in models:
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=240
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            last_err = e
            if model == "kimi-k2.6:cloud":
                print("  ⚠️ kimi unavailable, falling back to gemma4", flush=True)
            continue
    raise RuntimeError(f"All models failed. Last error: {last_err}")

files = sorted(units_dir.glob("*.json"))
processed = 0
skipped = 0
errors = []

for f in files:
    unit = json.loads(f.read_text(encoding="utf-8"))
    if not needs_enrichment(unit):
        skipped += 1
        print(f"  SKIP: {f.name[:8]}")
        continue

    print(f"  [{processed+1}] جاري: {f.name[:8]} | {unit.get('domain')} | {unit.get('age_group')}", flush=True)

    backup_path = backup_dir / f.name
    if not backup_path.exists():
        backup_path.write_text(f.read_text(encoding="utf-8"))

    try:
        enriched = enrich_unit(unit)
        for key in ["text_simplified", "age_group", "severity", "intervention_type", "reference_info", "keywords"]:
            if key in enriched:
                unit[key] = enriched[key]
        f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    ✅ age_group={unit['age_group']} | severity={unit['severity']} | intervention={unit['intervention_type']}", flush=True)
        processed += 1
        time.sleep(3)
    except Exception as e:
        print(f"    ❌ خطأ: {e}", flush=True)
        errors.append({"file": f.name[:8], "error": str(e)})
        time.sleep(5)

print(f"\n=== النتيجة النهائية ===")
print(f"✅ تم تحسين: {processed} وحدة")
print(f"⏭ تم تخطي: {skipped} وحدة (كاملة مسبقاً)")
print(f"❌ أخطاء: {len(errors)}")
if errors:
    for e in errors:
        print(f"  - {e['file']}: {e['error']}")
