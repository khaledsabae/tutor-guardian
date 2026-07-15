#!/usr/bin/env python3
"""Generate Remotion data/reel.json from tutor-guardian path manifest."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
MANIFEST = BASE / "scratch" / "path_video_manifest.json"
OUT = BASE / "remotion-reels" / "data" / "reel.json"
LOGO = BASE / "frontend" / "icons" / "icon-512.png"


def generate(path_id: str | None = None):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mapping = json.loads((BASE / "scratch" / "path_source_mapping_new.json").read_text(encoding="utf-8"))
    title_map = {m["path_id"]: m["title"] for m in mapping}

    # Pick first ready video if no path_id specified
    ready = sorted(
        [pid for pid, info in manifest.items() if info.get("size_bytes", 0) > 5 * 1024 * 1024],
        key=lambda pid: title_map.get(pid, ""),
    )
    if not ready:
        raise SystemExit("No ready videos found in manifest")

    pid = path_id or ready[0]
    title = title_map.get(pid, pid)

    # Build 4 punchy scenes from the title
    scenes = [
        {"text": title.split("،")[0].split(":")[0], "sub": "تعرف على المزيد", "start": 0, "end": 5},
        {"text": "منهج متكامل", "sub": "لكل مرحلة عمرية", "start": 5, "end": 11},
        {"text": "تربية إسلامية", "sub": "من الحمل لـ 18 سنة", "start": 11, "end": 18},
        {"text": "حمّل المربّي مجاناً", "sub": "ابدأ رحلة التربية الصح", "start": 18, "end": 25},
    ]

    data = {
        "title": title,
        "subtitle": "",
        "scenes": scenes,
        "logoPath": "logo.png",
        "screenshotPath": "screenshot.jpg",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} for path_id={pid}")
    return pid, title


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    generate(pid)
