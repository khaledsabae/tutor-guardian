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
LANG = "ar_001"
RESOLUTION = "2752x1536"

STARTED_RE = re.compile(r"(?:Started|Task):\s*([0-9a-f-]{36})")
EMPTY_MARKERS = ("No parseable chunks", "Source not found", "Error:")


def _run(args: list[str], timeout: int) -> tuple[int, str, str]:
    p = subprocess.run(
        [NLM, *args], cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout
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
    idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    out = []
    for l in idx["lessons"]:
        if not (l.get("assets", {}) or {}).get("infographics"):
            out.append(
                {
                    "lesson_id": l["lesson_id"],
                    "age_group": l.get("age_group", ""),
                    "topic_path": l.get("topic_path", ""),
                    "title_ar": l.get("title_ar", ""),
                }
            )
    return out


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
    age = lesson.get("age_group", "")
    return (
        f"أنشئ إنفوجرافيك تربوي عربي أنيق وعملي للأهل (الفئة العمرية {age}). "
        "اعتمد حصراً على محتوى المصدر المحدد لهذا الدرس فقط، واستخرج منه عنوان الدرس "
        "وأهم 3-4 نقاط، وقسّمه إلى أقسام مرقّمة بأيقونات بسيطة معبّرة. "
        "المتطلبات: ألوان باستيل هادئة، خط عربي واضح، تخطيط RTL، "
        "بدون أي نص إنجليزي، بدون صور أشخاص حقيقية، بدون فوضى بصرية."
    )


def existing_asset(lesson: dict) -> dict | None:
    """If a PNG for this lesson is already on disk, build its index entry (no API call).

    Lets the batch resume after a rate-limit kill without re-generating (and re-burning
    quota on) infographics that were already produced."""
    lesson_id = lesson["lesson_id"]
    matches = sorted(INFO_DIR.glob(f"*_infographic_{lesson_id}.png"))
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
            "--style", "instructional", "--language", LANG,
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

    filename = f"{artifact_id}_infographic_{lesson_id}.png"
    filepath = INFO_DIR / filename
    rc, out, err = _run(
        ["download", "infographic", str(filepath), "-n", NOTEBOOK_ID, "--latest"],
        timeout=120,
    )
    if rc != 0 or not filepath.exists() or filepath.stat().st_size < 10_000:
        print(f"    ❌ download failed: {(err or out)[:160]}")
        return None

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
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=4.0)
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
