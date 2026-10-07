# Curated social tips — 2026-10-07

`ops/tools/social_media_autoposter.py` now reads Arabic text verbatim from
`knowledge_base/curriculum/daily_tips/*.json`, ordered by each record's stable
string `id` (for example `tip_7-9_001`). Records explicitly marked
`is_published: false` are excluded; records without that optional field remain
eligible. Missing/duplicate IDs and missing text fail before posting. The old
arsenal and its generated `tip_N.png` cards remain the legacy card generator's
inputs; this change does not regenerate cards or change that tool.

## State and rollback

Keep the existing `ops/tools/autoposter_state.json` in place. No pre-run rewrite
or renumbering is needed. Its integer `last_posted_id` and every existing history
entry are retained. The first successful curated post adds
`curated_last_posted_id` and appends a history entry with the source string ID.
The two ID namespaces are distinct; a legacy number is never interpreted as an
index into the curated bank. With only legacy history, curated selection begins
at the first stable ID. If a curated cursor is absent or removed from the bank,
selection skips curated IDs already in history; if all are recorded, it stops
instead of restarting. A valid curated cursor advances to the following ID and
wraps after the last, preserving the existing deliberate repeat-cycle behavior.
Explicit `--post-id` remains an override and may deliberately select an old
curated post. It now accepts source string IDs, not legacy integers.

A corrupt/unreadable state file stops the run instead of silently resetting
history. Back up state before deployment. Reverting the code leaves the preserved
legacy cursor/history available to the previous version; its extra curated
cursor is ignored. No running service, schedule, global settings, or live state
was changed for this patch.

## Images and offline verification

Only existing generic graphics in `docs/marketing/launch_graphics/` are used:
announcement for prenatal/infant/toddler, AI feature for ages 4–9, journey feature
for ages 10–18. Never attach legacy text cards to curated text. Unknown age groups
or missing graphics omit the image URL. Telegram's existing photo-only path
skips posting without an image; Buffer receives text without an image asset.

Safe previews (no network calls or state writes):

```sh
python3 ops/tools/social_media_autoposter.py --dry-run
python3 ops/tools/social_media_autoposter.py --post-id tip_7-9_001 --dry-run
python3 -m unittest discover -s ops/tools/tests -p test_social_media_autoposter.py
python3 -m pytest backend/tests/test_tip_cards.py -k autoposter_curated
```

Local migration verification used a read-only copy of the existing state: legacy
cursor `14`, 44 entries (IDs 1–30, then 1–14). Selection and simulated successful
recording preserved the cursor and all 44 entries; only a new curated cursor and
one history entry were added in memory. No live state file was written. No posting
command, deployment, push, or merge is part of this change.
