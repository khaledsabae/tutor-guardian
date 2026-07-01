#!/usr/bin/env python3
"""Generate remaining aqeedah infographics one by one with per-lesson timeout."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
INFO_DIR = BASE_DIR / "docs" / "lesson_assets" / "infographics"
INDEX_PATH = BASE_DIR / "docs" / "lesson_index.json"
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
NLM = str(BASE_DIR / "notebooklm_env" / "bin" / "notebooklm")
RESOLUTION = "2752x1536"
STARTED_RE = re.compile(r"(?:Started|Task):\s*([0-9a-f-]{36})")

sys.path.insert(0, str(BASE_DIR))
from scripts.infographic_prompts_lib import buildable_targets


def run_cmd(args, timeout=180):
    p = subprocess.run([NLM] + args, cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def generate_one(lesson, index_lookup):
    lid = lesson["lesson_id"]
    src = lesson.get("source_id") or index_lookup.get(lid, {}).get("source_id")
    if not src:
        return None, "no source_id"
    desc = (
        f"أنشئ إنفوجرافيك تربوي عربي أنيق وعملي للأهل (الفئة العمرية {lesson.get('age_group','')}) بعنوان '{lesson['title']}'.\n"
        f"محتوى الإنفوجرافيك يجب أن يغطي النقاط التالية حصراً:\n{lesson['description']}\n\n"
        "المتطلبات: ألوان باستيل هادئة، خط عربي واضح، تخطيط RTL، "
        "بدون أي نص إنجليزي، بدون صور أشخاص حقيقية، بدون فوضى بصرية."
    )
    print(f"\n[{lid}] generating...")
    rc, out, err = run_cmd([
        'generate', 'infographic', desc, '-n', NOTEBOOK_ID, '-s', src,
        '--orientation', 'landscape', '--detail', 'standard', '--style', 'instructional',
        '--language', 'ar_001', '--wait', '--timeout', '360', '--retry', '1',
    ], timeout=420)
    m = STARTED_RE.search(out)
    if rc != 0 or not m:
        return None, (err or out)[:200]
    artifact_id = m.group(1)
    print(f"  ✅ artifact {artifact_id[:8]}")

    filename = f"{artifact_id}_infographic_{lid}.png"
    filepath = INFO_DIR / filename
    rc2, out2, err2 = run_cmd([
        'download', 'infographic', str(filepath), '-n', NOTEBOOK_ID, '--latest'
    ], timeout=120)
    if rc2 != 0 or not filepath.exists() or filepath.stat().st_size < 10_000:
        return None, (err2 or out2)[:200]
    print(f"  ✅ saved {filepath.name} ({filepath.stat().st_size // 1024} KB)")
    return filename, None


def update_index(filename, title):
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    lid = filename.split('_infographic_')[1].replace('.png', '')
    artifact_id = filename.split('_infographic_')[0]
    for lesson in data["lessons"]:
        if lesson.get("lesson_id") == lid:
            if not isinstance(lesson.get("assets"), dict):
                lesson["assets"] = {}
            lesson["assets"].setdefault("infographics", [])
            lesson["assets"]["infographics"].append({
                "id": f"{artifact_id}_infographic",
                "file": f"docs/lesson_assets/infographics/{filename}",
                "title": title,
                "item_count": 0,
                "resolution": RESOLUTION,
            })
            break
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    index_lookup = {l["lesson_id"]: l for l in index["lessons"]}
    ready, _ = buildable_targets()
    already = {p.name.split('_infographic_')[1].replace('.png', '') for p in INFO_DIR.glob('*_infographic_*.png')}
    remaining = [r for r in ready if r['lesson_id'] not in already]
    print(f"Remaining: {len(remaining)}")

    generated, failed = [], []
    for lesson in remaining:
        try:
            fname, error = generate_one(lesson, index_lookup)
            if fname:
                update_index(fname, lesson['title'])
                generated.append(lesson['lesson_id'])
            else:
                print(f"  ❌ {lesson['lesson_id']}: {error}")
                failed.append(lesson['lesson_id'])
        except Exception as e:
            print(f"  ❌ {lesson['lesson_id']} exception: {e}")
            failed.append(lesson['lesson_id'])
        time.sleep(3)

    print(f"\n=== SUMMARY ===")
    print(f"Generated: {len(generated)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()
