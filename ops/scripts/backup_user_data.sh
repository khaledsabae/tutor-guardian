#!/usr/bin/env bash
# Nightly backup of tutor-guardian production user data.
#
# Snapshots every SQLite DB in the tg_sessions volume (/app/ops inside the
# tg_backend container) using the online backup API — safe against concurrent
# writes, unlike a raw cp. Each copy is integrity-checked before it counts.
#
# Runs from root cron on the VPS:
#   30 3 * * * /root/tutor-guardian/ops/scripts/backup_user_data.sh >> /var/log/tg-backup.log 2>&1
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/root/tg-backups}"
CONTAINER="${CONTAINER:-tg_backend}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DEST="$BACKUP_ROOT/$(date +%F_%H%M)"

mkdir -p "$DEST"

# Backup + integrity-check inside the container (host has no sqlite3 CLI).
docker exec -i "$CONTAINER" python - <<'PY'
import glob, os, sqlite3, sys

tmp = "/app/ops/.backup_tmp"
os.makedirs(tmp, exist_ok=True)
dbs = glob.glob("/app/ops/*.db")
if not dbs:
    sys.exit("no .db files found in /app/ops — refusing to write an empty backup")
for db in dbs:
    dst = os.path.join(tmp, os.path.basename(db))
    src, out = sqlite3.connect(db), sqlite3.connect(dst)
    with out:
        src.backup(out)
    ok = out.execute("PRAGMA integrity_check").fetchone()[0]
    src.close(); out.close()
    if ok != "ok":
        sys.exit(f"integrity_check failed for {dst}: {ok}")
    print(f"backed up {db} ({os.path.getsize(dst)} bytes, integrity ok)")
PY

docker cp "$CONTAINER":/app/ops/.backup_tmp/. "$DEST/"
docker exec "$CONTAINER" rm -rf /app/ops/.backup_tmp

gzip -f "$DEST"/*.db

# Retention: drop dated backup dirs older than RETENTION_DAYS.
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -exec rm -rf {} +

echo "OK $(date -Is) -> $DEST ($(ls "$DEST" | tr '\n' ' '))"
