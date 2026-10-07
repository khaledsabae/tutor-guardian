# Lesson 11: primary source proof and review hold

Base: `db07c35f36395ce5cee7a1344442d77c996d95bd`. This correction adds one authored reference unit, replaces both unsupported lesson anchors, and revises the Arabic and English lesson together.

## Verified primary text

- [مسلم 2713a](https://sunnah.com/muslim:2713a): local canonical number **2713**.

> اللَّهُمَّ أَنْتَ الأَوَّلُ فَلَيْسَ قَبْلَكَ شَىْءٌ

- [البخاري 3276](https://sunnah.com/bukhari:3276): local canonical number **3276**.

> يَأْتِي الشَّيْطَانُ أَحَدَكُمْ فَيَقُولُ مَنْ خَلَقَ كَذَا مَنْ خَلَقَ كَذَا حَتَّى يَقُولَ مَنْ خَلَقَ رَبَّكَ فَإِذَا بَلَغَهُ فَلْيَسْتَعِذْ بِاللَّهِ، وَلْيَنْتَهِ

Muslim 2713a is the public subentry; the local canon uses 2713. Exact Arabic excerpts were extracted from the retrieved narration pages and checked against the unchanged local canon. The JSON companion records excerpt, reader snapshot, and canon SHA-256 hashes. Wrong-number negative checks must fail. These checks establish textual evidence, not human or scholar approval.

## Claim boundaries

- Source-derived: Allah is the First, with nothing before Him (Muslim); seeking refuge and ending pursuit of the described recurring thought (Bukhari). The lesson describes these meanings without inventing quoted wording.
- Authored parenting advice: listen calmly, ask what the child means, avoid judging faith or mental state from one question, use a short explanation, return to an ordinary activity, and consult a trusted scholar when needed. These suggestions are explicitly separated from hadith-derived theology in both lesson metadata and the reference unit.
- Removed unsupported certainty: a question proves the mind is working; analogy increases confusion. No clinical or developmental assertion replaces them. No blanket creation argument or unsupported no-likeness claim is attributed to these two sources.
- The new Arabic reference unit preserves exact source excerpts in text_original. Its explanatory text is identified as authored guidance; both lesson languages point to that same unit. Existing source corpus and unrelated units remain unchanged.

## Source-fix review status at commit 8d026a14 (historical)

Arabic and English approved_by are null; needs_scholar_review remains true. Current English content is queued awaiting-review with its current pair fingerprint. Historical English approval and automated-review stamps are cleared. Historical review records are marked unaccepted for this changed lesson. Test-only fixtures preserve the prior approved pair solely to exercise approval regression tests; they do not approve current content. No models were called during that source-fix stage. Independent dual-family review was then pending; the subsequent current-hash review is recorded below. Human/scholar approval remains pending. Existing repository publication flags are not changed by this draft correction; a queue hold alone is not a deployment or runtime suppression mechanism. No content was published or deployed.

## Validation

Red baseline before the source fix: focused proof tests exited 1 (4 failures). After the fix: `test_lesson11_source_proof.py` and `test_deepen_paths.py` exited 0, **54 passed**. Exact quotes pass the local canon at 2713 and 3276; deliberately wrong number 1 is rejected. The canon hash remains unchanged.

Actual exit **0** for each: KB integrity, KB source fidelity, English parity hold, Quran citations, hadith citations, scripture coverage, Quran rendering, curriculum schema, adhkar integrity, family programs, and Ruff. `git diff --check` exited 0. The index preserves all prior rows and appends only the new unit; the English queue changes only lesson 11. No build, corpus regeneration, model review, approval stamp, or publishing action was run.

## Subsequent genuine canonical review

Both `deepseek-v4-pro` and `glm-5.2` were called with the canonical review rubric, the complete corrected AR/EN fields, and a primary-source packet containing the exact excerpts and public URLs: https://sunnah.com/muslim:2713a and https://sunnah.com/bukhari:3276. Each returned the requested lesson ID with `defects: []`; no missing verdict was treated as acceptance. Calls ran serially under the shared review lock.

Reviewed pair SHA-256: `5b8150f5b1387c8b6b8c4215b9ef09d81ed06c448ecfe2d8a0ef7cc5bb582129`. No lesson wording, anchor, or reference-unit text changed after review. The canonical tool applied its current-hash English approval from those actual cached responses and removed only lesson 11 from the parity queue. `needs_scholar_review` remains true; no human or specialist signoff is claimed. The original JSON proof's approval block records the earlier source-verification stage, not this subsequent model parity review.

The path pair is unchanged from db07c35f, has valid existing approval and no deterministic defects; its pair SHA-256 is `6394507cc6f7fce2a27a95470ca5d1ef005269736653c61e431e0f4dea5ec3f9`. No path rereview or rewrite was needed.

[Current review evidence and future specialist packet](lesson11.canonical-review.json) records exact reviewed fields, raw model verdicts, request and response-artifact hashes, model response IDs, usage, and the primary-source URLs/excerpts. This evidence certifies actual model parity review, not scholar approval or a new verification of the public sources by a model.

After canonical acceptance: the focused source-proof and db07 approval-contract suites exited 0 (**54 passed**); all 11 deterministic guards exited 0 again. The lesson wording and anchors remain byte-equivalent by JSON fields to source-fix 8d; only review metadata changed. The queue diff removes only lesson 11. No build or push was run.
