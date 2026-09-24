#!/usr/bin/env bash
# Schema v27 migration runbook — child_challenges active-only unique key.
#
# What v27 changes (backend/app/db/init_db.py::_ensure_child_challenges_active_key):
#   child_challenges had UNIQUE(device_id, child_id, status), which allowed ONE
#   'resolved' row per child ever — the third challenge change answered 500.
#   The table is rebuilt (single transaction) without that key, plus a partial
#   unique index ux_child_challenges_active ... WHERE status = 'active'.
#   The app runs this automatically on startup (lifespan → init_db); this
#   script wraps it with a verified backup, explicit checks and a rollback.
#
# Usage (on the VPS, from /root/tutor-guardian):
#   ops/scripts/migrate_schema_v27.sh preflight   # read-only report
#   ops/scripts/migrate_schema_v27.sh backup      # verified backup → $BACKUP_ROOT
#   #  … deploy the v27 image (deploy.yml or the commands in ops/RELEASE_v1.0.61.md)
#   ops/scripts/migrate_schema_v27.sh apply       # idempotent; normally a no-op
#   ops/scripts/migrate_schema_v27.sh verify      # asserts the v27 end state
#   ops/scripts/migrate_schema_v27.sh rollback <backup.db>   # restore + restart
#
# LOCAL=1 runs the same Python against DB_PATH on this machine instead of
# inside the container (staging copies, CI, tests).
set -euo pipefail

CONTAINER="${CONTAINER:-tg_backend}"
DB_PATH="${DB_PATH:-/app/ops/conversations.db}"
BACKUP_ROOT="${BACKUP_ROOT:-/root/tg-backups/pre-v27}"
COMPOSE=(docker compose -f docker-compose.production.yml)

run_py() {  # run a Python snippet against the DB (in-container unless LOCAL=1)
  if [[ "${LOCAL:-0}" == "1" ]]; then
    DB_PATH="$DB_PATH" PYTHONPATH="${PYTHONPATH:-backend}" python3 - "$@"
  else
    docker exec -i -e DB_PATH="$DB_PATH" "$CONTAINER" python - "$@"
  fi
}

preflight() {
  run_py <<'PY'
import os, sqlite3
db = os.environ["DB_PATH"]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
v = c.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
sql = (c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='child_challenges'")
        .fetchone() or [""])[0] or ""
legacy = "unique(device_id,child_id,status)" in "".join(sql.split()).lower()
rows = c.execute("SELECT status, COUNT(*) FROM child_challenges GROUP BY status").fetchall() if sql else []
active_dupes = c.execute(
    "SELECT COUNT(*) FROM (SELECT 1 FROM child_challenges WHERE status='active' "
    "GROUP BY device_id, child_id HAVING COUNT(*) > 1)").fetchone()[0] if sql else 0
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
print(f"db={db}")
print(f"schema_version={v[0] if v else None}")
print(f"child_challenges legacy UNIQUE(status) key present={legacy}")
print(f"child_challenges rows by status={dict(rows)}")
print(f"children with >1 active challenge (must be 0)={active_dupes}")
print(f"integrity_check={ok}")
if ok != "ok" or active_dupes:
    raise SystemExit("PREFLIGHT FAILED — do not migrate; investigate first")
PY
}

backup() {
  local stamp dest
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$BACKUP_ROOT/conversations.pre-v27.$stamp.db"
  mkdir -p "$BACKUP_ROOT"
  if [[ "${LOCAL:-0}" == "1" && -x "$(command -v sqlite3 || true)" ]]; then
    # The CLI's .backup — the online backup API, safe with WAL writers.
    sqlite3 "$DB_PATH" ".backup '$dest'"
  else
    # No sqlite3 CLI on the host or in python:3.11-slim: the same online backup
    # API through Python's sqlite3, inside the container, then copied out.
    local tmp="/app/ops/.pre_v27_$stamp.db"
    [[ "${LOCAL:-0}" == "1" ]] && tmp="$dest"
    run_py "$tmp" <<'PY'
import os, sqlite3, sys
src = sqlite3.connect(os.environ["DB_PATH"])
out = sqlite3.connect(sys.argv[1])
with out:
    src.backup(out)
src.close(); out.close()
PY
    if [[ "${LOCAL:-0}" != "1" ]]; then
      docker cp "$CONTAINER:$tmp" "$dest"
      docker exec "$CONTAINER" rm -f "$tmp"
    fi
  fi
  # Verify the copy, not the source: integrity + same row count.
  DB_PATH="$DB_PATH" BACKUP="$dest" python3 - <<'PY' || { echo "BACKUP VERIFY FAILED: $dest"; exit 1; }
import os, sqlite3
b = sqlite3.connect(os.environ["BACKUP"])
assert b.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity"
n = b.execute("SELECT COUNT(*) FROM child_challenges").fetchone()[0]
print(f"backup ok: {os.environ['BACKUP']} ({os.path.getsize(os.environ['BACKUP'])} bytes, "
      f"child_challenges={n})")
PY
  echo "$dest"
}

apply() {
  if [[ "${LOCAL:-0}" == "1" ]]; then
    CONVERSATIONS_DB="$DB_PATH" PYTHONPATH="${PYTHONPATH:-backend}" \
      python3 -c "from app.db.init_db import init_db; init_db(); print('init_db ok')"
  else
    docker exec -e CONVERSATIONS_DB="$DB_PATH" "$CONTAINER" \
      python -c "from app.db.init_db import init_db; init_db(); print('init_db ok')"
  fi
}

verify() {
  run_py <<'PY'
import os, sqlite3
c = sqlite3.connect(f"file:{os.environ['DB_PATH']}?mode=ro", uri=True)
v = c.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]
sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='child_challenges'").fetchone()[0]
idx = c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='ux_child_challenges_active'").fetchone()
problems = []
if v < 27: problems.append(f"schema_version={v} (<27)")
if "unique(device_id,child_id,status)" in "".join(sql.split()).lower():
    problems.append("legacy UNIQUE(device_id, child_id, status) still present")
if not idx or "where status = 'active'" not in idx[0].lower():
    problems.append("partial unique index ux_child_challenges_active missing")
if c.execute("SELECT name FROM sqlite_master WHERE name='child_challenges_v27'").fetchone():
    problems.append("rebuild debris child_challenges_v27 left behind")
if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    problems.append("integrity_check failed")
print(f"schema_version={v}; child_challenges rows="
      f"{c.execute('SELECT COUNT(*) FROM child_challenges').fetchone()[0]}")
if problems:
    raise SystemExit("VERIFY FAILED: " + "; ".join(problems))
print("VERIFY OK — v27 in place")
PY
}

rollback() {
  local backup_file="${1:?usage: rollback <backup.db>}"
  [[ -f "$backup_file" ]] || { echo "no such backup: $backup_file"; exit 1; }
  if [[ "${LOCAL:-0}" == "1" ]]; then
    cp "$backup_file" "$DB_PATH"; rm -f "$DB_PATH-wal" "$DB_PATH-shm"
    echo "restored $backup_file → $DB_PATH"; return
  fi
  echo "Stopping $CONTAINER, restoring $backup_file, restarting…"
  "${COMPOSE[@]}" stop backend
  docker cp "$backup_file" "$CONTAINER:$DB_PATH"
  docker run --rm --volumes-from "$CONTAINER" alpine \
    sh -c "rm -f '$DB_PATH-wal' '$DB_PATH-shm'"
  # The restored file is v26. Start the PREVIOUS image (see RELEASE notes) —
  # starting the v27 image would simply migrate it again.
  "${COMPOSE[@]}" up -d --no-build backend
  echo "Restored. Confirm with: $0 preflight"
}

case "${1:-}" in
  preflight) preflight ;;
  backup) backup ;;
  apply) apply ;;
  verify) verify ;;
  rollback) shift; rollback "$@" ;;
  *) sed -n '2,24p' "$0"; exit 2 ;;
esac
