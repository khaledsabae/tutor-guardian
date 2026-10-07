# Screen guidance source correction — 2026-10-07

Base: `codex/reviewed-content-oct7` at `95d208ba`. Work branch:
`codex/screen-guidance-source`. No model review, mobile build, index service rebuild,
publication or changes to other lessons.

## Source verification

- **AAP Council on Communications and Media, Media and Young Minds (2016),
  Pediatrics 138(5):e20162591, doi:10.1542/peds.2016-2591.**
  [Official full article](https://publications.aap.org/pediatrics/article/138/5/e20162591/60503/Media-and-Young-Minds),
  sections **Recommendations → Pediatricians / Families** and **Infants and Toddlers**.
  Read the actual full text in Chrome after the HTTP reader returned a verification
  page. Under 18 months: discourage screen media other than video chatting.
  At 18–24 months, parents choosing to introduce media should choose high-quality
  content, use it with their child, and avoid solo use. Ages 2–5: one hour daily of
  high-quality content with co-viewing. The article visibly marks this statement
  **revised**, linking doi:10.1542/peds.2025-075320. This correction identifies the
  requested **2016** statement; it does not call it AAP's latest guidance.
- **WHO, Guidelines on physical activity, sedentary behaviour and sleep for
  children under 5 years of age (2019), ISBN 9789241550536.**
  [Official publication page](https://www.who.int/publications/i/item/9789241550536)
  and its [official full PDF](https://iris.who.int/server/api/core/bitstreams/60a1cbaa-2bef-4251-9557-e52ce22112b3/content).
  Read and extracted **printed p. 8 / PDF p. 20**, Recommendations → Sedentary
  behaviour: no screen time recommended for infants, no sedentary screen time
  recommended for one-year-olds; at age two no more than one hour, less is better.
  No AAP video-chat exception is attributed to WHO.

Both new KB units retain short primary-source excerpts, exact document locations,
URLs, publication years and extraction notes. Arabic paraphrases are written for
this app, not official agency translations or endorsements. Replaced anchors were
Common Sense screen-use census, cyberbullying advice and a school-age gaming study,
which did not support the age-specific AAP/WHO recommendations.

## Scope and review state

- Development path title now says birth to age three. Its linked lesson `_03`
  explicitly addresses age two and uses CDC two-year checklist unit
  `2b2d1fdd-1a30-40f3-aa2b-0dbadea2ce2c`; it is not a first-year-only path.
- Screen path description distinguishes the two guidelines and covers the 0–3 band.
- Screen lesson `_01` identifies each guideline's age limits and links both new units.
- Screen lesson `_b04` scopes the video-call exception before 18 months and links
  the actual AAP unit. Its activity and reflections are unchanged.
- All four matching English files are drafts awaiting actual independent review.
  Both approval fields are null, previous approval stamps removed, verdict pending,
  and queue entries bind their current Arabic/English hashes. Existing English
  authors remain recorded, with Codex added. No review or sign command was run.
- Existing lesson order, durations, other lesson files and prior KB index entries
  remain unchanged. Only the two new entries and derived count/size metadata were added.

## Validation

All commands below completed with exit **0** (long output kept outside the checkout):

- `python3 ops/tools/check_curriculum_schema.py`
- `python3 ops/tools/check_kb_integrity.py` — 1,390 units; schema matches taxonomy.
- `python3 ops/tools/check_quran_citations.py` — 142/142 matching citations.
- `python3 ops/tools/check_hadith_citations.py` — 15/15 app hadith matching;
  349 translated units checked, no invented attribution.
- `python3 ops/tools/check_scripture_coverage.py`
- `python3 ops/tools/review_en_parity.py check` — four changed files pass via
  current awaiting-review queue entries; this is not an approval or model review.
- `python3 ops/tools/check_kb_fidelity.py check` — no new exemption or verdict added.
- Scoped deterministic verification of all four current queue hashes, null approvals,
  removed stamps, preserved activities/reflections/order/durations, unchanged old
  index entries, and WHO quotation text against the downloaded official PDF.
- `git diff --check`
