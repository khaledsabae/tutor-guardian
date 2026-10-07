# English prepared but not yet accepted — not served

The 2026-10-07 closeout ran the canonical dual-family review (deepseek-v4-pro +
glm-5.2 via Ollama Cloud, `run --rounds 1 --no-fix`, wire concurrency 1) on the
15 items that waited here. Nine passed both families and are live with their
stamp: 8 stories (hope_sprout, omar_prayer, khadija_neighbor, abdullah_bismillah,
hamza_truth — interactive fields; badr_broken_toy, tamim_anger_volcano,
noura_sharing_box — new) and `tip_prenatal-1_006`. Proof, raw responses and
reasons: `review-2026-10-07/` (`verdicts.json`, `raw-calls.json`, `run-report.json`).

Six stories were held in `stories_en.pending.json`, and `worship_06` stayed in
`ops/data/en_unpublished/`. **All seven were resolved the same evening** (fresh dual-family
review, `review-2026-10-07-held/`: 8 review calls + 2 evidence calls, all ok, no 429), and the
pending file is now empty (`[]`):

| item | resolution |
|---|---|
| maryam_toys, yaseen_creation, fatima_parents | the held candidates had been translated from the stale Arabic in `docs/stories.json`; the live English already carried the corrected fields (sharing category/questions/challenge; ant-stars-trees-flowers; «بالمعروف» as "in what is right", «جوري» as damask rose). Candidates discarded; live text re-reviewed fresh — low notes only — and re-stamped |
| bilal_forgiveness | Arabic question «أثناء اللعب» → «أثناء حصة الرسم» (the story is unchanged), English to match; stamped |
| salman_secret_trust | colloquial «وأكيد» → «ولا بدّ أن» in the Arabic; stamped and live |
| sarah_basil_sprout | the citation is right: «ويميط» is verbatim Bukhari 2989, «وتميط» is Muslim 1009. Evidence + both families' verdict on it in `sarah-evidence*.json`; **agent** adjudication (not human) in `ops/data/en_parity_adjudications.json`; stamped and live |
| lesson worship_06 | the verified unit `isl-3f0af447` (al-Bara' showing the Prophet's wudu, Alukah pp.99–102) now sits in the Arabic and English `unit_ids` alike; the withdrawn `isl-ab49af82` is gone; restored and stamped |

The Arabic of every story now lives in two identical copies, `mobile/assets/data/stories.json` (bundled) and
`docs/stories.json` (fetched first by the app). They had drifted — the served copy still carried
older text (tidiness questions for maryam_toys, «تروّخ», «يده الشمال») — and were made byte-identical here.

To hold a future story: put the candidate here, fix the English (or the Arabic, in both copies),
put it in place as before, and run:

```bash
python3 ops/tools/review_en_parity.py run --only story:<id> --rounds 1 --no-fix --workers 1 --max-concurrent 1
```

Authorship: sarah_basil_sprout and salman_secret_trust carry `translator_model: claude-opus-5.5`;
bilal_forgiveness carries `english_authors: [mistral-large-3:675b, claude-opus-5.5]`. Claude cannot
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
