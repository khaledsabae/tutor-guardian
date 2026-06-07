import json, requests
from pathlib import Path

f = Path('/home/khalednew/projects/tutor-guardian/knowledge_base/units/6ce0dab4-4a0f-459c-9190-b6d3dfa8cee7.json')
with open(f, 'r', encoding='utf-8') as fp:
    data = json.load(fp)

domain = data.get('domain', '')
bt = data.get('behavior_type', '')
ref = data.get('reference_info', '')

domain_ar = {'islamic_parenting': 'تربية إسلامية'}.get(domain, domain)

prompt = f'''أنت خبير تربوي تكتب محتوى مبسطاً للأهل العرب المسلمين.
المجال: {domain_ar}
الموضوع/السلوك: {bt}
المرجع: {ref if ref else 'عام'}

اكتب شرحاً عربياً واضحاً ومفيداً للأهل في 3-5 جمل، عربي فقط.
أجب بتنسيق JSON فقط:
{"{"}
  "text_simplified": "نص عربي واضح 3-5 جمل، عربي فقط",
  "age_group": "unspecified",
  "severity": "خفيف",
  "intervention_type": "إرشادي",
  "reference_info": "{ref}",
  "keywords": ["كلمة1", "كلمة2", "كلمة3"]
{"}"}'''

payload = {'model': 'qwen2.5:3b', 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.2, 'num_predict': 600}}
resp = requests.post('http://localhost:11434/api/generate', json=payload, timeout=120)
raw = resp.json().get('response', '')
print('Response:', raw)

if '```' in raw:
    raw = raw.split('```')[1]
    if raw.startswith('json'):
        raw = raw[4:]
enriched = json.loads(raw.strip())
data['text_simplified'] = enriched.get('text_simplified', data['text_simplified'])
data['age_group'] = enriched.get('age_group', data['age_group'])
data['severity'] = enriched.get('severity', data['severity'])
data['intervention_type'] = enriched.get('intervention_type', data['intervention_type'])
data['reference_info'] = enriched.get('reference_info', data['reference_info'])
data['keywords'] = enriched.get('keywords', data['keywords'])

with open(f, 'w', encoding='utf-8') as fp:
    json.dump(data, fp, ensure_ascii=False, indent=2)
print('Fixed!')