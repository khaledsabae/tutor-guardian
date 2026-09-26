#!/usr/bin/env bash
# Force-update floor (MINIMUM_BUILD_NUMBER) — decide on evidence, apply, verify.
#
# Every install below the floor gets ForceUpdateScreen and nothing else until
# it updates from Play. That makes two mistakes expensive:
#   * a floor above what Play actually serves locks people out with nothing to
#     update to (a release still in review, a staged rollout);
#   * a floor chosen without knowing who is below it (docs/OPS_RUNBOOK.md §10.1).
# The census in push_tokens (schema v25: app_version / build_number, rewritten
# on every launch) answers the second; this script refuses the first by
# requiring that recently active devices already run a build at or above the
# floor — proof that build is really downloadable.
#
# Usage (on the VPS, from /root/tutor-guardian):
#   ops/scripts/min_build.sh current            # floor in .env and as served
#   ops/scripts/min_build.sh census [DAYS]      # active devices per build (default 30 days)
#   ops/scripts/min_build.sh plan FLOOR [DAYS]  # who a floor would force, and the safety check
#   ops/scripts/min_build.sh apply FLOOR        # plan check → .env backup → set → recreate → verify
#
# Rollback = `apply` with the previous value (printed by `apply`), or restore
# the .env backup it writes and recreate the backend.
#
# FORCE=1 skips the "someone already runs it" check (e.g. a brand-new build
# confirmed live in Play Console). LOCAL=1 runs the census Python against
# DB_PATH on this machine instead of inside the container (tests, copies).
set -euo pipefail

CONTAINER="${CONTAINER:-tg_backend}"
DB_PATH="${DB_PATH:-/app/ops/conversations.db}"
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE=(docker compose -f docker-compose.production.yml)
# Devices active this recently must already run >= FLOOR for `plan` to pass.
PROOF_DAYS="${PROOF_DAYS:-7}"

run_py() {  # run a Python snippet against the DB (in-container unless LOCAL=1)
  if [[ "${LOCAL:-0}" == "1" ]]; then
    DB_PATH="$DB_PATH" python3 - "$@"
  else
    docker exec -i -e DB_PATH="$DB_PATH" "$CONTAINER" python - "$@"
  fi
}

served_floor() {
  docker exec "$CONTAINER" curl -fsS http://localhost:8000/api/app-config \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["minimum_build_number"])'
}

env_floor() {
  grep -E '^MINIMUM_BUILD_NUMBER=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true
}

census() {
  run_py "${1:-30}" <<'PY'
import os, sqlite3, sys
days = int(sys.argv[1])
c = sqlite3.connect(f"file:{os.environ['DB_PATH']}?mode=ro", uri=True)
rows = c.execute(
    "SELECT build_number, COUNT(*), MAX(updated_at) FROM push_tokens "
    "WHERE updated_at >= datetime('now', ?) GROUP BY build_number "
    "ORDER BY build_number IS NULL, build_number DESC",
    (f"-{days} days",),
).fetchall()
total = sum(n for _, n, _ in rows)
print(f"active devices, last {days} days: {total}")
print(f"{'build':>7} {'devices':>8} {'share':>7}  last seen")
for build, n, last in rows:
    label = "unknown" if build is None else str(build)
    print(f"{label:>7} {n:>8} {n / total:>7.1%}  {last}")
if any(b is None for b, _, _ in rows):
    print("(unknown: a build from before the census, ~1.0.56, that has not "
          "updated since; it is below any floor)")
print("Devices that never registered for push are not counted.")
PY
}

plan() {
  local floor="${1:?FLOOR required}" days="${2:-30}"
  run_py "$floor" "$days" "$PROOF_DAYS" "${FORCE:-0}" <<'PY'
import os, sqlite3, sys
floor, days, proof_days, force = map(int, sys.argv[1:5])
c = sqlite3.connect(f"file:{os.environ['DB_PATH']}?mode=ro", uri=True)
def count(where, window):
    return c.execute(
        f"SELECT COUNT(*) FROM push_tokens WHERE updated_at >= datetime('now', ?) AND {where}",
        (f"-{window} days", floor) if "?" in where else (f"-{window} days",),
    ).fetchone()[0]
total = count("1", days)
below = count("build_number < ?", days)
unknown = count("build_number IS NULL", days)
at_or_above = count("build_number >= ?", days)
recent_on_floor = count("build_number >= ?", proof_days)
share = (lambda n: f"{n / total:.1%}" if total else "-")
print(f"floor {floor}, devices active in the last {days} days: {total}")
print(f"  forced to update: {below + unknown} ({share(below + unknown)})"
      f"  = {below} on a known older build + {unknown} unknown")
print(f"  unaffected:       {at_or_above} ({share(at_or_above)})")
print(f"  proof: {recent_on_floor} device(s) active in the last {proof_days} days run >= {floor}")
if recent_on_floor == 0 and not force:
    raise SystemExit(
        f"REFUSED: no recently active device runs build {floor} or later, so there is "
        "no evidence Play serves it yet. Everyone below would be locked out with "
        "nothing to update to. Check Play Console; FORCE=1 overrides.")
print("OK")
PY
}

apply() {
  local floor="${1:?FLOOR required}"
  [[ "$floor" =~ ^[0-9]+$ ]] || { echo "FLOOR must be a number" >&2; exit 2; }
  [[ -f "$ENV_FILE" ]] || { echo "no $ENV_FILE here — run from /root/tutor-guardian" >&2; exit 2; }
  plan "$floor"

  local previous backup
  previous="$(env_floor)"
  backup="$ENV_FILE.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "$ENV_FILE" "$backup"
  if grep -qE '^MINIMUM_BUILD_NUMBER=' "$ENV_FILE"; then
    sed -i -E "s/^MINIMUM_BUILD_NUMBER=.*/MINIMUM_BUILD_NUMBER=$floor/" "$ENV_FILE"
  else
    printf '\nMINIMUM_BUILD_NUMBER=%s\n' "$floor" >> "$ENV_FILE"
  fi
  echo "→ .env: MINIMUM_BUILD_NUMBER ${previous:-<unset>} → $floor (backup: $backup)"

  # env_file is read at container creation, so a restart is not enough.
  "${COMPOSE[@]}" up -d --no-build --force-recreate backend
  echo "→ waiting for the backend to answer"
  local served=""
  for _ in $(seq 1 60); do
    served="$(served_floor 2>/dev/null || true)"
    [[ -n "$served" ]] && break
    sleep 5
  done
  if [[ "$served" != "$floor" ]]; then
    echo "VERIFY FAILED: /api/app-config serves '${served:-nothing}', expected $floor" >&2
    echo "Rollback: cp -p $backup $ENV_FILE && ${COMPOSE[*]} up -d --no-build --force-recreate backend" >&2
    exit 1
  fi
  echo "OK: /api/app-config serves minimum_build_number=$floor"
  echo "Rollback: $0 apply ${previous:-0}   (FORCE=1 not needed for a lower floor)"
}

current() {
  echo ".env:   ${ENV_FILE} → MINIMUM_BUILD_NUMBER=$(env_floor)"
  echo "served: $(served_floor)"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  current) current ;;
  census)  census "$@" ;;
  plan)    plan "$@" ;;
  apply)   apply "$@" ;;
  *) sed -n '2,24p' "$0"; exit 2 ;;
esac
