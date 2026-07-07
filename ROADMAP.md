# Tutor Guardian — Product Roadmap / Backlog

This file tracks known technical debt and follow-up work that is intentionally
out of scope for the current feature but must be closed before the next phase.

## Active Backlog

### Daily-routine tracker («حِساب اليوم»)

1. **PATCH does not zero optional fields**
   - Current: `PATCH /api/daily-routine/events/{event_id}` replaces all columns
     from `RoutineEventCreate`, so setting `amount_ml`/`ended_at`/`diaper_type`
     back to `null` requires sending explicit `null` values, and the router
     stores them as `None`. Confirm whether the mobile client can send explicit
     `null`s; if not, implement field-level partial update semantics so omitted
     fields preserve existing values and an explicit `null` clears them.
   - Files: `backend/app/routers/daily_routine.py`,
     `backend/app/models/daily_routine.py`,
     `mobile/lib/features/routine/`.

2. **Summary treats `amount_ml=0` as no amount**
   - Current: summary aggregation only adds `amount_ml` when it is truthy:
     `if row["amount_ml"]: feed_amount += row["amount_ml"]`. This means a
     logged feed with `amount_ml=0` is counted in `total_feed_count` but does
     not contribute to `total_feed_amount_ml`. Decide product behaviour:
     either reject `amount_ml=0` at creation, or include zeroes in the sum so
     the count/amount relationship is consistent.
   - Files: `backend/app/routers/daily_routine.py` (`get_summary`).

## Done

- `flutter test` passes with 0 failures.
- Backend `pytest` passes with 0 failures.
- Added missing backend tests for invalid datetime and non-existent child_id.
