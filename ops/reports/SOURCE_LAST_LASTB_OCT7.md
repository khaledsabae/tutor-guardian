# Native last-three source recovery — 2026-10-07

Branch: `codex/source-last-lastb`. Base: `6016bb4c796dc4b7a12835092c6f998bd3619c62`, preserving the previously accepted three English parity reviews and all earlier commits. Only `isl-f782f2ed`, `isl-fb04bcd3`, `isl-fe2f3c39` and their English drafts are recovered. No inference model was called.

The actual Book17337 primary PDF was downloaded directly from https://www.alukah.net/Books/Files/Book_17337/BookFile/brotherandboys.pdf. SHA-256: `7fa6f88fbf1ba714947983c11cde1e8c67b576374ae06c08a081444743d1272c`, matching the prior committed source proof. Agent Reach's Jina Reader route was used for the catalogue URL; it returned a generic home page, which was not treated as source evidence. Source decisions rely on the actual PDF checksum and native visual reading of the relevant pages with system Poppler. No whole-book thematic exploration, smart-PDF/model route, copied PDF/page artifact or new modern prose quotation was used.

Before changing titles or summaries, the original OCR passages were hashed, their actual historical/Quran/glyph anchors identified, and candidate/adjacent pages read. Each committed proof in `ops/data/kb_fidelity/source_recovery/` records the exact original Git blob/field, raw OCR hash and anchor, selected page, ancient excerpt checksum and scope. The old OCR remains recoverable verbatim from the base commit. Old model verdicts are preserved verbatim in each proof under `previous_translation_review`, explicitly attached to the old hash; the recovered drafts have not received a new model verdict.

| Unit | Selected PDF / printed page | Current AR/EN canonical hash |
|---|---|---|
| isl-f782f2ed | 7 / 6 | `ec09dce7df2ac9836b4da4c7fd9263859e93123608732c9aac82244c2260440d` |
| isl-fb04bcd3 | 30 / 29 | `6216c131a2fbb88f319be3576cc4115d53659a5fe61c1a53298d71c1b2638a93` |
| isl-fe2f3c39 | 121 / 120 | `4b51131897ff1a51358ca8edfdccd3d971183458c7ae8fd3e00fc30ee1b0101d` |

## Actual passages and limits

`isl-f782f2ed`: raw OCR matches PDF7/printed6. This is substantive discussion of children's religious education in the author's introduction, not an author-method statement or contents listing. The author presents teaching Quran, Sunnah and creed, conduct and avoiding prohibited acts as parental responsibilities. The app's summary attributes this account to the author rather than issuing a new mandatory practice or a new ruling. The original field selects the actual ancient Quran quotation, al-Tahrim 66:6, verified against the local mushaf by the canonical consonantal normalizer. Modern surrounding commentary is our own paraphrase. English is a summary of that discussion, not English passed off as Quran.

`isl-fb04bcd3`: raw OCR spans PDF30–31/printed29–30, including Aisha's response to a newborn and a separate naming section. The recovery narrows to the actual Aisha report on PDF30: she asks about the newborn's condition rather than its sex and praises Allah when told the baby was soundly formed. This is Aisha's historical report (athar), not the Prophet's speech. The page visibly cites al-Adab al-Mufrad 1256; no Sahihayn corpus match or independent isnad grade is claimed. No diagnosis, preference for a sex, medical outcome, aqiqah requirement or current mandatory practice is inferred.

`isl-fe2f3c39`: raw OCR spans PDF120–121/printed119–120. PDF120 has historical racing reports; PDF121 has al-A'mash's report from Abd al-Rahman about his father inviting him to race and winning, followed by modern commentary on play. The recovered title and summary reflect this father-son account, rather than broad claims about good character, the Sunnah, intelligence or modern electronic games. The source page's first footnote visibly cites Ibn Abi Shaybah 12/509. It is an ancient athar, not a prophetic hadith; the footnote's authenticity statement is not adopted as an independent grading. The son's age is unspecified. No benefits, harmful-game diagnosis, modern gender prescription or parental mandate is added.

All three selected passages supply substantive source content. There are **zero new TOC/catalogue/author-method quarantine candidates** among these three. No occurrence of these IDs was found in curriculum, NotebookLM path-source files, mobile, backend or docs references before adding this report. Carver's separate auditing/quarantine work, existing TOC draft `isl-7349e59c`, prior source proofs and all other queue/ledger/index entries are preserved. No branch used by Carver was changed.

## Draft and quotation state

Six AR/EN files retain `approved_by: null`, `needs_scholar_review: true`, `review_verdict: pending`, and explicit draft status. Native English authorship is recorded with `openai:codex`, preserving the original Mistral translator identity. Historical review timestamps/defects describing the old text are retained in the source proofs; they are not claimed as a fresh review of these drafts. The former religious-title omission on `isl-f782f2ed` is corrected in the native draft but remains pending independent review.

Exactly three `source-unverified` queue entries change to `awaiting-review` at the current hashes after source recovery. The queue retains **42 entries: 32 awaiting review and 10 source-unverified**; no entry is removed. Source verification is not parity approval or scholar approval. Fresh canonical DeepSeek + GLM review awaits the parent's explicit grant, with one request per family and two overall concurrent requests. No cache/adjudication state was altered.

Modern-book quotation accounting remains **89/90 words**: zero new copied modern-author words in this batch. The identified Quran and ancient historical reports are public-domain quotations, separately identified in each proof; modern commentary is paraphrased. No long modern text or page copy is committed.

## Actual validation

`SOURCE_LAST_LASTB_VALIDATION_OCT7.json` preserves each executed guard's real output, elapsed time and exit code. Six schema validations, three original-OCR and ancient-excerpt hash checks, three current-hash queue checks, one exact Quran match, and zero deterministic parity defects passed. No hadith corpus match is claimed for the two athars.

All seven executed guards returned **exit 0**:

- KB integrity: 1,388 units; 223 existing optional-metadata warnings.
- Source fidelity: 716 served base units; detector flags 246 to 243 after the three genuine OCR recoveries; 281 ledger records, 205 quarantined, 231 withdrawn sources held.
- Hadith citations: 349 translated units, 100 program cards, 15 app hadiths; zero attribution/citation violations.
- Scripture coverage: 31 surfaces, 35,102 texts, 130 cards, 6,426 translation pairs.
- Quran citations: 142/142 existing citations matched; selected source verse additionally verified independently.
- Quran rendering: 808 English files checked.
- Canonical parity check: 814 items; drafts accounted for by the unchanged-total queue and fresh fingerprints.

Scope checks compared every unrelated queue, index and ledger entry with the base. Index totals/domain counts are unchanged; only six target index title/size/age fields change. All six ages are unspecified, avoiding an unsupported specific age inference. Deterministic validations ran in a bounded child process with captured logs; only native source reading and translation were used. Normal Git hooks are required for the commit. No paid API, purchase, push, build, emulator or production change.
