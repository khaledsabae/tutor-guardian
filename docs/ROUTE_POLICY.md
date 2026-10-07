# Route policy inventory — Phase 3, item 2

The table in `backend/app/security/route_policy.py` records the effective
FastAPI registrations at main `5d566611`. It is a review/test contract;
the application and middleware do not consume it. This change adds no runtime
authentication, rate limits, feature restrictions, or production configuration.

The inventory contains **166 route objects / 170 method-and-path entries**:
157 API entries, eight framework GET/HEAD entries, and five static mounts.

| Authentication layer | Entries | Meaning |
| --- | ---: | --- |
| Public | 56 | No mandatory credential in AuthMiddleware; some have a separate capability or staged handler guard |
| Device | 91 | Parent Bearer is validated and binds device/session state |
| Child | 15 | Child-Bearer is validated and binds device/child state |
| Ops | 7 | Middleware exemption; credentials are checked in the actual handler |
| Soft | 1 | Story binds valid Bearer identity when present; `STORY_AUTH_ENFORCE` makes it mandatory |

`scope` describes public, device, session, child, or ops resource context. It
does **not** imply that every handler performs a complete ownership check.
Fourteen entries also have explicit device-proof dependencies. The table records
their callable identities and nested dependency/security-scope graphs, rather
than assuming a protected pathname is sufficient.

## Reviewed exceptions

- `POST /api/chat/sessions` is bootstrap-public, whereas `GET` on the same path
  requires device auth. The mint handler uses proof to choose identity and
  refuses a known-device bare mint only under `SESSION_MINT_ENFORCE`. New device
  IDs remain admitted. Existing sessions are not revoked by this policy table.
- `/api/program/story` has staged soft auth. Child ownership checking there is
  conditional on having device identity and a supplied child ID. Public catalog
  routes, including story themes, remain public. Tafsir and Quranic linguistics
  POST routes are also public; no blanket “all APIs require auth” claim applies.
- `POST /api/feedback/app` is public submission. Its list, digest, audio and
  admin reply routes require `FEEDBACK_ADMIN_KEY` through `X-Admin-Key` in their
  handlers. Operational metrics use `OPS_METRICS_TOKEN` / `X-Ops-Token`; manual
  push uses `TG_ADMIN_KEY` / `X-Admin-Key`. All fail closed when unconfigured.
  Telegram uses its own secret header and configured chat allowlist.
- QR claim redemption is public at the transport layer but requires a valid,
  single-use claim capability. It conditionally opens a budget session. Child
  content routes require a live session when the child-surface gate is enabled;
  `/child-web/me`, `/child-web/refresh`, and child-mode `/session-end` require
  Child-Bearer but are explicitly exempt from that live-session check.
- Registered memory/privacy dependencies require device proof. Destructive
  child dependencies are conditional on enrollment/the configured proof floor;
  irreversible actions also have cooldown rules. Handler-only checks remain
  documented: enabling memory needs proof while disabling does not, and child
  renaming conditionally checks proof.
- Session-owned assistant/chat handlers retain compatibility for legacy
  ownerless sessions. Parent-owned child handlers use their existing ownership
  checks; lesson progress retains its legacy child-ID fallback.
- **Observed ownership exception:** `POST /api/feedback` authenticates the
  device but accepts the caller's supplied `session_id` without checking its
  owner (`feedback.submit_feedback`). The table records this rather than
  describing it as session authorization. No behavior change is included.
- OpenAPI, Swagger, ReDoc and the five known static mounts are explicitly
  public. Known static mounts are optional because main registers them only
  when their directories exist. Unknown mounts, route types and schema routes
  are rejected. Framework `GET /docs` and static `MOUNT /docs` are separate
  inventory entries; their existing order/behavior is unchanged.

## What the regression gate verifies

`backend/tests/test_route_policy.py` compares the actual `app.routes` against
exact `(route kind, method, path)` entries. New routes under existing public or
protected prefixes receive no inherited classification. Missing required entries,
duplicate registrations, endpoint swaps, schema-exposure changes and changed
dependency graphs fail the gate. A mount must actually be `StaticFiles`, not an
unreviewed application hidden under an allowed prefix.

The tests exercise the real AuthMiddleware dispatch for every HTTP entry with
anonymous, parent and child credentials, including both story enforcement modes.
They check child-session exemptions with the gate enabled, execute denial through
all fourteen registered proof dependencies, and verify ops-handler denial before
database/sender effects for configured and unconfigured credentials. Bootstrap
mint and invalid QR claim behavior are also checked. These are separate from the
table-coverage test; authentication is not inferred just from route names.

TDD began with the actual route-inventory test failing because the table was
absent: unclassified live registrations included `GET /api/app-config`, exit 1.
Negative checks also demonstrate rejection of new API/schema/static routes and
removal of a registered proof dependency. Existing ownership and auth regressions
remain necessary; the table does not audit every handler body, response schema,
query/body field, service, dynamic file, or data-access path.

When adding or changing a route, review its effective middleware branch,
dependency graph and handler guards before adding an explicit table entry. Add
a denial case for a new ops handler. Do not regenerate the table automatically
inside the test, loosen a prefix, or turn an unclassified route into “public”
merely to make CI pass.

Run the gate from the repository root with the existing backend test environment:

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_route_policy.py
```

No model/server startup is needed. TestClient checks use no lifespan, synthetic
credentials and isolated test databases; private logs and JUnit counts provide
verification without exposing tokens or production settings.

Validation on this branch: **40 policy tests plus 77 existing related
regressions passed (117 total), exit 0, zero failures/errors/skips**. The related
suite covers story auth, monthly-report ownership, ops metrics, audit
regressions, child web/claims and device proof. Ruff checks/format and
`git diff --check` passed. This is a focused gate, not a full-backend-suite claim.
