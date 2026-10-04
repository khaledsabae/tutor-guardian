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

Commit only what `run` stamped. New English cannot be queued, and English cannot be
added to a unit that is not stamped, so any story or tip left unresolved goes back
into this folder until it passes.

Authorship is recorded so the family rule holds after they move: the 5 new stories and
the tip carry `translator_model: claude-opus-5.5`; the 9 updated stories carry
`english_authors: [mistral-large-3:675b, claude-opus-5.5]` (mistral's text, Claude's new
fields). Claude cannot stamp any of them; deepseek-v4-pro + glm-5.2 can.

## Queued live English — `ops/data/en_parity_queue.json`

The authoritative list is the queue file, not this README. It names every published
English unit that is live without a stamp, bound to the sha of its current text, with
a reason and a category (`check` — and CI — fail on anything unstamped that is not
there, or that changed after it was queued):

- `awaiting-review` (46): English Claude wrote or rewrote (fixing reviewer-located
  defects, or with PR #27's Arabic), the 9 stories waiting on the fields above, and
  `lesson_7-9_islamic_parenting_worship_01` (owned by #31). `run` stamps them and
  removes their entries.
- `source-unverified` (130): Alukah units whose Arabic summary was never shown to
  match its reversed-PDF source. `run`, `stamp-reviewed` and `sign` refuse them until
  the hold is released (`unqueue`) after re-extraction.

```bash
python3 ops/tools/review_en_parity.py inventory     # queued / src-hold columns
python3 ops/tools/review_en_parity.py run --all --unstamped --workers 1 --max-concurrent 2
```
