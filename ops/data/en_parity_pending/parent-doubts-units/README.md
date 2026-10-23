# English twins of the parent-doubts units: prepared, not served

These seven files are the English twins of the seven Arabic units added on branch
`content/parent-doubts-units` (see `docs/content_reviews/parent-doubts-units_REVIEW.md`).
They are held here and not in `knowledge_base/units/` because the English gate
(`ops/tools/review_en_parity.py check --staged`, run by `.githooks/pre-commit` and CI)
refuses any new `<id>__en.json` without a dual-family review stamp, and the stamp needs
`OLLAMA_API_KEY` (deepseek-v4-pro + glm-5.2), which was not available when these were written.
The queue cannot hold new English ("the queue holds live text only"), so the files wait here.

Translator: claude-sonnet-5-5 (Anthropic family). `approved_by` is null on all of them.

To promote, after the Arabic units pass scholar review and are final:

```bash
# 1. move each file next to its Arabic unit
git mv ops/data/en_parity_pending/parent-doubts-units/<id>__en.json knowledge_base/units/<id>__en.json
# 2. review and stamp (needs OLLAMA_API_KEY; do it on tg-home)
python3 ops/tools/review_en_parity.py run --only <id>__en --rounds 1 --no-fix --workers 1 --max-concurrent 1
# 3. refresh the index, then check
python3 ops/tools/build_vector_db.py   # or only rebuild_units_index() when Chroma is not needed
python3 ops/tools/review_en_parity.py check
```

Any edit to the Arabic text after the stamp invalidates it, so promote only after the
scholar's edits to the Arabic have landed.
