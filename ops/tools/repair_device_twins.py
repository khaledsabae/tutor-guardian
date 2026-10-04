#!/usr/bin/env python3
"""
Re-attach families whose install split into device twins — one-off repair.
==========================================================================
From 1.0.58 to 1.0.67 every app process ran main() twice, and on a fresh
install each copy minted its own device id: the family's device (the child
lives there) and a childless twin with the same FCM token. After a restart some
apps came back as the twin, and the parent saw no child. The backend now folds
a twin into its family on the twin's next push registration or proof-carrying
mint (backend/app/services/device_twins.py); this script does the same for the
backlog in one pass — including twins whose token was renewed since, which the
request-time rule deliberately does not trust.

The rule is the runtime one (backend/app/services/device_twins.py, module
doc), minus the request credential — there is no request here; an operator
runs this — and re-decided under the write lock for every pair (`fold_pair`):
the cohort (both born from 2026-09-12, the twin before TWIN_FOLD_BORN_BEFORE),
a childless twin sharing its FCM token with exactly one device that has a
child, born within a minute of it, and then either the family identity went
quiet after its first session while the twin is in use (the app came back as
the twin) or the twin went quiet (a phantom). Two halves both in use are never
folded. Tokens: only the twin's birth-window ones move, unless
--include-later-twin-tokens. Colliding unique-key rows stay with the twin;
every moved or deleted row is logged in device_fold_log (revert_fold undoes a
fold).

DEFAULT IS A DRY RUN. It opens the database read-only (`mode=ro`) and prints
aggregates only — no device ids, no names, no tokens.

  # on the VPS, once this file is deployed:
  docker exec -i -w /app tg_backend python ops/tools/repair_device_twins.py
  # before it is deployed, the read-only dry run can be piped in with the
  # service module it imports:
  python3 ops/tools/repair_device_twins.py --bundle | \\
      ssh root@<vps> 'docker exec -i -w /app tg_backend python -'

  --apply   fold every twin into its family. Takes a sqlite3.backup() snapshot
            first (--backup-dir), then one transaction per pair. Prints counts
            and log-safe device tags. Not run by agents: production writes are
            Khaled's call (publishing-center/OPERATIONS_LOG.md entry + commit).
"""
from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

# A childless device born this close to a childful one, with no FCM token in
# common, is reported (it is how most twins look when notification permission
# was refused) but never folded: without the shared token nothing proves the
# two are one install, and at launch-spike volume two families do get born in
# the same seconds.
TIME_ONLY_WINDOW_SECONDS = 2

# Push rows that moved apart by more than this after birth tell us which half
# the app has been running as since (every launch re-registers the identity on
# disk).
RELAUNCH_SECONDS = 60


def survey(conn: sqlite3.Connection, twins) -> dict:
    """Classify every device pair the split could have produced. Read-only."""
    q = conn.execute
    born = {d: twins.first_seen(conn, d) for (d,) in q("SELECT DISTINCT device_id FROM api_tokens")}
    kids = dict(q("SELECT device_id, COUNT(*) FROM child_profiles GROUP BY device_id").fetchall())
    push = {d: (tok, twins._when(upd), build) for d, tok, upd, build in
            q("SELECT device_id, token, updated_at, build_number FROM push_tokens")}
    holders = collections.defaultdict(list)
    for d, (tok, _, _) in push.items():
        holders[tok].append(d)
    # The emulator E2E gate (.github/workflows/mobile-e2e.yml) runs against
    # production and names its test child E2E-Maestro; its baseline lineage is
    # a build that still splits, so some twins here are test devices.
    e2e = {d for (d,) in q("SELECT DISTINCT device_id FROM child_profiles WHERE name LIKE 'E2E-Maestro%'")}

    out = collections.Counter()
    pairs = []          # (twin, family, kind, has_later_tokens) — what --apply folds
    for device, (tok, updated, _build) in push.items():
        if kids.get(device):
            continue
        others = [o for o in holders[tok] if o != device]
        if not others:
            continue
        with_children = [o for o in others if kids.get(o)]
        if not with_children:
            out["shared_token_no_child_anywhere"] += 1
            continue
        if len(with_children) > 1:
            out["ambiguous_several_families_on_one_token"] += 1
            continue
        if twins.family_of(conn, device, within_cohort=False) is None:
            out["same_token_born_apart_not_folded"] += 1     # identity resets, not the race
            continue
        family = twins.family_of(conn, device)
        if family is None:
            out["twin_outside_cohort_not_folded"] += 1
            continue
        kind = twins.repairable(conn, device, family)
        tag = " (e2e)" if family in e2e else ""
        if kind is None:
            out[f"twin:both_halves_in_use_not_folded{tag}"] += 1
            continue
        family_born = twins.first_seen(conn, family)
        later = any(not twins._within_window(twins._when(c), family_born) for (c,) in
                    q("SELECT created_at FROM api_tokens WHERE device_id = ?", (device,)))
        out[f"twin:{kind}{tag}"] += 1
        if later:
            out[f"twin:{kind}{tag}:twin_has_later_tokens"] += 1
        pairs.append((device, family, kind, later))

    # Both halves with children: the parent re-onboarded on the twin. Same
    # install (shared token, same seconds) but two children now — reported,
    # never folded automatically.
    for tok, ds in holders.items():
        ds = [d for d in ds if kids.get(d) and born.get(d)]
        for i, a in enumerate(ds):
            for b in ds[i + 1:]:
                if abs((born[a] - born[b]).total_seconds()) <= twins.TWIN_WINDOW_SECONDS:
                    out["both_halves_have_a_child_reonboarded"] += 1

    # Twins with no FCM token in common (notification permission refused or
    # not yet answered when the twin registered): visible only by birth time.
    seq = sorted((t, d) for d, t in born.items() if t)
    times = [t for t, _ in seq]
    import bisect
    childful = [d for d in kids if born.get(d)]
    time_only = 0
    time_only_active = 0
    for d in childful:
        t = born[d]
        i = bisect.bisect_left(times, t - _secs(TIME_ONLY_WINDOW_SECONDS))
        while i < len(seq) and seq[i][0] <= t + _secs(TIME_ONLY_WINDOW_SECONDS):
            o = seq[i][1]
            i += 1
            if o == d or kids.get(o):
                continue
            if push.get(o) and push.get(d) and push[o][0] == push[d][0]:
                continue                       # counted above with the token
            time_only += 1
            last = max(filter(None, [
                push.get(o, (None, None, None))[1],
                twins._when(q("SELECT MAX(created_at) FROM api_tokens WHERE device_id = ?", (o,)).fetchone()[0]),
                twins._when(q("SELECT MAX(m.created_at) FROM chat_messages m JOIN chat_sessions s "
                        "ON s.id = m.session_id WHERE s.device_id = ?", (o,)).fetchone()[0]),
            ]), default=None)
            if last and last > t + _secs(RELAUNCH_SECONDS):
                time_only_active += 1
            break
    out["time_only_twin_not_folded"] = time_only
    out["time_only_twin_used_after_first_minute"] = time_only_active

    # Devices on an id the API now refuses (stored before SessionCreate
    # validated it): their app gets 422 at every mint until the fixed build
    # moves them to a valid id on its next proof-carrying mint.
    refused = [d for d in born if not twins.is_valid_device_id(d)]
    out["refused_id_devices"] = len(refused)
    out["refused_id_devices_with_children"] = sum(1 for d in refused if kids.get(d))
    return {"counts": dict(out), "pairs": pairs}


def _secs(n: int):
    from datetime import timedelta
    return timedelta(seconds=n)


def _open(path: Path, readonly: bool) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="read-only survey (default)")
    mode.add_argument("--apply", action="store_true", help="fold every twin into its family")
    ap.add_argument("--db", type=Path, help="database (default: CONVERSATIONS_DB / the app's)")
    ap.add_argument("--backup-dir", type=Path, default=ROOT / "ops" / "backups")
    ap.add_argument("--limit", type=int, default=0, help="--apply at most N pairs (0 = all)")
    ap.add_argument("--include-later-twin-tokens", action="store_true",
                    help="with --apply, also move twin tokens minted after the birth minute. "
                         "Reaches families whose app renewed its token, at the price that ANY "
                         "token ever minted for that twin id then opens the family")
    ap.add_argument("--bundle", action="store_true",
                    help="print this script with the service module inlined, for piping a "
                         "dry run into a container that does not have the module yet")
    args = ap.parse_args(argv)

    if args.bundle:
        sys.stdout.write(_bundle())
        return 0

    from app.db.init_db import db_path
    from app.services import device_twins as twins

    path = args.db or db_path()
    conn = _open(path, readonly=not args.apply)
    report = survey(conn, twins)
    counts = report["counts"]
    print(f"device twin survey — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — "
          f"window {twins.TWIN_WINDOW_SECONDS}s")
    for key in sorted(counts):
        print(f"  {key:48s} {counts[key]}")
    pairs = report["pairs"]
    later = sum(1 for *_, has_later in pairs if has_later)
    print(f"  {'=> foldable twins (what --apply would fold)':48s} {len(pairs)}")
    print(f"  {'   of which the twin has later tokens':48s} {later}")
    print("     (their app holds a token minted after the birth minute: --apply moves it")
    print("      only with --include-later-twin-tokens — see the module doc)")

    if not args.apply:
        print("dry run: nothing written")
        return 0

    conn.close()
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    snapshot = args.backup_dir / f"conversations.pre-twin-repair-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.db"
    src = sqlite3.connect(path)
    dst = sqlite3.connect(snapshot)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print(f"snapshot: {snapshot}")

    from app.core.log_safety import device_tag
    conn = _open(path, readonly=False)
    done = 0
    for twin, family, kind, _later in pairs[: args.limit or None]:
        # Re-decided under the write lock: the app may have folded it meanwhile.
        folded, moved = twins.fold_pair(conn, twin, family, all_tokens=args.include_later_twin_tokens)
        if folded is None:
            print(f"  skip {device_tag(twin)}: no longer a foldable twin")
            continue
        done += 1
        print(f"  folded {device_tag(twin)} -> {device_tag(family)} [{folded}] "
              + ", ".join(f"{k}={v}" for k, v in sorted(moved.items())))
    print(f"folded {done} of {len(pairs)}  (undo one: device_twins.revert_fold(conn, twin))")
    return 0


def _bundle() -> str:
    """This script, preceded by the service module registered under its import
    name — so `python -` in an older container runs the same code.

    Every name the service imports from `app.*` and the container may not have
    yet (it predates this change) is supplied from this checkout's source:
    the defining top-level statements are picked out with `ast` and added to
    the container's module only where the name is missing — nothing it already
    has is replaced.
    """
    import ast

    backend = ROOT / "backend"
    service = (backend / "app" / "services" / "device_twins.py").read_text(encoding="utf-8")
    supply = []
    for node in ast.parse(service).body:
        if not (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.")):
            continue
        source = (backend / Path(*node.module.split("."))).with_suffix(".py").read_text(encoding="utf-8")
        wanted = {alias.name for alias in node.names}
        tree = ast.parse(source)
        defined = {}
        for stmt in tree.body:
            names = ([stmt.name] if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)) else
                     [t.id for t in getattr(stmt, "targets", []) if isinstance(t, ast.Name)])
            for name in names:
                defined[name] = stmt
        # A picked function may lean on module globals defined beside it.
        picked, queue = {}, list(wanted)
        while queue:
            name = queue.pop()
            stmt = defined.get(name)
            if stmt is None or name in picked:
                continue
            picked[name] = stmt
            queue.extend(n.id for n in ast.walk(stmt) if isinstance(n, ast.Name) and n.id in defined)
        # The statements' own text (not ast.unparse, whose output follows the
        # Python that builds the bundle, not the container's 3.11).
        code = "\n\n".join(ast.get_source_segment(source, stmt) for stmt in picked.values())
        supply.append((node.module, sorted(picked), code))

    future = "from __future__ import annotations\n"
    me = Path(__file__).read_text(encoding="utf-8").replace(future, "", 1)
    prelude = [future, "import importlib, sys, types\n"]  # future: must stay first
    for module, names, code in supply:
        prelude.append(
            f"_mod = importlib.import_module({module!r})\n"
            f"_ns = dict(_mod.__dict__)\n"
            f"exec(compile({code!r}, {module!r}, 'exec'), _ns)\n"
            f"[setattr(_mod, _n, _ns[_n]) for _n in {names!r} if not hasattr(_mod, _n)]\n"
        )
    prelude.append(
        "_m = types.ModuleType('app.services.device_twins')\n"
        "_m.__file__ = 'bundled:device_twins.py'\n"
        f"exec(compile({service!r}, 'device_twins.py', 'exec'), _m.__dict__)\n"
        "sys.modules['app.services.device_twins'] = _m\n"
        "import app.services as _s; _s.device_twins = _m\n"
        "sys.argv = ['repair_device_twins.py', '--dry-run']\n"
        # `python -` has no __file__; the container keeps the repo at /app.
        "__file__ = '/app/ops/tools/repair_device_twins.py'\n"
    )
    return "".join(prelude) + me


if __name__ == "__main__":
    sys.exit(main())
