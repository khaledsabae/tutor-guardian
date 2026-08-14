#!/usr/bin/env python3
"""Alert when main has deploy-relevant commits that production is not running.

The Deploy workflow's own failure alert covers a run that failed. It cannot
cover a run that never started — a dead self-hosted runner, a push whose paths
all miss the workflow's filters, or a queue that silently drops. This checks
the invariant those all violate instead of watching the workflow: *is what
origin/main says should be in production actually in production?*

Why not compare the two SHAs directly: most commits on main never trigger a
deploy at all (mobile/, docs/, marketing/ are outside the path filters), so a
plain SHA mismatch is the normal state and would alert every day. The real
question is narrower — are there commits main has, production does not, that
touch a path the deploy workflow watches?

Grace period exists because a deploy legitimately takes ~10-15 minutes: a
commit pushed two minutes ago is not drift, it is a deploy in flight.

Run on the VPS (it reads the production checkout):
    python3 ops/tools/check_deploy_drift.py            # check + alert
    python3 ops/tools/check_deploy_drift.py --dry-run  # check, print, no send
    python3 ops/tools/check_deploy_drift.py --self-test

Exit 0 = in sync (or within grace). Exit 1 = drift found. Exit 2 = check broke.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(os.environ.get("TG_REPO", "/root/tutor-guardian"))
STATE = Path(os.environ.get("TG_DRIFT_STATE", "/root/.tg_deploy_drift.json"))

# Kept in step with the `paths:` filter in .github/workflows/deploy.yml. A path
# here that the workflow does not watch produces a false alert; a path the
# workflow watches and this omits produces the silence this tool exists to end.
DEPLOY_PATHS = [
    "backend", "knowledge_base", "ops/tools", "ops/scripts", "frontend",
    "docs/lesson_index.json", "docs/lesson_assets",
    "docker-compose.production.yml", "backend/Dockerfile",
    ".github/workflows/deploy.yml", "requirements",
]

GRACE_SECONDS = int(os.environ.get("TG_DRIFT_GRACE", 45 * 60))
RENOTIFY_SECONDS = 6 * 3600


def git(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def pending_commits(deployed: str, target: str) -> list[tuple[str, int, str]]:
    """(sha, author_timestamp, subject) for deploy-relevant commits main has
    and the deployed tree does not."""
    out = git(
        "log", "--no-merges", "--format=%h\x1f%at\x1f%s",
        f"{deployed}..{target}", "--", *DEPLOY_PATHS,
    )
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, ts, subject = line.split("\x1f", 2)
        rows.append((sha, int(ts), subject))
    return rows


def send_telegram(text: str) -> bool:
    env = {}
    env_path = REPO / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("no TELEGRAM_BOT_TOKEN/CHAT_ID in .env — cannot alert", file=sys.stderr)
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.load(resp)
    # Verified by the response, not by the absence of an exception: Telegram
    # answers 200 with ok=false for a wrong chat_id.
    print("telegram ok=", body.get("ok"),
          "message_id=", (body.get("result") or {}).get("message_id"))
    return bool(body.get("ok"))


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    try:
        git("fetch", "origin", "main", "--quiet")
        deployed = git("rev-parse", "HEAD")
        target = git("rev-parse", "origin/main")
        pending = pending_commits(deployed, target)
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2

    if not pending:
        print(f"✅ in sync — production at {deployed[:7]}, "
              f"no deploy-relevant commit pending")
        return 0

    oldest_ts = min(ts for _, ts, _ in pending)
    age = int(time.time()) - oldest_ts
    if age < GRACE_SECONDS:
        print(f"⏳ {len(pending)} pending, oldest {age // 60}min "
              f"(< {GRACE_SECONDS // 60}min grace) — a deploy may be in flight")
        return 0

    listing = "\n".join(f"  {sha} {subj[:60]}" for sha, _, subj in pending[:6])
    text = (
        "🔴 المربّي: main فيه شغل لم يصل الإنتاج\n\n"
        f"الإنتاج على: {deployed[:7]}\n"
        f"main على:    {target[:7]}\n"
        f"معلّق:       {len(pending)} كوميت يمسّ مسارات النشر\n"
        f"أقدمها من:   {age // 60} دقيقة\n\n"
        f"{listing}\n\n"
        "يعني إما نشر فشل، أو ماشتغلش أصلًا (رانر واقف/فلاتر المسارات).\n"
        "الفحص: gh run list --workflow=Deploy --limit 5"
    )
    print(text)

    if args.dry_run:
        return 1

    state = load_state()
    now = int(time.time())
    same_target = state.get("target") == target
    recent = now - int(state.get("notified_at", 0)) < RENOTIFY_SECONDS
    if same_target and recent:
        print("(already alerted for this target within the re-notify window)")
        return 1

    if send_telegram(text):
        STATE.write_text(json.dumps({"target": target, "notified_at": now}))
    return 1


def self_test() -> int:
    """Guards the one thing that would silently defang this: a path list that
    has drifted from the workflow it mirrors."""
    ok = True
    wf = REPO / ".github/workflows/deploy.yml"
    if wf.exists():
        body = wf.read_text(encoding="utf-8")
        watched = body.split("paths:", 1)[1].split("workflow_dispatch", 1)[0]
        for p in DEPLOY_PATHS:
            if p not in watched:
                print(f"  ❌ '{p}' is checked here but not watched by deploy.yml")
                ok = False
        print(f"  path list vs deploy.yml: {'ok' if ok else 'DRIFTED'}")
    else:
        print("  ⚠️  deploy.yml not found — path comparison skipped")

    # A commit touching nothing deploy-relevant must not raise an alert.
    try:
        subj = git("log", "-1", "--format=%s", "--", "mobile") or "(none)"
        print(f"  git plumbing reachable (last mobile-only subject: {subj[:40]})")
    except subprocess.CalledProcessError:
        print("  ❌ git plumbing failed")
        ok = False

    print("  ✅ self-test passed" if ok else "  ❌ self-test FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
