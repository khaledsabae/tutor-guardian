# Plan closeout — 7 October 2026

This checklist records observed state, not a claim that the annual growth plan is complete.

## Verified delivery

- `origin/main` at start: `da731bdc`; its latest Deploy and Backend tests runs succeeded.
- Published Android release recorded in the previous release handoff: `1.0.68+113`, built from `efaa740f48389636ea4bf06b6a71bbe3f324e8bc`.
- GitHub variable `E2E_BASELINE_REF` was set to that released commit and read back through the GitHub API on 7 October. Upgrade journeys now start from the released code instead of the default `1.0.66+111`.
- Local emulator and local APK/AAB builds remain prohibited until Khaled authorizes their use again.
- PR #58 merged as `3d40ae7b` and deployed successfully on 7 October at 08:15 UTC (run `37590344627`). Checkout and image labels matched that commit; the public health snapshot reported SQLite, ChromaDB and reranker healthy. Earlier reranker degradation and SSH timeouts remain unexplained; this snapshot does not establish a latency root-cause fix.

## Content remaining

- English queue on `da731bdc`: 55 `awaiting-review`, 23 `source-unverified` (78 total). Source-unverified content requires source verification before any approval stamp.
- Prepared English outside loaders: 14 stories and one prenatal tip; these overlap with parts of the live queue and are not an additive count.
- Persistent lesson backup: `/home/khalednew/.local/share/tg-deepen-paths`; 114 drafts across three topics, of which five are recorded as published, leaving 109. Historical review files are not approval of changed text.
- PR #58 integrates the four medical units with source corrections after twenty cited pages were fetched. Their four English twins subsequently passed independent DeepSeek and GLM review. These are model-reviewed translations, not clinician sign-off.
- Never describe software or model review as human medical or scholarly approval.

## Delivery checks still open

- PR #58 passed 2,887 backend tests (3 skipped), candidate smoke, both hosted APK builds, and all 13 fresh/upgrade emulator journeys (0 skipped, 0 failed). Main now requires the stable Mobile delivery gate, bound to GitHub Actions. Those journeys exercised code version 113; they do not validate release 114.
- Post-113 mobile fixes have been identified. Metadata and bilingual notes for 1.0.69+114 are included in this batch; this does not mean the signed release has been built or published.
- The curated poster was activated in the existing local PCC checkout by syncing only its script and 72 changed Arabic tips after merge, with private backups and state/user-file hash preservation. A network-blocked loader check found 220 tips. No posting job was invoked.
- Both Play Console deletion URLs were corrected to `/delete-account`, validated, saved and submitted. Khaled published the metadata; the Console then showed publication on 7 October and no pending changes. This is separate from publishing mobile release 114.
- Donations remain off until the merchant profile, products, and restricted verification credentials are ready. No payments setup or subscription purchase is implied by this checklist.

The canonical task state for this run is the claude-mem work-state list `plan-completion-oct7`.

## Additional reviewed content

- The first new aqeedah lesson initially passed translation review, but a subsequent source audit found unsupported anchors. The Arabic and English are now grounded in Muslim 2713a and Bukhari 3276; old approval was cleared and fresh DeepSeek/GLM review of the exact changed pair is clean (`5b8150f5…`). Scholar review remains pending; no human approval is claimed. The second lesson is now grounded in exact guarded-corpus quotations Q7:157 and Q16:43; its corrected pair passed fresh DeepSeek/GLM parity review (`c35b590e…`). Both prefix lessons retain scholar-review requirements. Historical review records alone are not publishable evidence.
- PR #60 consolidates 54 approved items from the original 55 awaiting English items (including four medical twins), plus three recovered source-held parenting units. The five corrected screen items were re-reviewed on their current text; only their two formerly pending paths add original-queue approvals. Independent evidence checks passed for those 21 items (42 current cache records) and the three added Abdullah/Omar/Fatima stories (six current cache records); final delivery checks remain required before merge. The original 23 source holds are now 20 after three source recoveries. Only family adhkar remains awaiting review, bound to its current hash. Maryam was accepted in the editorial story batch; Yaseen subsequently passed fresh Google/GLM review on pair `66bcd1f7…` with no adjudications. The Google request used `gemini-3.1-pro-low`; its actual serving model was unreported and is not claimed as verified. These are model translation reviews, not human expert approval.
- Future hosted E2E builds now include a reviewed CI-only Firebase Analytics deactivation step for both head and old-baseline APKs. Production collection settings are unchanged. Historical GA4 aggregates may contain test traffic and have not been adjusted by assumption.
- The five-item screen correction now includes the prenatal lesson and removes its blanket all-organisations/prevention claim. Current AAP 2026 guidance and distinct WHO 2019 age-specific sedentary guidance are separated. Two GLM future-date objections were resolved by explicit current-hash adjudications; the other recorded low observations remain. Independent verification confirmed the WHO primary PDF and the AAP publication date through Crossref; the AAP full article/PDF reread was blocked by 403 verification in this reviewer session, so its complete context was not independently reopened. The WHO excerpt was subsequently shortened to 77 words using only its existing verbatim sentences; Arabic paraphrase, source locators and all five current pair hashes were unchanged. Translation review remains separate from clinician endorsement.
- Three specialist packets are being prepared with exact text, source links, content hashes and editable decisions. Human review proceeds alongside implementation; it is not a global development gate.

## Operational metrics authentication

- M15 is complete in this batch: `/api/stats/ops-llm` requires a nonblank configured token in every environment and rejects missing, incorrect or non-ASCII mismatched headers with 403 before metrics access. Exact token comparison uses constant-time UTF-8 bytes. All 15 route tests passed; this records tested code, not production token configuration or deployment.
