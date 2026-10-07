# Revised AAP screen guidance — source correction, 2026-10-07

This follows `cd7c434f` on `codex/screen-guidance-source`. The first correction
accurately identified AAP 2016 as historical, but the lesson drafts now need the
replacement policy's actual recommendations. The development path's corrected
0–3 scope is unchanged. Specialist review packets do not block this source work.

## Verified primary source and publication date

[Digital Ecosystems, Children, and Adolescents: Policy Statement](https://publications.aap.org/pediatrics/article/157/2/e2025075320/206129/Digital-Ecosystems-Children-and-Adolescents-Policy),
AAP Council on Communications and Media, **published 20 January 2026**;
*Pediatrics* **157(2), February 2026**, e2025075320,
[doi:10.1542/peds.2025-075320](https://doi.org/10.1542/peds.2025-075320).
The DOI's `2025` component is not the publication year.

The actual official full article was read in the in-app browser after the HTTP
reader returned a verification page. This is the document linked by the revision
notice on the official AAP 2016 article; no search snippet was used as evidence.

Exact support in **Recommendations for Children, Teens, and Families**:

- **Set time boundaries**: infant media is not presented as a learning tool;
  the text says occasional brief, high-quality infant viewing is not detrimental.
  It permits clinicians to discuss limits fitting a family's routine, gives
  possible limits of **less than one hour/day for toddlers and preschoolers**, and
  prioritizes high-quality content, sleep, play, physical activity and reading.
  These are context-sensitive recommendations, not a guaranteed safe allowance,
  a prescription for routine infant viewing, or a universal daily quota.
- **Relationship-building**: joint media engagement may support relationships
  and learning.
- The family recommendations do **not** restate the old policy's age-specific
  18/24-month restriction or video-chat-only exception. The updated lesson does
  not present those older rules as current AAP advice.

The new unit `cyb-aap-digital-ecosystems-2026` retains short verbatim excerpts
from those two named sections, with publication metadata, URL, and extraction
notes. Non-breaking spaces are normalized; the Arabic paraphrase is this app's
wording, not an official AAP translation.

## WHO remains distinct; historical provenance preserved

[WHO 2019 publication](https://www.who.int/publications/i/item/9789241550536),
ISBN 9789241550536, [official full PDF](https://iris.who.int/server/api/core/bitstreams/60a1cbaa-2bef-4251-9557-e52ce22112b3/content),
**printed p. 8 / PDF p. 20, Sedentary behaviour**:
no screen time recommended for infants; no sedentary screen time recommended
for one-year-olds; at age two no more than one hour, less is better.
No AAP video-chat exception is attributed to WHO.

Both `cyb-who-screen-under5-2019` and `cyb-aap-media-young-minds-2016` are
unchanged from `cd7c434f`. The old AAP unit is preserved as historical provenance,
not relabelled as a 2026 source. Video-call lesson `_b04` cites it only for the
older article's description of video chatting with relatives as social interaction;
it cites the new unit for current joint-engagement guidance. Its existing practical
activity and reflections remain unchanged.

## Changed content and approval state

Only the screen path and screen lessons `_01` / `_b04`, in Arabic and English,
are updated in this follow-up. Their order, timing, activities and reflections
remain unchanged. One new KB unit and its derived index entry are added. No
unrelated lessons, WHO unit, historical AAP unit or development path are edited.

All **four** English items from the original correction, including the unchanged
 development path, remain unapproved: top-level and translation `approved_by` are
null, review verdict pending, and each awaiting-review entry matches its current
Arabic/English hash. No new model calls or stamps were made. Ampere and Hilbert
were reported to be using both shared slots; the instruction to wait for a confirmed
free slot is preserved. Genuine dual-family review is still a separate pending step.

## Validation

Exit **0** on the revised content:

- `python3 ops/tools/check_curriculum_schema.py`
- `python3 ops/tools/check_kb_integrity.py` — 1,391 units, schema matches taxonomy.
- `python3 ops/tools/review_en_parity.py check` — current hashes accepted as queued,
  not as approved; this command makes no model calls.
- `python3 ops/tools/check_kb_fidelity.py check` — no new exemption/verdict added.
- Scoped checks: four null approvals/current queue hashes; unchanged WHO and AAP
  2016 source files and development pair; unchanged activities, reflections, lesson
  order and timing; every pre-existing index entry unchanged; new index size exact.
- `git diff --check`.

Normal pre-commit runs the repository's citation, rendering, scripture coverage,
adhkar, curriculum, programs, fidelity, English queue and Ruff guards. Long logs
remain private outside the checkout. No local mobile build, emulator, service
mutation or push is performed. The medical specialist snapshot can be refreshed
from this corrected text while honestly retaining its pending review status.
