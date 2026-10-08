#!/usr/bin/env python3
"""Deploy gate — production only gets a commit whose hosted tests passed.

deploy.yml runs this on a GitHub-hosted runner, as a job the production job
`needs:`. It finds the "Backend tests" run (.github/workflows/backend.yml) for
the exact commit being deployed, on main, waits for it to finish, and passes
only if the jobs in REQUIRED_JOBS all concluded `success` in its latest attempt.
Anything else fails closed: a red or cancelled job, a required job that is
missing or skipped (renamed in backend.yml?), no run at all, or a timeout.

Why an API check and not `on: workflow_run`: deploy.yml keeps its own `push`
trigger and path filter, so a docs-only merge still never deploys and every
merge that touches a deploy path still deploys — through this gate, which it
cannot route around. A manual `workflow_dispatch` deploy is gated the same way.
workflow_run would instead deploy on any green Backend tests run (its paths,
not the deploy's), leave manual deploys ungated, and silently skip — no alert —
when tests are red. Polling happens here, on a hosted runner, so the production
runner is not held while tests run.

Usage:
  CI:          python3 ops/tools/deploy_gate.py --sha "$GITHUB_SHA"
  local check: GH_TOKEN=$(gh auth token) python3 ops/tools/deploy_gate.py --sha <sha> --once
  preflight:   python3 ops/tools/deploy_gate.py --check-env /root/tutor-guardian/.env
Exit: 0 pass · 1 fail · 2 misuse · 3 still waiting (--once only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

WORKFLOW = "backend.yml"
# Job names in backend.yml. backend/tests/test_deploy_gate_paths.py fails if
# one of them disappears from that file, so a rename cannot quietly turn every
# deploy red (or, worse, be "fixed" by dropping the name from this list).
REQUIRED_JOBS = ("pytest", "KB integrity", "ruff")
BRANCH = "main"
EVENTS = ("push", "workflow_dispatch")


# ── CLOUD_BUDGET_ENFORCE preflight (runs on the production host) ─────────
# A stdlib copy of app.config.llm_config.cloud_budget_enforce_state, so the
# check runs from `git show` before the checkout moves;
# backend/tests/test_cloud_budget_operability.py keeps the two equal.
_ENFORCE_ON = ("1", "true", "yes", "on")
_ENFORCE_OFF = ("", "0", "false", "no", "off")


def cloud_budget_enforce_state(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in _ENFORCE_ON:
        return "on"
    if value in _ENFORCE_OFF:
        return "off"
    return "unrecognised"


def _env_value(value: str) -> str:
    """Remove whitespace-prefixed comments outside quotes, then unquote."""
    quote = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote:
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and index > 0 and value[index - 1].isspace():
            value = value[:index]
            break
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def check_env_file(path: str) -> int:
    """0 when CLOUD_BUDGET_ENFORCE in this .env is on/off/unset, 1 when it is
    a value the app would not recognise (read as ON and only logged), 2 when
    the file cannot be read. The last assignment wins, as in env_file."""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError as exc:
        print(f"❌ cannot read {path}: {exc}")
        return 2
    raw = None
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == "CLOUD_BUDGET_ENFORCE":
            raw = _env_value(value)
    state = cloud_budget_enforce_state(raw)
    if state == "unrecognised":
        print("❌ CLOUD_BUDGET_ENFORCE in .env is not one of "
              f"{'/'.join(_ENFORCE_ON)} or {'/'.join(v for v in _ENFORCE_OFF if v)}/unset — "
              "the app would read it as ON; fix the value before deploying")
        return 1
    print(f"✅ CLOUD_BUDGET_ENFORCE: {state}")
    return 0


def pick_run(runs: list[dict], sha: str, branch: str = BRANCH,
             events: tuple[str, ...] = EVENTS) -> dict | None:
    """The newest Backend tests run for this commit on main (push or manual)."""
    mine = [r for r in runs
            if r.get("head_sha") == sha and r.get("head_branch") == branch
            and r.get("event") in events]
    return max(mine, key=lambda r: (r.get("created_at") or "", r.get("id") or 0), default=None)


def judge(jobs: list[dict], required: tuple[str, ...] = REQUIRED_JOBS) -> tuple[str, list[str]]:
    """("pass" | "fail" | "wait", one line per required job)."""
    lines, verdict = [], "pass"
    for name in required:
        named = [j for j in jobs if j.get("name") == name]
        if not named:
            lines.append(f"{name}: MISSING from the run")
            verdict = "fail"
            continue
        job = max(named, key=lambda j: j.get("id") or 0)
        if job.get("status") != "completed":
            lines.append(f"{name}: {job.get('status')}")
            if verdict == "pass":
                verdict = "wait"
            continue
        conclusion = job.get("conclusion")
        lines.append(f"{name}: {conclusion}")
        if conclusion != "success":
            verdict = "fail"
    return verdict, lines


class Api:
    def __init__(self, repo: str, token: str) -> None:
        self.base = f"https://api.github.com/repos/{repo}"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tutor-guardian-deploy-gate",
        }

    def get(self, path: str) -> dict:
        last: Exception | None = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(self.base + path, headers=self.headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                if exc.code < 500 and exc.code != 429:
                    raise
                last = exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"GitHub API unreachable for {path}: {last}")


def evaluate(api: Api, sha: str) -> tuple[str, list[str], dict | None]:
    runs = api.get(f"/actions/workflows/{WORKFLOW}/runs?head_sha={sha}&per_page=50")
    run = pick_run(runs.get("workflow_runs", []), sha)
    if run is None:
        return "missing", [], None
    if run.get("status") != "completed":
        return "wait", [f"run status: {run.get('status')}"], run
    jobs = api.get(f"/actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    verdict, lines = judge(jobs.get("jobs", []))
    return verdict, lines, run


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--sha")
    ap.add_argument("--check-env", metavar="ENV_FILE",
                    help="only check CLOUD_BUDGET_ENFORCE in this .env (production preflight)")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--ref", default=os.environ.get("GITHUB_REF", f"refs/heads/{BRANCH}"),
                    help="the ref being deployed; only main may deploy")
    ap.add_argument("--timeout", type=int, default=50 * 60, help="seconds, overall")
    ap.add_argument("--appear-timeout", type=int, default=10 * 60,
                    help="seconds to wait for the run to exist at all")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--once", action="store_true", help="evaluate once; exit 3 if not finished")
    args = ap.parse_args(argv)

    if args.check_env:
        return check_env_file(args.check_env)
    if not args.sha:
        print("need --sha (or --check-env ENV_FILE)")
        return 2
    if args.ref != f"refs/heads/{BRANCH}":
        print(f"❌ refusing to deploy {args.ref}: only {BRANCH} deploys")
        return 1
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not (args.repo and token and len(args.sha) == 40):
        print("need --repo (or GITHUB_REPOSITORY), GH_TOKEN/GITHUB_TOKEN and a full 40-char --sha")
        return 2

    api = Api(args.repo, token)
    short = args.sha[:8]
    start = time.monotonic()
    while True:
        verdict, lines, run = evaluate(api, args.sha)
        waited = int(time.monotonic() - start)
        where = (f"Backend tests run {run.get('run_number')} ({run.get('event')}, attempt "
                 f"{run.get('run_attempt')}) {run.get('html_url')}") if run else "Backend tests"
        if verdict == "pass":
            print(f"✅ {where} passed for {short} after {waited}s: " + " · ".join(lines))
            _summary(f"✅ deploy gate: {short} — " + " · ".join(lines))
            return 0
        if verdict == "fail":
            print(f"❌ {where} did not pass for {short}: " + " · ".join(lines))
            _summary(f"❌ deploy gate: {short} — " + " · ".join(lines))
            return 1
        if verdict == "missing" and waited >= args.appear_timeout:
            print(f"❌ no Backend tests run for {args.sha} on {BRANCH} after {waited}s. "
                  "Either the push matched none of backend.yml's push paths (they must "
                  "cover deploy.yml's — backend/tests/test_deploy_gate_paths.py checks it) "
                  "or the commit carried [skip ci]. Run Backend tests on main by hand "
                  "(Actions → Backend tests → Run workflow), then re-run this deploy.")
            _summary(f"❌ deploy gate: no Backend tests run for {short}")
            return 1
        if args.once:
            print(f"⏳ {where} for {short}: {verdict} " + " · ".join(lines))
            return 3
        if waited >= args.timeout:
            print(f"❌ {where} for {short} still not finished after {waited}s: "
                  + " · ".join(lines))
            return 1
        print(f"⏳ {waited:>4}s {verdict}: " + (" · ".join(lines) or "waiting for the run"),
              flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
