#!/usr/bin/env python3
"""
Generate missing infographic assets for lessons using NotebookLM.

Per lesson:
  1. resolve source_id from source_to_lesson.json (reverse map)
  2. ask the source for its title + key axes (grounds the infographic)
  3. generate an Arabic infographic via NotebookLM, grounded in that content
  4. wait for the artifact, download the PNG
  5. record it in docs/lesson_index.json
Finally: one git commit + push for the whole batch.

Lessons whose source is missing/empty are skipped and recorded in
scripts/infographics_blocked.json (same gap that blocks their reports).

Usage:
  ./notebooklm_env/bin/python scripts/generate_missing_infographics.py [--limit N] [--delay S]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
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
from scripts.infographic_prompts_lib import buildable_targets

STARTED_RE = re.compile(r"(?:Started|Task):\s*([0-9a-f-]{36})")
EMPTY_MARKERS = ("No parseable chunks", "Source not found", "Error:")


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


def ask_source_axes(source_id: str) -> str | None:
    """Return short grounding text (title + key axes), or None if source is empty/broken."""
    rc, out, _ = _run(
        [
            "ask", "-n", NOTEBOOK_ID, "-s", source_id,
            "اذكر عنوان الدرس و4 محاور رئيسية فقط في نقاط قصيرة جداً للأهل، بدون مقدمات.",
        ],
        timeout=120,
    )
    if rc != 0 or not out or any(m in out for m in EMPTY_MARKERS):
        return None
    # strip CLI chrome (Matched:/Answer:/Conversation: lines)
    lines = []
    for line in out.splitlines():
        if line.startswith(("Matched:", "Conversation:", "New conversation:")):
            continue
        if line.strip() == "Answer:":
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    return text or None


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

    Lets the batch resume after a rate-limit kill without re-generating (and re-burning
    quota on) infographics that were already produced."""
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


def generate_one(lesson: dict, source_id: str) -> dict | None:
    lesson_id = lesson["lesson_id"]
    # CRITICAL: -s scopes generation to THIS lesson's source only. NotebookLM reads the
    # source directly, so no separate axes-extraction roundtrip is needed (it was fragile
    # and would skip valid lessons). Without -s, generation draws from the whole notebook
    # → duplicate/overlapping infographics (the rejected first attempt).
    print(f"  → generating, scoped to source {source_id[:8]}...")
    desc = build_description(lesson)
    rc, out, err = _run(
        [
            "generate", "infographic", desc, "-n", NOTEBOOK_ID, "-s", source_id,
            "--orientation", "landscape", "--detail", "standard",
            "--style", "instructional", "--language", CLI_LANG,
            "--wait", "--timeout", "320", "--retry", "2",
        ],
        timeout=420,
    )
    m = STARTED_RE.search(out)
    if rc != 0 or "ready" not in out.lower() or not m:
        blob = (err or "") + (out or "")
        if "RateLimit" in blob or "rate limit" in blob.lower():
            print("    ⛔ NotebookLM RATE LIMIT hit — stopping batch to resume later")
            return "RATELIMIT"
        print(f"    ❌ generate failed: {(err or out)[:160]}")
        return None
    artifact_id = m.group(1)
    print(f"    ✅ generated artifact {artifact_id[:8]}")

    filename = f"{artifact_id}_infographic_{lesson_id}{LANG_TAG}.png"
    filepath = INFO_DIR / filename
    rc, out, err = _run(
        ["download", "infographic", str(filepath), "-n", NOTEBOOK_ID, "--latest"],
        timeout=120,
    )
    if rc != 0 or not filepath.exists() or filepath.stat().st_size < 10_000:
        print(f"    ❌ download failed: {(err or out)[:160]}")
        return None
    # The CLI writes 0600; the container runs as uid 10001 against a host bind
    # mount, so 0600 is unreadable in production — the 2026-07-27 outage. The
    # podcast and video generators already do this; this one did not.
    filepath.chmod(0o644)

    # NotebookLM auto-title, e.g. "Artifact: <title> (latest of N)"
    tmatch = re.search(r"Artifact:\s*(.+?)\s*\(latest", out)
    title = tmatch.group(1).strip() if tmatch else (lesson["title_ar"] or "إنفوجرافيك")
    print(f"    ✅ saved {filename} ({filepath.stat().st_size // 1024} KB)")
    return {
        "id": f"{artifact_id}_infographic",
        "file": f"docs/lesson_assets/infographics/{filename}",
        "title": title,
        "item_count": 0,
        "resolution": RESOLUTION,
        "language": LANG,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=4.0)
    # Read at import time by _arg_lang() (LANG/CLI_LANG/LANG_TAG are module
    # constants), but argparse must still know the flag or it rejects the run.
    parser.add_argument("--lang", default=SOURCE_LANG, choices=sorted(AUDIO_CLI_LANG),
                        help="output language (default: ar)")
    args = parser.parse_args()

    INFO_DIR.mkdir(parents=True, exist_ok=True)
    rev = reverse_source_map()
    lessons = missing_infographic_lessons()
    if args.limit:
        lessons = lessons[: args.limit]

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    lookup = {l["lesson_id"]: i for i, l in enumerate(index["lessons"])}

    print(f"Generating infographics for {len(lessons)} lessons. Notebook: {NOTEBOOK_ID}")
    generated, recovered, failed, blocked = 0, 0, [], []
    rate_limited = False

    def attach(lid: str, asset: dict) -> None:
        pos = lookup.get(lid)
        if pos is None:
            return
        entry = index["lessons"][pos]
        if not isinstance(entry.get("assets"), dict):
            entry["assets"] = {}
        entry["assets"].setdefault("infographics", [])
        entry["assets"]["infographics"].append(asset)

    for i, lesson in enumerate(lessons, 1):
        lid = lesson["lesson_id"]
        print(f"\n[{i}/{len(lessons)}] {lid}")

        # Resume: if a PNG already exists on disk (from a prior killed run), just register it.
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
            asset = generate_one(lesson, src)
        except subprocess.TimeoutExpired:
            print("    ❌ timeout")
            asset = None
        except Exception as e:  # noqa: BLE001
            print(f"    ❌ exception: {e}")
            asset = None

        if asset == "RATELIMIT":
            rate_limited = True
            failed.append(lid)
            break
        if asset:
            attach(lid, asset)
            generated += 1
        else:
            failed.append(lid)

        if i < len(lessons):
            time.sleep(args.delay)

    total = len(index["lessons"])
    index.setdefault("metadata", {}).setdefault("coverage", {})
    index["metadata"]["coverage"]["infographics"] = (
        f"{sum(1 for l in index['lessons'] if (l.get('assets', {}) or {}).get('infographics'))}/{total}"
    )
    index["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    if blocked:
        BLOCKED_PATH.write_text(json.dumps(blocked, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Generated {generated} infographics (+{recovered} recovered from disk)")
    print(f"❌ Failed: {len(failed)} - {failed}")
    print(f"⛔ Blocked (no source): {len(blocked)} - {blocked}")
    if rate_limited:
        print("⛔ Stopped early on NotebookLM rate limit — re-run later to resume.")

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
        subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True)
        print("✅ Committed and pushed.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
