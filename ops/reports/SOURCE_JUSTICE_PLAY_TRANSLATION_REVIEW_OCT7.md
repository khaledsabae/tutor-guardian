# Justice and play: actual translation-review closeout

Source-recovery commit: 8493250b on codex/source-justice-play. Actual canonical reviewer families: DeepSeek (deepseek-v4-pro) and Zhipu (glm-5.2). English author histories retain Mistral and native openai:codex. Max concurrency 1; workers 1; no fixer model used.

Initial three-pair review: 54 seconds, both families returned their batches. Justice and play passed. Both independently flagged the Eid wording: first-person “our festival” had become third-person “theirs”. Native Codex corrected only this English phrase, then both families genuinely reviewed its new hash in 20 seconds and passed it. No adjudications, manual stamps, fabricated verdicts, or source-content endorsements.

All three approvals were written by ops/tools/review_en_parity.py after actual provider responses. Scholar review remains required and draft_status remains draft. Two low notes are preserved in canonical records: “other” before donations, and passive phrasing of parental permission. The corrected Eid pair has its actual residual notes recorded below.

| Pair | Accepted current AR/EN hash | Low notes |
|---|---|---:|
| isl-10541fe2__en | `9fc119c817af991c576d2914dd1b657224a6db466ce527d533383a76c764d5c3` | 1 |
| isl-8aa15666__en | `90365a62e08fdb8f04b728e2d320d0f30537176958885150cee0c6269f3b8209` | 1 |
| isl-be38b357__en | `8a78b2b6961b339b33ed7a35dda7f394fc8c8a976f972ec28c2f93de1525fb6c` | 0 |

Primary proof is unchanged: PDF checksum 7fa6f88fbf1ba714947983c11cde1e8c67b576374ae06c08a081444743d1272c; justice PDF69/printed68; Abu Umayr PDF116/printed115; Aisha’s Eid PDF113/printed112. Modern-book recovery quotation budget remains 83/90 words with ancient hadith/commentary explicitly excluded. Aisha’s narration describes Eid; it is not a blanket permission for all games. No developmental-benefit claims added.

Historical draft-validation snapshots are retained as draft_validation in each source evidence file; translation_review records the actual current approvals. Stale no-model-review-yet source notes were corrected without altering source excerpts, Arabic summaries, scholar-review requirements or canonical content hashes.

Verification: 3/3 valid current hashes, distinct reviewer families, zero unresolved blockers/adjudications, and all three removed from pending queue. Final canonical parity and normal commit guards are required. No push, mobile build, emulator, or provider setting change. This is next-batch material; current PR60 batch is separate.
