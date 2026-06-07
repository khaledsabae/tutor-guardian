import json, time, requests, re
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units")
backup_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units_backup_enrich")
backup_dir.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
BATCH_SIZE = 5
START_FROM = "/home/khalednew/projects/tutor-guardian/backend/app/services/retrieval.py"  # just a marker

AGE_GROUPS = {"0-3", "4-6", "7-9", "10-12", "13-15", "16-18", "unspecified"}
SEVERITIES = {"خفيف", "متوسط", "شديد", "طارئ"}
INTERVENTIONS = {"وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"}

def clean_value(val, allowed_set, default):
    if not val or not isinstance(val, str):
        return default
    val = val.strip().strip("،,./")
    # Handle combined values like "7-9, 10-12" or "شديد/طارئ"
    for sep in ["،", ",", "/", "و"]:
        if sep in val:
            val = val.split(sep)[0]
    val = val.strip()
    return val if val in allowed_set else default

DOMAIN_AR = {
    "medical": "طبي/نفسي", "cyber": "سيبراني/رقمي",
    "islamic_parenting": "تربية إسلامية", "development": "تطور الطفل",
    "fiqh": "شرعي", "tarbiyah": "تربوي", "digital_safety": "أمان رقمي"
}

def needs_enrichment(unit):
    ag = unit.get("age_group", "unspecified")
    return ag in ("unspecified", "all", "")

def enrich_unit(unit):
    ref = unit.get("reference_info", "")
    domain = unit.get("domain", "")
    bt = unit.get("behavior_type", "")

    prompt = f"""المجال: {DOMAIN_AR.get(domain, domain)}
الموضوع: {bt}
المرجع: {ref or 'عام'}

JSON فقط مع قيم محددة:
{{"text_simplified":"شرح عربي 3-4 جمل", "age_group":"اختر قيمة واحدة: 0-3 أو 4-6 أو 7-9 أو 10-12 أو 13-15 أو 16-18", "severity":"خفيف أو متوسط أو شديد أو طارئ", "intervention_type":"وقائي أو إرشادي أو علاجي أو إحالة_لطبيب", "keywords":["كلمة1","كلمة2","كلمة3"]}}"""

    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# Find targets
targets = []
for f in sorted(units_dir.glob("*.json")):
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if needs_enrichment(data):
        targets.append((f, data))

while targets:
    batch = targets[:BATCH_SIZE]
    targets = targets[BATCH_SIZE:]
    print(f"\n--- Batch: processing {len(batch)} ---", flush=True)
    processed = 0
    for f, unit in batch:
        backup_path = backup_dir / f.name
        if not backup_path.exists():
            backup_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            enriched = enrich_unit(unit)
            for key in ["text_simplified", "reference_info", "keywords"]:
                if key in enriched and enriched[key]:
                    unit[key] = enriched[key]
            # Clean categorical values
            unit["age_group"] = clean_value(enriched.get("age_group"), AGE_GROUPS, unit.get("age_group", "unspecified"))
            unit["severity"] = clean_value(enriched.get("severity"), SEVERITIES, unit.get("severity", "متوسط"))
            unit["intervention_type"] = clean_value(enriched.get("intervention_type"), INTERVENTIONS, unit.get("intervention_type", "إرشادي"))
            f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"OK {f.name[:8]} | age={unit['age_group']} | sev={unit['severity']}", flush=True)
            processed += 1
            time.sleep(2)
        except Exception as e:
            print(f"ERR {f.name[:8]}: {e}", flush=True)
            targets.append((f, unit))  # retry later
            time.sleep(1)
    print(f"Done: {processed}, Remaining: {len(targets)}", flush=True)