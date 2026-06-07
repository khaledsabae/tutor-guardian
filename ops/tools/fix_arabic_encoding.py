#!/usr/bin/env python3
"""
Fix Arabic encoding issues in knowledge units by regenerating text_simplified
using a local LLM (qwen2.5:3b) that handles Arabic well.
"""
import json
import time
import requests
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units")
backup_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units_backup_arabic_fix")
backup_dir.mkdir(exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"  # Local model, good for Arabic

def has_bad_arabic(text: str) -> bool:
    """Check if text contains Arabic presentation forms (ligatures)."""
    for ch in text:
        cp = ord(ch)
        if (0xFB50 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF) or ch == '\uFFFD':
            return True
    return False

def enrich_unit(unit: dict) -> dict:
    """Regenerate text_simplified and metadata using LLM."""
    prompt = f"""أنت محرر متخصص في قاعدة معرفة تربوية للأهل العرب المسلمين.

النص الأصلي (قد يحتوي على مشاكل ترميز):
{str(unit.get('text_original', ''))[:2000]}

المجال: {unit.get('domain', '')}
behavior_type: {unit.get('behavior_type', '')}

أعطني JSON فقط بهذه الحقول، بدون أي نص خارج الـ JSON:
{{
  "text_simplified": "شرح عربي واضح للأهل في 3-5 جمل بدون مصطلحات طبية معقدة، يذكر الأعراض والتعامل العملي",
  "age_group": "اختر واحداً فقط: 0-3 أو 4-6 أو 7-9 أو 10-12 أو 13-15 أو 16-18 أو unspecified",
  "severity": "اختر واحداً: خفيف أو متوسط أو شديد أو طارئ",
  "intervention_type": "اختر واحداً: وقائي أو إرشادي أو علاجي أو إحالة_لطبيب",
  "reference_info": "اسم المصدر الرسمي والسنة إن وجدت",
  "keywords": ["كلمة1", "كلمة2", "كلمة3"]
}}"""
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 800}
    }
    
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        
        # Strip markdown code fences
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
    print("  🔧 Fix Arabic Encoding Issues in Knowledge Units")
    print("=" * 60)
    
    # Find units with bad text_simplified
    bad_files = []
    for f in sorted(units_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if has_bad_arabic(data.get("text_simplified", "")):
            bad_files.append((f, data))
    
    print(f"Found {len(bad_files)} units with encoding issues")
    print()
    
    processed = 0
    errors = []
    
    for f, unit in bad_files:
        print(f"[{processed+1}/{len(bad_files)}] Fixing: {f.name[:8]} | {unit.get('domain')} | {unit.get('behavior_type')}")
        
        # Backup
        backup_path = backup_dir / f.name
        if not backup_path.exists():
            backup_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
        
        try:
            enriched = enrich_unit(unit)
            if not enriched:
                errors.append(f.name)
                continue
                
            # Update fields
            for key in ["text_simplified", "age_group", "severity", "intervention_type", "reference_info", "keywords"]:
                if key in enriched:
                    unit[key] = enriched[key]
            
            # Write back
            f.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ age_group={unit.get('age_group')} | severity={unit.get('severity')}")
            processed += 1
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors.append(f.name)
            time.sleep(2)
    
    print(f"\n=== Result ===")
    print(f"✅ Fixed: {processed} units")
    print(f"❌ Errors: {len(errors)}")
    if errors:
        print("Errors:", errors)

if __name__ == "__main__":
    main()