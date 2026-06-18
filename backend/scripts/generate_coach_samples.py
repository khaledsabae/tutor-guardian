"""
Generate ~20 coach-tip samples for offline human review (Gate #1).

Output: JSONL lines with {child_id, name, age_group, domain, text, source}.
Run from repo root or backend/ with:

    CONVERSATIONS_DB=/tmp/coach_samples.db \
    OLLAMA_BASE_URL=http://100.109.163.64:11434 \
    OLLAMA_PRIMARY_MODEL=tg-tutor:v3 \
    OLLAMA_LOCAL_FAST_MODEL=tg-tutor:v3 \
    OLLAMA_TIMEOUT=600 \
    COACH_TIP_ENABLED=true \
    python3 -m scripts.generate_coach_samples
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Set env before importing app modules
os.environ.setdefault("OLLAMA_BASE_URL", "http://100.109.163.64:11434")
os.environ.setdefault("OLLAMA_PRIMARY_MODEL", "tg-tutor:v3")
os.environ.setdefault("OLLAMA_LOCAL_FAST_MODEL", "tg-tutor:v3")
os.environ.setdefault("OLLAMA_TIMEOUT", "600")
os.environ.setdefault("COACH_TIP_ENABLED", "true")

from app.db.init_db import init_db
from app.services import coach_service, conversation_store
from app.db.init_db import get_conn
from app import curriculum_loader

DEVICE_ID = f"sample_{uuid.uuid4().hex[:8]}"
DB_PATH = os.environ.get("CONVERSATIONS_DB", "/tmp/coach_samples.db")

# (name, age_group, gender, recent question, domain tag)
SCENARIOS: list[tuple[str, str, str, str, str]] = [
    ("يوسف", "4-6", "male", "ابني يبقى ساعات طويلة قدام التلفزيون، إزاي أقلّله الشاشات؟", "cyber"),
    ("مريم", "4-6", "female", "بنتي بتعاند في الأكل كل يوم، أعمل إيه؟", "development"),
    ("عمر", "7-9", "male", "ابني سمع ألفاظ من المدرسة، أعمل إيه؟", "islamic_parenting"),
    ("ليلى", "7-9", "female", "بنتي خايفة تنام لوحدها، أعمل إيه؟", "medical"),
    ("آدم", "10-12", "male", "ابني بيستخدم التلفون سراً لحدّ متأخر بالليل، أعمل إيه؟", "cyber"),
    ("سارة", "10-12", "female", "بنتي بتقارن نفسها بصحابها على السوشيال ميديا، أعمل إيه؟", "cyber"),
    ("تالا", "2-3", "female", "بنتي عندها نوبات غضب شديدة في السوق، أعمل إيه؟", "development"),
    ("يحيى", "2-3", "male", "ابني مش بيقبل يصلي معايا وبيجرّي، أعمل إيه؟", "islamic_parenting"),
    ("نور", "13-15", "female", "بنتي بتقولي إنها مش عايزة تروح المدرسة عشان قافلة معايا في الباص، أعمل إيه؟", "development"),
    ("كريم", "13-15", "male", "ابني بيضغط عليه في المذاكرة عشان صحابه بيجيبوا درجات أعلى، أعمل إيه؟", "development"),
    ("سلمى", "0-3", "female", "بنتي صغيرة مش بتنام بالليل وبتصحى كتير، أعمل إيه؟", "medical"),
    ("إبراهيم", "0-3", "male", "ابني سنة ونص ولسه مش بيتكلم، أعمل إيه؟", "medical"),
    ("مازن", "16-18", "male", "ابني مراهق وبيضغط عليه في الجامعة، أعمل إيه؟", "medical"),
    ("هدير", "16-18", "female", "بنتي كبرت وعايزة تسافر لوحدها، أعمل إيه؟", "islamic_parenting"),
    ("يونس", "4-6", "male", "ابني مش بيركز معايا لما بقرا له، أعمل إيه؟", "development"),
    ("رنا", "7-9", "female", "بنتي بتكذب على صحابها عشان تبقى محبوبة، أعمل إيه؟", "islamic_parenting"),
    ("سيف", "10-12", "male", "ابني بيلعب ألعاب عنيفة على التابلت، أعمل إيه؟", "cyber"),
    ("جنا", "2-3", "female", "بنتي مش عايزة تاكل غير بسكوت وبيبسي، أعمل إيه؟", "medical"),
    ("ليان", "13-15", "female", "بنتي بتقعد ساعات على تيك توك، أعمل إيه؟", "cyber"),
    ("زياد", "4-6", "male", "ابني بيضرب أخوه الصغير، أعمل إيه؟", "islamic_parenting"),
]


def setup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.environ["CONVERSATIONS_DB"] = DB_PATH
    init_db()
    # Eager-load curriculum so plain fallback has a varied pool.
    curriculum_loader.load_curriculum()
    # Close default connection so create_session/add_message can open their own.
    get_conn().close()
    children = []
    for name, age_group, gender, question, domain in SCENARIOS:
        sid = conversation_store.create_session(DEVICE_ID, metadata={"child_id": -1})
        conversation_store.add_message(sid, role="user", content=question, domain=domain)
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group, gender) VALUES (?, ?, ?, ?)",
                (DEVICE_ID, name, age_group, gender),
            )
            child_id = cur.lastrowid
            conn.execute(
                "UPDATE chat_sessions SET metadata = ? WHERE id = ?",
                (json.dumps({"child_id": child_id}, ensure_ascii=False), sid),
            )
            conn.commit()
        finally:
            conn.close()
        children.append((child_id, name, age_group, gender))
    return children


async def generate(children):
    samples = []
    used_texts: set[str] = set()
    personal_count = 0
    plain_count = 0
    for i, (child_id, name, age_group, gender) in enumerate(children, 1):
        print(f"[{i}/{len(children)}] generating for {name} ({age_group})...", file=sys.stderr)
        tip = await coach_service.get_proactive_tip(
            DEVICE_ID, child_id, mark_shown=False, used_texts=used_texts
        )
        used_texts.add(tip["text"])
        # Detect personal vs plain by checking warm frame presence
        is_personal = tip["text"].startswith(name)
        if is_personal:
            personal_count += 1
        else:
            plain_count += 1
        record = {
            "child_id": child_id,
            "name": name,
            "age_group": age_group,
            "gender": gender,
            "domain": tip.get("domain"),
            "text": tip["text"],
            "source": tip["source"],
            "personal": is_personal,
        }
        samples.append(record)
        print(json.dumps(record, ensure_ascii=False))

    print(f"\n=== 20 samples: {personal_count} personal, {plain_count} plain ===", file=sys.stderr)
    print(f"=== Coverage: {personal_count / len(children) * 100:.0f}% ===", file=sys.stderr)
    print(f"=== DB path: {DB_PATH} ===", file=sys.stderr)


async def main():
    children = setup()
    await generate(children)


if __name__ == "__main__":
    asyncio.run(main())
