# Three real-source English parity reviews — 2026-10-07

Base: `d0806de9cbd2a6c5a767dba125a64bdcdd4a23eb` in the persistent source-four-b-resume checkout.

Accepted **3/3** for English/Arabic parity only. Both actual canonical reviewers returned an empty defects list for each exact current hash. No translation edit, medium/high defect, adjudication, cache read/write, or invented clean verdict was involved. Review stamps were written through the existing canonical `build_record` and `write_stamp` functions. The independent source and scholar approval remains null on each Arabic unit; all six units retain draft status and need scholar review. The English `approved_by` fields now record the real automated parity review, which is not source or scholar approval.

| English unit | Canonical AR/EN content SHA-256 | PDF / printed page |
|---|---|---|
| isl-2fee1086__en | 5bf1065f6281df926fe785a8b477fd34a23b72f01f22a935c644546c1bab4f62 | 134 / 133 |
| isl-552b4f5a__en | 09672e0ea924d75a0a991ac0ebd2115fe48b9117ca2d128cfd28a5c570ee971f | 79 / 78 |
| isl-8f8f836b__en | dd3b28ba61d065108a8096a10d9d74939f1e0114a2bf3c39f75d7ffd2111d963 | 173 / 172 |

The existing committed proof files under `ops/data/kb_fidelity/source_recovery/` retain the raw OCR anchors, original OCR/PDF checksums, exact page locators and excerpt hashes. Their three excerpt hashes and equality to both unit copies were checked again; proofs and Arabic units are byte-for-byte unchanged from the base commit. This run did not independently re-download the PDF.

Source scope: Aisha's healing supplication remains a historical prayer without a medical-treatment claim. Uthman's Quran-learning/teaching hadith retains directly verified Bukhari 5027; raw OCR 5427 remains documented as an OCR error. Mu'tamir's Ramadan report remains an athar, not prophetic hadith, with no new child-waking instruction or authenticity grading.

`isl-7349e59c` is excluded: contents catalogue only, not substantive knowledge. Both language files, its queue entry and its proof remain unchanged. Carver auditing and every other quarantine/draft record are untouched. The semantic queue changed from **45 to 42** entries; only the three accepted English IDs were removed, with every remaining entry compared for exact semantic equality.

## Actual reviewer evidence

[SOURCE_FOUR_B_EN_REVIEW_OCT7.json](SOURCE_FOUR_B_EN_REVIEW_OCT7.json) contains the unaltered response text from both reviewers, parsed verdicts, all three hashes, canonical request text and prompt/tool hashes, HTTP statuses, measured elapsed times, actual returned token usage and acceptance checks. No credentials, account identifiers or purchased-credit route are recorded.

One child worker sent one three-item batch per family concurrently, using the current `review_en_parity.py` canonical system, request builder and parser. The transport wrapper enforced the user's stricter policy instead of the canonical transport's eight retries: max two concurrent requests, one bounded retry only for transport failure, immediate hold on 429/auth/quota, no missing-response resubmission. Both calls succeeded at HTTP 200 on attempt 1: DeepSeek `deepseek-v4-pro` **13.91 s**, GLM `glm-5.2` **5.46 s**. Existing Ollama authentication only; no fallback, paid API, purchase, or extra provider call.

## Validation

[SOURCE_FOUR_B_EN_VALIDATION_OCT7.json](SOURCE_FOUR_B_EN_VALIDATION_OCT7.json) preserves actual guard output and exit codes. Six target AR/EN schema validations, zero errors, exit 0; three committed source proofs checked, exit 0. All five executed guards returned exit 0:

- KB integrity: 1,388 units; 223 existing optional-metadata warnings.
- KB source fidelity: 716 served base units; 246 detector flags, 281 judged faithful, 205 quarantined and 231 withdrawn sources held.
- Hadith citations: 349 translated units, 100 program cards and 15 app hadiths; zero invented attributions or citation violations.
- Scripture coverage: 31 surfaces, 35,102 texts, 130 cards and 6,426 translation pairs.
- Full canonical English parity gate: 814 items; remaining queue 29 awaiting review and 13 source-unverified.

Codex acceptance: the real dual-family results and deterministic checks justify only the three parity stamps. No scholar approval or new publication decision is claimed. The normal Git pre-commit hooks must pass before the commit is accepted; no bypass, push, build or emulator is authorized for this run.
