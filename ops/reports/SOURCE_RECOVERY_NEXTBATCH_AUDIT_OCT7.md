# Six-pair source recovery and nonknowledge impact audit

Base: `e20fe437`; branch: `codex/source-recovery-final`. Source-only integration;
no models, build, emulator, push or deployment. The primary checkout was read
only. Four chronological cherries: `5324b177 → 049902d5`,
`8493250b → ccb4c458`, `42a67c4a → 792a849b`, `fdb2fc23 → a68bc515`.
The last queue conflict was resolved semantically: remove only the six accepted
keys, preserving every other base entry and the queue documentation.

## Evidence and acceptance

Freshly hashed surviving primary cache:
`knowledge_base/raw_sources/islamic_parenting/Alukah_Rights_of_Children.pdf`
in the primary checkout. SHA256:
`7fa6f88fbf1ba714947983c11cde1e8c67b576374ae06c08a081444743d1272c`.
Native targeted PDF rendering and visual re-reading confirmed these passages:

| Pair | PDF / printed pages | Scope |
| --- | --- | --- |
| `isl-09afb431` | 105 / 104 | Father's request to arrive early for Jumu'ah |
| `isl-14009a8e` | 90–91 / 89–90 | Abu Qirsafa calling Iyad; no inferred childhood age |
| `isl-3d476538` | 92–93 / 91–92 | Al-Rubayyi's historical Ashura account |
| `isl-10541fe2` | 69 / 68 | Al-Munawi's commentary on fairness in gifts |
| `isl-8aa15666` | 116 / 115 | Abu Umayr narration and attributed Ibn Hajar commentary |
| `isl-be38b357` | 113 / 112 | Aisha's Eid narration; original broader OCR spans 113–114 |

All six primary excerpt hashes, AR/EN original excerpts and current canonical
title/summary hashes match their committed proofs. DeepSeek and GLM are two
different families, both independent of recorded Mistral/OpenAI authors.
Existing stamps were cherry-picked, never regenerated. Five selected hadith
fragments freshly matched the local canonical corpus, including Bukhari 1960,
Bukhari 6129, Bukhari 952 and Muslim 892. No medium/high residuals or
adjudications were introduced; Group B retains its two recorded low notes.

Ashura is an attributed historical report, not a present child-fasting mandate,
food-withholding instruction, age/health quota or developmental claim. Aisha's
Eid account is not blanket permission for all games. Scholar/source-content
and human approval remain pending; draft status stays draft. Stale Group A
unit metadata saying no model review was corrected without changing reviewed
fields or primary proof files.

Proof limit after environment reset: Group A's committed provider response
content in `three-units-parity-2026-10-07.json` was parsed and compared with
both reviewers' parsed verdicts. Group B's committed canonical `auto_review`
and source `translation_review` records plus its actual-call closeout survive;
its private provider raw responses do not appear in the preserved commit tree.
Group B acceptance relies on those authoritative actual commits and documented
prior actual-call audits. This audit does not claim fresh inspection of lost
raw transport files or reconstruct/fabricate responses. No old handle was
treated as a running worker.

## Two nonknowledge sources: exact graph and held action

Recursive value/key inspection of 934 JSON documents in
`knowledge_base/curriculum/`, `docs/lesson_index.json`,
`docs/source_inventory.json`, `source_to_lesson.json` and
`remaining_lessons_queue.json` found **zero references** to either source ID
or its English twin. There are no curriculum claims to replace with another
anchor. The exact result and original draft proofs are retained in
`ops/data/kb_fidelity/source_recovery/nextbatch-audit-2026-10-07.json`.

| Source | Actual evidence | Appropriate held action |
| --- | --- | --- |
| `isl-23c2dd25` / `isl-23c2dd25__en` | `78895565`, PDF9 / printed8: modern author's collection, assessment and organization method | Quarantine as bibliographic methodology; not parenting evidence |
| `isl-7349e59c` / `isl-7349e59c__en` | `d0806de9`, PDF184–185 / printed183–184: table of contents | Quarantine as catalogue metadata; chapter headings are not substantive evidence |

Proposal only, not implemented in this integration: move both AR/EN pairs
outside `knowledge_base/units` and all retrieval/serving loaders, remove their
four `units_index.json` rows and two queue entries, preserve proofs outside
loaders, and retire their stale `judged_faithful.json` entries. That later
quarantine would change 1393 to 1389 authored files/index entries; keep the
count unchanged here. No broad replacement or invented chapter anchor.

Current baseline still serves these AR units: `knowledge_loader.py` excludes
three whole policy source files, not these IDs; a `source-unverified` parity
queue entry blocks stamping but does not exclude retrieval. The older
`judged_faithful.json` records accept an overview about parental values/duties
for `23c2dd25` and an overview of religious duties for `7349e59c`. Neither
turns collection methodology or a contents list into parenting evidence.
This audit therefore does not certify them safe to serve.

## Preservation and meaningful gates

The eight draft IDs in `78895565` and `d0806de9` remain unintegrated and
unapproved. Their persistent managed worktrees are `source-four-a-resume`
and `source-four-b-resume`; no changes made there. Fourteen source holds
remain: those eight plus `isl-c0936200`, `isl-d6faddeb`, `isl-f6bbab53`,
`isl-f782f2ed`, `isl-fb04bcd3`, `isl-fe2f3c39` (queue keys use `__en`).
The two nonknowledge items remain among the fourteen pending quarantine.

Verified invariants: 1393 unique index entries; twelve affected sizes equal
the current original-excerpt lengths; all 1381 other index rows unchanged;
only the twelve approved-pair unit files differ from the base. All unrelated
base approvals and the unrelated awaiting-review queue entry are preserved.
Measured global translated KB count is 349: 329 valid + 20 held at base,
335 valid + 14 held after integration. The requested 54-accepted baseline
subset was not supplied as an ID list; no unrelated approval was changed.

Approval cherry's normal pre-commit exit: **0**. Integrity checked 1393 units;
Qur'an checked 142/142 citations; rendering checked 809 English files;
hadith checked 15 numbered matches and 349 translated units; curriculum
schema checked 920 files; programs checked three bilingual programs; scripture
coverage, fidelity and ruff passed. Canonical parity check examined 349 KB
translations, exit **0**, retaining fourteen source holds. Assertions checked
six canonical hashes, six source hashes and six reviewer-family separations;
fresh local hadith fragment check: **5/5, exit 0**. No success was inferred
from empty filtered output. Final audit commit uses the normal hooks too.
