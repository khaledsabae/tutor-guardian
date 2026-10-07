# English prepared but not yet accepted — not served

The 2026-10-07 closeout ran the canonical dual-family review (deepseek-v4-pro +
glm-5.2 via Ollama Cloud, `run --rounds 1 --no-fix`, wire concurrency 1) on the
15 items that waited here. Nine passed both families and are live with their
stamp: 8 stories (hope_sprout, omar_prayer, khadija_neighbor, abdullah_bismillah,
hamza_truth — interactive fields; badr_broken_toy, tamim_anger_volcano,
noura_sharing_box — new) and `tip_prenatal-1_006`. Proof, raw responses and
reasons: `review-2026-10-07/` (`verdicts.json`, `raw-calls.json`, `run-report.json`).

Six stories are held in `stories_en.pending.json`, each with a blocking finding:

| story | blocking finding | side |
|---|---|---|
| maryam_toys | category + all three discussionQuestions do not match the Arabic (deepseek, 4× medium) | English |
| yaseen_creation | discussionQuestions[0] swaps ant/stars/trees/flowers for "sky and birds" (glm high, deepseek medium) | English |
| fatima_parents | description drops «بالمعروف»; pages[4] «جوري» rendered as a red carnation (both medium) | English |
| bilal_forgiveness | the Arabic question puts the incident at play; the story has it in art class (deepseek medium) | Arabic |
| sarah_basil_sprout | deepseek says Bukhari 2989 reads «وتميط» — probably a false positive (scripture gate matches 2989; «وتميط» is Muslim 1009); needs an adjudication Claude may not record on its own English | Arabic |
| salman_secret_trust | colloquial «أكيد» in the Arabic pages[2] (deepseek medium) | Arabic |

The four existing stories (maryam_toys, yaseen_creation, fatima_parents,
bilal_forgiveness) stay live with their earlier stamped text, without the new
interactive fields; the two new ones are not served in English. Arabic-side
findings need an Arabic correction by a human — the review never rewrites the Arabic.
Fix the English (or the Arabic), put a story in place as before, and run:

```bash
python3 ops/tools/review_en_parity.py run --only story:<id> --rounds 1 --no-fix --workers 1 --max-concurrent 1
```

Authorship: the 2 new stories carry `translator_model: claude-opus-5.5`; the 4 updated
ones carry `english_authors: [mistral-large-3:675b, claude-opus-5.5]`. Claude cannot
stamp any of them; deepseek-v4-pro + glm-5.2 can. A stamp certifies English–Arabic
parity only — scholar review stays pending.

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
