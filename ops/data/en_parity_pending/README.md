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

## Queued for a non-Anthropic review (unstamped, live as before)

The Ollama key hit its weekly cap on 2026-10-04 and also serves a live system,
so it is not called again this week. These units carry English that Claude
wrote (fixing reviewer-located defects) or that #27 rewrote, so Claude does not
stamp them; they wait for deepseek-v4-pro + glm-5.2. Also parked above: 5 new
stories and tip_prenatal-1_006.

```bash
python3 ops/tools/review_en_parity.py run --all --unstamped --workers 1 --max-concurrent 2
```

- **adhkar** (1): `adhkar:family_adhkar`
- **daily_tips** (4): `tip_0-3_018`, `tip_13-15_020`, `tip_7-9_024`, `tip_7-9_030`
- **kb_units** (14): `0bd76d3c-548a-46ed-b17b-78874741662a__en`, `968f42b5-5184-4f4a-97d9-b854f507dbe6__en`, `cd81035d-4fdb-4274-bcf2-55074ee7a1de__en`, `isl-27372b44__en`, `isl-624104ea__en`, `isl-73905b43__en`, `isl-8bf4e7a3__en`, `isl-9933c64e__en`, `isl-b1e6de34__en`, `isl-c4b3fccc__en`, `isl-f6c0c64a__en`, `isl-fd937511__en`, `med-6de3365b__en`, `med-ccf5e011__en`
- **lessons** (14): `lesson_13-15_cyber_digital_maturity_02`, `lesson_13-15_cyber_digital_maturity_03`, `lesson_13-15_islamic_mockery_01`, `lesson_13-15_islamic_parenting_steadfast_04`, `lesson_16-18_cyber_digital_professional_02`, `lesson_4-6_aqeedah_seeds_02`, `lesson_4-6_aqeedah_seeds_03`, `lesson_4-6_development_positive_parenting_02`, `lesson_4-6_islamic_parenting_adab_02`, `lesson_7-9_aqeedah_fundamentals_01`, `lesson_7-9_aqeedah_fundamentals_04`, `lesson_prenatal-1_infant_pregnancy_03`, `lesson_prenatal-1_infant_pregnancy_04`, `lesson_prenatal-1_infant_pregnancy_05`
- **stories** (9): `story:abdullah_bismillah`, `story:bilal_forgiveness`, `story:fatima_parents`, `story:hamza_truth`, `story:hope_sprout`, `story:khadija_neighbor`, `story:maryam_toys`, `story:omar_prayer`, `story:yaseen_creation`
