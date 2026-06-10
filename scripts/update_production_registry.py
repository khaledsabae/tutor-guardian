#!/usr/bin/env python3
"""
Update production_registry.md - robust table parsing
"""
import re

REGISTRY_FILE = "/home/khalednew/projects/tutor-guardian/docs/production_registry.md"

COMPLETED_SOURCE_IDS = {
    "5fb6588e-d31a-4cca-8e0c-052b364a72ac",
    "440183bc-479c-49c1-bb07-fe35fa62295f",
    "55fb8fb3-2eed-4eb2-9940-0a1e07d3e951",
    "bc41f39f-97ae-4af2-80dd-b070907a80e4",
    "dab0fff1-8180-4a3f-99ae-6791b243d690",
    "42bc52b6-7d36-486f-aa79-e98ea5dcb4c9",
    "20e00eef-fa60-4165-9364-ef869223c0f6",
    "f7e6f02d-39fb-4888-ae4a-9e0644e75f5e",
    "4086896f-0dd6-4a28-bade-c8032b18e9d1",
}

with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

table_header = "| اسم الدرس | `معرف المصدر (Source ID)` | حالة التوليد النصي | حالة البودكاست | حالة التحليل إلى JSON | ملاحظات |"
idx = content.find(table_header)
if idx == -1:
    print("ERROR: Table header not found")
    exit(1)

# Find table end (next blank line after data rows)
table_body = content[idx:]
# Split by lines
lines = table_body.split('\n')

# Find header line index (0)
# Line 1 is empty or separator
# Line 2+ are data rows starting with |

data_rows = []
for i, line in enumerate(lines):
    if line.startswith('|') and 'age_' in line:
        parts = line.split('|')
        if len(parts) >= 7:
            lesson = parts[1].strip()
            source_id = parts[2].strip().replace('`', '')
            text_status = parts[3].strip()
            podcast_status = parts[4].strip()
            json_status = parts[5].strip()
            notes = parts[6].strip()
            data_rows.append({
                'lesson': lesson,
                'source_id': source_id,
                'text': text_status,
                'podcast': podcast_status,
                'json': json_status,
                'notes': notes,
                'original_line': line
            })

print("Found " + str(len(data_rows)) + " data rows")

# Deduplicate
seen = set()
unique_rows = []
for r in data_rows:
    key = r['lesson'] + "|" + r['source_id']
    if key in seen:
        print("Duplicate: " + r['lesson'])
        continue
    seen.add(key)
    unique_rows.append(r)

print("Unique rows: " + str(len(unique_rows)))

# Update status
for r in unique_rows:
    if r['source_id'] in COMPLETED_SOURCE_IDS:
        if '⏳' in r['text'] or 'لم يبدأ' in r['text']:
            r['text'] = '✅ ناجح'
        if '⏳' in r['json'] or 'لم يبدأ' in r['json']:
            r['json'] = '✅ ناجح'
        if not r['notes'] or r['notes'] == '':
            r['notes'] = 'الأصول النصية والـ JSON جاهزة، البودكاست قيد الانتظار (Rate Limit)'

# Rebuild: replace each original line with updated version
new_content = content
for r in unique_rows:
    old_line = r['original_line']
    new_line = "| " + r['lesson'] + " | `" + r['source_id'] + "` | " + r['text'] + " | " + r['podcast'] + " | " + r['json'] + " | " + r['notes'] + " |"
    new_content = new_content.replace(old_line, new_line, 1)

with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done! Updated " + str(len(unique_rows)) + " rows")