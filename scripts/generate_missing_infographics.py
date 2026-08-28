#!/usr/bin/env python3
"""
Generate missing infographic assets for lessons using NotebookLM.

Trigger-then-harvest, like gen_podcasts_cron.py — NOT the old blocking
`--wait` call. That mattered starting 2026-08-21: a `--wait` generate blocks on
NotebookLM's own polling internally, and when the polling RPC itself starts
throwing `RPC LIST_ARTIFACTS (TransportServerError)` — a transient backend
error, not a refusal — the whole call is scored a failure and the lesson is
walked past. Measured over six runs (08-21 through 08-28, excluding two
session-death days): the failure share climbed from ~25% to **89%** as this
got worse, while the underlying generation may well have succeeded server-side
and simply never been picked up. The trigger was never the fragile part; the
wait was.

So, mirroring gen_podcasts_cron.py exactly:
  1. harvest — poll every in-flight task; download the completed ones
  2. trigger — for each lesson with no PNG and no in-flight task, fire ONE
     `generate infographic --no-wait` (near-instant: returns a task id, does
     not block on completion) and record it
  3. exit — cron drains the backlog over runs; nothing here loops forever

This also means the daily ceiling is now spent almost entirely on real
attempts instead of losing capacity to polling errors mid-wait — the same
"per-medium quota" the audio pipeline already gets, not split against a doomed
wait.

Per lesson:
  1. resolve source_id from source_to_lesson.json (reverse map)
  2. generate an infographic via NotebookLM, grounded in that lesson's source
  3. next run's harvest downloads it once ready and records it in
     docs/lesson_index.json
Finally: one git commit + push for the whole batch, covering whatever the
harvest of THIS run recovered.

Lessons whose source is missing/empty are skipped and recorded in
scripts/infographics_blocked.json (same gap that blocks their reports).

Usage:
  ./notebooklm_env/bin/python scripts/generate_missing_infographics.py [--lang en] [--limit N] [--harvest-only]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
INFO_DIR = BASE_DIR / "docs" / "lesson_assets" / "infographics"
INDEX_PATH = BASE_DIR / "docs" / "lesson_index.json"
SRC_MAP_PATH = BASE_DIR / "source_to_lesson.json"
BLOCKED_PATH = BASE_DIR / "scripts" / "infographics_blocked.json"
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
NLM = str(BASE_DIR / "notebooklm_env" / "bin" / "notebooklm")
RESOLUTION = "2752x1536"

sys.path.insert(0, str(BASE_DIR / "backend"))
from app.media_naming import AUDIO_CLI_LANG, SOURCE_LANG  # noqa: E402


def _arg_lang() -> str:
    """`--lang en`. Defaults to Arabic so existing invocations are unchanged."""
    if "--lang" in sys.argv:
        value = sys.argv[sys.argv.index("--lang") + 1]
        if value not in AUDIO_CLI_LANG:
            sys.exit(f"❌ unknown --lang {value!r}; known: {sorted(AUDIO_CLI_LANG)}")
        return value
    return SOURCE_LANG


# 🚨 An infographic is text rendered into PIXELS, so it is the least
# translatable asset in the app: an English reader gets no partial
# understanding and there is no fallback — the text IS the image. That also
# makes it the one asset where the generator's own text rendering is a content
# risk. A shipped Arabic example, 64_lesson_16-18_medical_adult_transition_b04:
# the heading meant to read «روتين يومي مش مثالي» rendered «مش» as a broken
# glyph cluster, leaving it visually identical to the «روتين يومي مثالي» panel
# above it — two panels teaching opposite things, told apart by one corrupted
# word. Proofread output rather than trusting it.
LANG = _arg_lang()
CLI_LANG = AUDIO_CLI_LANG[LANG]
# Arabic keeps the bare filename it has always had; other languages are tagged.
LANG_TAG = "" if LANG == SOURCE_LANG else f"_{LANG}"

sys.path.insert(0, str(BASE_DIR))
from scripts.infographic_prompts_lib import buildable_targets  # noqa: E402

STARTED_RE = re.compile(r"(?:Started|Task):\s*([0-9a-f-]{36})")
EMPTY_MARKERS = ("No parseable chunks", "Source not found", "Error:")

# State keyed like podcast_tasks.json: bare lesson_id for Arabic (the
# original, unlagged state), `<lesson_id>@<lang>` otherwise.
STATE_FILE = BASE_DIR / "ops" / "data" / "infographic_tasks.json"
ERRORS_FILE = BASE_DIR / "ops" / "data" / "infographic_poll_errors.json"
ERROR_BUDGET = 3  # three consecutive poll errors before a task is dropped


# 🚨 Its own profile, like the audio and video generators.
#
# This file kept calling the CLI with no `-p`, so every call used `default` —
# a profile nothing logs into any more. The failure surfaces as
# "Authentication expired", which reads like a dead session and is really a
# request sent as the wrong user. Two profiles were created and this generator
# was left out of the change.
PROFILE = os.environ.get("TG_NOTEBOOKLM_PROFILE", "tg-video")


def _run(args: list[str], timeout: int) -> tuple[int, str, str]:
    p = subprocess.run(
        [NLM, "-p", PROFILE, *args], cwd=BASE_DIR,
        capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _state_key(lesson_id: str) -> str:
    return lesson_id if LANG == SOURCE_LANG else f"{lesson_id}@{LANG}"


def _split_key(key: str) -> str:
    return key.split("@", 1)[0]


def _load(p: Path, default):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
    return default


def _save(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reverse_source_map() -> dict[str, str]:
    """{lesson_id: source_id} from source_to_lesson.json ({src: [age, topic, lesson]})."""
    s2l = json.loads(SRC_MAP_PATH.read_text(encoding="utf-8"))
    rev = {}
    for src, v in s2l.items():
        if isinstance(v, list) and len(v) >= 3:
            rev[v[2]] = src
    return rev


def missing_infographic_lessons() -> list[dict]:
    lessons, _ = buildable_targets(LANG)
    return lessons


def build_description(lesson: dict) -> str:
    """Prompt for one infographic, in the target language.

    The English prompt is written, not translated: the Arabic one asks for an
    RTL layout, an Arabic typeface and «بدون أي نص إنجليزي» — translate that
    and you have asked an English infographic to contain no English.
    """
    age = lesson.get("age_group", "")
    title = lesson.get("title", "")
    desc = lesson.get("description", "")
    if LANG == "en":
        return (
            f"Create an elegant, practical parenting infographic in English for "
            f"parents of children aged {age}, titled '{title}'.\n"
            f"Cover exactly these points and nothing else:\n{desc}\n\n"
            "Requirements: soft pastel colours, a clear legible sans-serif "
            "typeface, left-to-right layout, all text in English with no Arabic "
            "text, no photographs of real people, no visual clutter. Spell every "
            "word correctly and completely — a single malformed word can invert "
            "the meaning of a panel."
        )
    return (
        f"أنشئ إنفوجرافيك تربوي عربي أنيق وعملي للأهل (الفئة العمرية {age}) بعنوان '{title}'.\n"
        f"محتوى الإنفوجرافيك يجب أن يغطي النقاط التالية حصراً:\n{desc}\n\n"
        "المتطلبات: ألوان باستيل هادئة، خط عربي واضح، تخطيط RTL، "
        "بدون أي نص إنجليزي، بدون صور أشخاص حقيقية، بدون فوضى بصرية. "
        "واكتب كل كلمة كاملة وسليمة الرسم — كلمة واحدة مشوّهة تقلب معنى اللوحة."
    )


def existing_asset(lesson: dict) -> dict | None:
    """If a PNG for this lesson is already on disk, build its index entry (no API call).

    Lets a run resume after a rate-limit or crash without re-generating (and
    re-burning quota on) infographics that were already produced."""
    lesson_id = lesson["lesson_id"]
    matches = sorted(INFO_DIR.glob(f"*_infographic_{lesson_id}{LANG_TAG}.png"))
    matches = [p for p in matches if p.stat().st_size >= 10_000]
    if not matches:
        return None
    fp = matches[-1]
    artifact_id = fp.name.split("_infographic_")[0]
    return {
        "id": f"{artifact_id}_infographic",
        "file": f"docs/lesson_assets/infographics/{fp.name}",
        "title": lesson.get("title_ar") or "إنفوجرافيك",
        "item_count": 0,
        "resolution": RESOLUTION,
        "language": LANG,
    }


def trigger(lesson: dict, source_id: str):
    """Fire one generation, --no-wait. Returns a task id, 'RATELIMIT', or None."""
    lesson_id = lesson["lesson_id"]
    desc = build_description(lesson)
    print(f"  → triggering, scoped to source {source_id[:8]}...")
    rc, out, err = _run(
        [
            "generate", "infographic", desc, "-n", NOTEBOOK_ID, "-s", source_id,
            "--orientation", "landscape", "--detail", "standard",
            "--style", "instructional", "--language", CLI_LANG, "--no-wait",
        ],
        timeout=90,
    )
    blob = out + err
    if "RateLimit" in blob or "rate limit" in blob.lower() or "quota" in blob.lower():
        print("    ⛔ NotebookLM RATE LIMIT hit — stopping batch to resume later")
        return "RATELIMIT"
    m = STARTED_RE.search(blob)
    if rc != 0 or not m:
        print(f"    ❌ trigger failed: {(err or out)[:160]}")
        return None
    print(f"    · task {m.group(1)[:8]}… queued")
    return m.group(1)


def poll(task_id: str) -> str:
    rc, out, err = _run(["artifact", "poll", "-n", NOTEBOOK_ID, task_id, "--json"], timeout=90)
    if rc != 0:
        return "error"
    try:
        return json.loads(out).get("status", "error")
    except (json.JSONDecodeError, ValueError):
        return "error"


def download(task_id: str, lesson_id: str) -> dict | None:
    filename = f"{task_id}_infographic_{lesson_id}{LANG_TAG}.png"
    filepath = INFO_DIR / filename
    rc, out, err = _run(
        ["download", "infographic", str(filepath), "-n", NOTEBOOK_ID,
         "--artifact", task_id, "--force"],
        timeout=120,
    )
    if rc != 0 or not filepath.exists() or filepath.stat().st_size < 10_000:
        print(f"    ❌ download failed: {(err or out)[:160]}")
        return None
    # The CLI writes 0600; the container runs as uid 10001 against a host bind
    # mount, so 0600 is unreadable in production — the 2026-07-27 outage.
    filepath.chmod(0o644)
    tmatch = re.search(r"Artifact:\s*(.+?)\s*\(latest", out)
    title = tmatch.group(1).strip() if tmatch else "إنفوجرافيك"
    print(f"    ✓ downloaded {filename} ({filepath.stat().st_size // 1024} KB)")
    return {
        "id": f"{task_id}_infographic",
        "file": f"docs/lesson_assets/infographics/{filename}",
        "title": title,
        "item_count": 0,
        "resolution": RESOLUTION,
        "language": LANG,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="cap triggers this run")
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--lang", default=SOURCE_LANG, choices=sorted(AUDIO_CLI_LANG),
                        help="output language (default: ar) — read at import "
                             "time by _arg_lang(); argparse must still know the flag")
    parser.add_argument("--harvest-only", action="store_true",
                        help="poll + download in-flight tasks; trigger nothing")
    parser.add_argument("--push", action="store_true",
                        help="push the registration commit to main — this "
                             "deploys production. Off by default.")
    args = parser.parse_args()

    INFO_DIR.mkdir(parents=True, exist_ok=True)
    state = _load(STATE_FILE, {})
    errors = _load(ERRORS_FILE, {})
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    lookup = {l["lesson_id"]: i for i, l in enumerate(index["lessons"])}

    def attach(lid: str, asset: dict) -> None:
        pos = lookup.get(lid)
        if pos is None:
            return
        entry = index["lessons"][pos]
        if not isinstance(entry.get("assets"), dict):
            entry["assets"] = {}
        entry["assets"].setdefault("infographics", [])
        entry["assets"]["infographics"].append(asset)

    downloaded = 0
    # keys for the current language only (mirrors gen_podcasts_cron.py's split)
    lang_keys = [k for k in state
                 if (LANG == SOURCE_LANG and "@" not in k)
                 or (LANG != SOURCE_LANG and k.endswith(f"@{LANG}"))]

    print(f"[harvest] {len(lang_keys)} in-flight task(s)")
    for key in lang_keys:
        lid = _split_key(key)
        task_id = state[key]
        status = poll(task_id)
        print(f"[poll] {lid}: {status}")
        if status == "completed":
            asset = download(task_id, lid)
            if asset:
                attach(lid, asset)
                downloaded += 1
                state.pop(key, None)
                errors.pop(key, None)
            # a completed task whose download failed stays in state — retried
            # next run rather than lost, matching the podcast harvest.
        elif status == "error":
            n = errors.get(key, 0) + 1
            if n >= ERROR_BUDGET:
                print(f"  ⛔ {lid}: {n} consecutive poll errors — dropping")
                state.pop(key, None)
                errors.pop(key, None)
            else:
                errors[key] = n
        else:
            errors.pop(key, None)  # any non-error outcome resets the strike count

    _save(STATE_FILE, state)
    _save(ERRORS_FILE, errors)

    still_flight = sum(1 for k in state
                        if (LANG == SOURCE_LANG and "@" not in k)
                        or (LANG != SOURCE_LANG and k.endswith(f"@{LANG}")))

    if args.harvest_only:
        _commit(index, generated=0, recovered=downloaded, failed=[], push=args.push)
        print(f"\n[harvest-only] {downloaded} downloaded · {still_flight} still in flight")
        return

    # ── trigger new ones ──
    rev = reverse_source_map()
    lessons = missing_infographic_lessons()
    if args.limit:
        lessons = lessons[: args.limit]

    triggered, recovered, failed, blocked = 0, 0, [], []
    rate_limited = False

    print(f"\nTriggering infographics for up to {len(lessons)} lessons. Notebook: {NOTEBOOK_ID}")
    for i, lesson in enumerate(lessons, 1):
        lid = lesson["lesson_id"]
        key = _state_key(lid)
        if key in state:
            continue  # already in flight
        print(f"\n[{i}/{len(lessons)}] {lid}")

        recov = existing_asset(lesson)
        if recov:
            print(f"    ♻️ already on disk → registering {recov['id'][:12]}")
            attach(lid, recov)
            recovered += 1
            continue

        src = rev.get(lid)
        if not src:
            print("  ⚠️ no source mapping — blocked")
            blocked.append(lid)
            continue

        try:
            task_id = trigger(lesson, src)
        except subprocess.TimeoutExpired:
            print("    ❌ timeout")
            task_id = None

        if task_id == "RATELIMIT":
            rate_limited = True
            break
        if task_id:
            state[key] = task_id
            triggered += 1
            _save(STATE_FILE, state)  # persist immediately — a crash mid-batch
                                       # must not orphan an already-paid task
        else:
            failed.append(lid)

        if i < len(lessons):
            time.sleep(args.delay)

    if blocked:
        _save(BLOCKED_PATH, blocked)

    print(f"\n✓ Downloaded (harvest): {downloaded}")
    print(f"→ Triggered this run: {triggered} (+{recovered} recovered from disk)")
    print(f"❌ Failed to trigger: {len(failed)} - {failed}")
    print(f"⛔ Blocked (no source): {len(blocked)} - {blocked}")
    if rate_limited:
        print("⛔ Stopped early on NotebookLM rate limit — re-run later to resume.")
    print(f"[summary] {LANG}: in-flight now {triggered + still_flight}")

    _commit(index, generated=triggered, recovered=downloaded + recovered,
            failed=failed, push=args.push)


def _commit(index: dict, generated: int, recovered: int, failed: list, push: bool) -> None:
    total = len(index["lessons"])
    index.setdefault("metadata", {}).setdefault("coverage", {})
    index["metadata"]["coverage"]["infographics"] = (
        f"{sum(1 for l in index['lessons'] if (l.get('assets', {}) or {}).get('infographics'))}/{total}"
    )
    index["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    if generated + recovered == 0:
        print("Nothing new to register — skipping commit.")
        return

    print("\nCommitting...")
    try:
        # NOTE: the PNGs themselves are gitignored (media is rsync'd to the VPS);
        # only the JSON index that references them is tracked.
        add_paths = ["docs/lesson_index.json"]
        if BLOCKED_PATH.exists():
            add_paths.append("scripts/infographics_blocked.json")
        subprocess.run(["git", "add", *add_paths], cwd=BASE_DIR, check=True)
        msg = f"chore(infographics): register {generated + recovered} NotebookLM infographics"
        if failed:
            msg += f" (failed: {len(failed)})"
        subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, check=True)
        if push:
            # Opt-in only — see 2026-08-15's 5a9562d for why an unattended
            # cron pushing to main is a deployment tool wearing a content
            # generator's name.
            subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True)
            print("✅ Committed and pushed.")
        else:
            print("✅ Committed locally. Not pushed — `--push` to deploy, or "
                  "push by hand after review.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
