import json, os
from pathlib import Path

units_dir = Path("/home/khalednew/projects/tutor-guardian/knowledge_base/units/")
results = []

for f in sorted(units_dir.glob("*.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        results.append({
            "file": f.name,
            "id": data.get("id", "N/A")[:8],
            "domain": data.get("domain", "N/A"),
            "age_group": data.get("age_group", "MISSING"),
            "behavior_type": data.get("behavior_type", "")[:50],
            "text_preview": data.get("text_simplified", data.get("text_original", ""))[:80]
        })
    except Exception as e:
        results.append({"file": f.name, "error": str(e)})

unspecified = [r for r in results if r.get("age_group") == "unspecified"]
specified = [r for r in results if r.get("age_group") not in ("unspecified", "MISSING")]

print(f"=== إجمالي الوحدات: {len(results)} ===")
print(f"unspecified: {len(unspecified)}")
print(f"محددة: {len(specified)}")
print("\n=== الوحدات ذات age_group محدد ===")
for r in specified:
    print(f"  [{r['age_group']}] {r['domain']} | {r['file']} | {r['behavior_type']}")

print("\n=== أول 10 وحدات unspecified ===")
for r in unspecified[:10]:
    print(f"  {r['file']} | {r['domain']} | {r['behavior_type']}")
    print(f"    نص: {r['text_preview']}")
