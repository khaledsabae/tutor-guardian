# English prepared but not yet reviewed — not served

The Ollama Cloud **weekly** cap closed the review on 2026-10-04 before these
were judged by both models. The English gate refuses new English that has not
passed review, so they wait here, outside every loader:

- `stories_en.pending.json` — the 14 stories still unstamped: interactive
  fields (age, category, three questions, Islamic value, challenge) for 9
  existing stories, and the 5 kindergarten stories that have no English at all.
  Islamic values follow #27's Arabic: Sahihayn hadith with Abd al-Baqi numbers,
  or the ayah in Arabic with a labelled interpretation (Saheeh International).
- `daily_tips/tip_prenatal-1_006.json` — translated from the current Arabic.

To finish, when the API is available:

```bash
python3 - <<'PY'   # put the prepared stories in place (keeps the stamped five)
import json
cur = json.load(open('mobile/assets/data/stories_en.json'))
pend = {s['id']: s for s in json.load(open('ops/data/en_parity_pending/stories_en.pending.json'))}
ar = json.load(open('mobile/assets/data/stories.json'))
by = {s['id']: s for s in cur}; by.update(pend)
out = [by[s['id']] for s in ar if s['id'] in by]
blob = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
open('mobile/assets/data/stories_en.json', 'w').write(blob); open('docs/stories.en.json', 'w').write(blob)
PY
git mv ops/data/en_parity_pending/daily_tips/tip_prenatal-1_006.json knowledge_base/curriculum/i18n/en/daily_tips/
python3 ops/tools/review_en_parity.py run --all --unstamped --workers 1 --max-concurrent 2
```
