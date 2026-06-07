#!/usr/bin/env python3
"""
Fix Arabic encoding issues by regenerating text_simplified from behavior_type + domain + reference_info
using qwen2.5:3b (local, good for Arabic). Does NOT use garbled text_original.
"""
import json
import time
import requests
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units")
backup_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units_backup_arabic_fix")
backup_dir.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

def has_bad_arabic(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (0xFB50 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF) or ch == '\uFFFD':
            return True
    return False

def regenerate_unit(unit: dict) -> dict:
    """Regenerate text_simplified from behavior_type + domain + reference_info only."""
    domain = unit.get('domain', '')
    bt = unit.get('behavior_type', '')
    ref = unit.get('reference_info', '')
    
    domain_ar = {
        'medical': 'طبي/نفسي', 'cyber': 'سيبراني/رقمي',
        'islamic_parenting': 'تربية إسلامية', 'development': 'تطور الطفل',
        'fiqh': 'شرعي', 'tarbiyah': 'تربوي', 'digital_safety': 'أمان رقمي'
    }.get(domain, domain)
    
    prompt = f"""أنت خبير تربوي تكتب محتوى مبسطاً للأهل العرب المسلمين.
المجال: {domain_ar}
الموضوع/السلوك: {bt}
المرجع: {ref if ref else 'عام'}

اكتب شرحاً عربياً واضحاً ومفيداً للأهل في 3-5 جمل، يغطي:
- ما هو هذا السلوك/المشكلة
- نصائح عملية للتعامل معه
- متى يلزم استشارة مختص

أجب بتنسيق JSON فقط:
{{
  "text_simplified": "نص عربي واضح 3-5 جمل",
  "age_group": "unspecified",
  "severity": "خفيف",
  "intervention_type": "إرشادي",
  "reference_info": "{ref}",
  "keywords": ["كلمة1", "كلمة2", "كلمة3"]
}}"""
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 600}
    }
    
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  Error: {e}")
        return {}

def main():
    print("=" * 60)
    print("  🔧 Fix Arabic Encoding - Regenerate from Metadata")
    print("=" * 60)
    
    bad_files = []
    for f in sorted(units_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if has_bad_arabic(data.get("text_simplified", "")):
            bad_files.append((f, data))
    
    print(f"Found {len(bad_files)} units with encoding issues\n")
    
    processed = 0
    errors = []
    
    for f, unit in bad_files:
        print(f"[{processed+1}/{len(bad_files)}] Fixing: {f.name[:8]} | {unit.get('domain')} | {unit.get('behavior_type')}")
        
        backup_path = backup_dir / f.name
        if not backup_path.exists():
            backup_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        
        try:
            enriched = regenerate_unit(unit)
            if not enriched:
                errors.append(f.name)
                continue
            
            for key in ["text_simplified", "age_group", "severity", "intervention_type", "reference_info", "keywords"]:
                if key in enriched:
                    unit[key] = enriched[key]
            
            f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ {unit.get('text_simplified', '')[:80]}...")
            processed += 1
            time.sleep(2)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors.append(f.name)
            time.sleep(3)
    
    print(f"\n=== Result ===")
    print(f"✅ Fixed: {processed} units")
    print(f"❌ Errors: {len(errors)}")
    if errors:
        print("Errors:", errors)

if __name__ == "__main__":
    main()