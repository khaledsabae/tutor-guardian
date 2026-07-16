# Tutor Guardian — Product Roadmap / Backlog

This file tracks known technical debt and follow-up work that is intentionally
out of scope for the current feature but must be closed before the next phase.

## Active Backlog

(empty — the two daily-routine items closed 2026-07-16, see Done)

## Done

- **PATCH partial-update semantics** («حِساب اليوم»): the router now builds the
  UPDATE from `RoutineEventUpdate` with `exclude_unset=True` — omitted fields
  preserve existing values, explicit `null` clears them. Covered by
  `backend/tests/test_daily_routine.py` (preserve-on-omit asserted).
- **`amount_ml=0` behaviour resolved**: product decision = reject at creation
  (`amount_ml: ge=1` in both Create and Update models) and the summary
  aggregation uses `is not None`, keeping count/amount consistent. Covered by
  `backend/tests/test_daily_routine.py` (422 on zero, summary sum asserted).
  Verified 2026-07-16: 13/13 tests pass inside the production container.

- `flutter test` passes with 0 failures.
- Backend `pytest` passes with 0 failures.
- Added missing backend tests for invalid datetime and non-existent child_id.
