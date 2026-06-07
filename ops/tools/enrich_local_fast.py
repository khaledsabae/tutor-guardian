import json, time, requests
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units")
backup_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units_backup_enrich")
backup_dir.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
BATCH_SIZE = 5  # small batches for speed

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
    orig = str(unit.get("text_original", ""))[:800]  # shorter prompt = faster

    prompt = f"""أنت محرر متخصص. المجال: {DOMAIN_AR.get(domain, domain)}. الموضوع: {bt}. المرجع: {ref}.

اكتب JSON فقط:
{{"text_simplified":"شرح عربي 3-4 جمل", "age_group":"اختر: 0-3,4-6,7-9,10-12,13-15,16-18,unspecified", "severity":"خفيف/متوسط/شديد/طارئ", "intervention_type":"وقائي/إرشادي/علاجي/إحالة_لطبيب", "keywords":["ك1","ك2","ك3"]}}"""

    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
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

batch = targets[:BATCH_SIZE]
print(f"Total: {len(targets)}, Processing first {len(batch)}", flush=True)

processed = 0
for f, unit in batch:
    backup_path = backup_dir / f.name
    if not backup_path.exists():
        backup_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        enriched = enrich_unit(unit)
        for key in ["text_simplified", "age_group", "severity", "intervention_type", "reference_info", "keywords"]:
            if key in enriched and enriched[key]:
                unit[key] = enriched[key]
        f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK {f.name[:8]} | age={unit.get('age_group')} | sev={unit.get('severity')}", flush=True)
        processed += 1
        time.sleep(2)
    except Exception as e:
        print(f"ERR {f.name[:8]}: {e}", flush=True)
        time.sleep(1)

print(f"Done: {processed}/{len(batch)}", flush=True)