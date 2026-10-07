# Final six primary-source recoveries and canonical parity

Source scope only, on `codex/source-recovery-final`, from `5f1951ea`.
Draft commits `72c9e921` and `77cb1938` were integrated as `526ed1a0` and
`c61d0df0`. The one queue conflict was merged by entry, preserving both batches
and the unrelated adhkar entry. Primary dirty main was untouched.

The final six pairs are `isl-c0936200`, `isl-d6faddeb`, `isl-f6bbab53`,
`isl-f782f2ed`, `isl-fb04bcd3`, and `isl-fe2f3c39`. The actual publisher PDF was
freshly fetched using the agent-reach Jina route and directly from Alukah.
Its 189 pages and SHA256
`7fa6f88fbf1ba714947983c11cde1e8c67b576374ae06c08a081444743d1272c` match the
committed proofs. Native Poppler renders of PDF pages 181, 176, 128, 7, 30,
and 121 were visually read. All six immutable Git OCR hashes and all six
excerpt hashes were checked; both languages preserve the identical excerpt.
The quotation of Quran 66:6 also matches the local mushaf normalizer.
Historical athar locators do not claim independent authenticity grading.

Fresh canonical reviews used the existing `ops/tools/review_en_parity.py`,
unchanged, and prompt version `dfa8a5f39718`, with one provider call at a time
and a 1200-second outer deadline. Requested and provider-reported identities
both matched `deepseek-v4-pro` and `glm-5.2`. These two actual calls took
64.058 and 32.3 seconds. All six pairs were accepted in one round: zero
medium/high defects, eight low notes retained, no fixer or adjudication.
Raw verdicts, response hashes, request hashes, actual usage, normalized
verdicts and twelve canonical cache records are committed in
`ops/data/kb_fidelity/source_recovery/last-six-canonical-review-2026-10-07.json`.
Cache records were checked against the raw verdicts; no verdict was invented.

Metadata describing these drafts as awaiting model review was clarified
without changing any reviewed content hash. Draft status and
`needs_scholar_review: true` remain. Arabic approval is null; English approval
certifies parity only. No human or Sharia approval is claimed.

The current count is **21 accepted of the original 23 sources**: three
baseline accepted pairs plus eighteen recovered source holds. The other two
are recoverably quarantined nonknowledge pairs `isl-23c2dd25` and
`isl-7349e59c`. They remain outside live units and index rows. **Zero source
holds and zero source awaiting-review entries remain.** The sole queue entry
is unchanged `adhkar:family_adhkar`. All **347 translated KB units** have
current valid stamps. Authored JSON files and unique index rows remain
**1389**. All 1377 index rows outside this phase's twelve unit files, the
previous twelve accepted pairs, and the three baseline accepted English
files are unchanged. Exact IDs, hashes and preservation assertions are in
`ops/data/kb_fidelity/source_recovery/last-six-final-audit-2026-10-07.json`.

The bounded additional Z.AI source audit timed out at 240 seconds, actual
exit 143, with no completed verdict; it is not counted as approval. An
initial delegated gate runner failed with exit 1 because its private log
directory was outside the child sandbox's writable scope. Logs were moved
to a private ignored worktree directory, and the delegated run then executed
all **11/11 content guards successfully**, each actual exit 0. Detailed
counts and exits are committed in
`ops/data/kb_fidelity/source_recovery/last-six-content-gates-2026-10-07.json`:
1389 KB files, 142/142 quoted notification verses, 15/15 notification hadiths,
807 English files for Quran rendering, 281 unique adhkar, 31 scripture
surfaces, three bilingual programs, current-hash parity and source fidelity.
These are content guards, not a backend/cache test suite.

**Push and source PR are held by the user's latest instruction.** The parent
reported two P1 cache races (eight passing and six failing independent
probes): delayed old answers can acquire a current revision at store, and a
revision can change between lookup validation and stale-hit return. Jason
owns cache/caller fixes in this same worktree. This content phase neither
edits nor stages those files and makes no cache-safety claim. The earlier
cache closeout is superseded by that independent review. No backend/mobile
tests, emulator, APK/AAB build, deploy, key upload, paid purchase or external
message was performed. Source publication awaits the separate cache fixes
and their review.
