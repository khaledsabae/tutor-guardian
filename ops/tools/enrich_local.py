import json, time, requests
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units")
backup_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units_backup_enrich")
backup_dir.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

DOMAIN_AR = {
    "medical": "طبي/نفسي", "cyber": "سيبراني/رقمي",
    "islamic_parenting": "تربية إسلامية", "development": "تطور الطفل",
    "fiqh": "شرعي", "tarbiyah": "تربوي", "digital_safety": "أمان رقمي"
}

def needs_enrichment(unit):
    ag = unit.get("age_group", "unspecified")
    sev = unit.get("severity")
    intv = unit.get("intervention_type")
    ts = unit.get("text_simplified", "")
    return (
        ag in ("unspecified", "all", "")
        or sev is None or intv is None
    )

def enrich_unit(unit):
    ref = unit.get("reference_info", "")
    domain = unit.get("domain", "")
    bt = unit.get("behavior_type", "")
    orig = str(unit.get("text_original", ""))[:1000]

    prompt = f"""أنت محرر متخصص في قاعدة معرفة تربوية للأهل العرب المسلمين.
المجال: {DOMAIN_AR.get(domain, domain)}
الموضوع/السلوك: {bt}
المرجع: {ref if ref else 'عام'}

النص الأصلي:
{orig}

أعطني JSON فقط بهذه الحقول، بدون أي نص خارج الـ JSON:
{{"text_simplified": "شرح عربي واضح للأهل في 3-5 جمل، يذكر الأعراض والتعامل العملي", "age_group": "اختر واحداً فقط: 0-3 أو 4-6 أو 7-9 أو 10-12 أو 13-15 أو 16-18 أو unspecified", "severity": "اختر واحداً: خفيف أو متوسط أو شديد أو طارئ", "intervention_type": "اختر واحداً: وقائي أو إرشادي أو علاجي أو إحالة_لطبيب", "reference_info": "اسم المصدر الرسمي والسنة إن وجدت", "keywords": ["كلمة1", "كلمة2", "كلمة3"]}}"""

    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    raw = resp.json().get("response", "")

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

targets = []
for f in sorted(units_dir.glob("*.json")):
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if needs_enrichment(data):
        targets.append((f, data))

print(f"Total needing enrichment: {len(targets)}")

processed = 0
errors = []
for f, unit in targets:
    if processed >= 15:
        break  # batch of 15 to avoid timeout
    print(f"[{processed+1}/{len(targets)}] {f.name[:8]} | {unit.get('domain')} | {unit.get('behavior_type')} | age={unit.get('age_group')}")

    backup_path = backup_dir / f.name
    if not backup_path.exists():
        backup_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        enriched = enrich_unit(unit)
        for key in ["text_simplified", "age_group", "severity", "intervention_type", "reference_info", "keywords"]:
            if key in enriched and enriched[key]:
                unit[key] = enriched[key]
        f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ age={unit.get('age_group')} | severity={unit.get('severity')} | intervention={unit.get('intervention_type')}")
        processed += 1
        time.sleep(3)
    except Exception as e:
        print(f"  ❌ {e}")
        errors.append(f.name)
        time.sleep(2)

print(f"\n=== Batch Result ===")
print(f"✅ Enriched: {processed}")
print(f"❌ Errors: {len(errors)}")
print(f"📊 Remaining: {len(targets) - processed}")