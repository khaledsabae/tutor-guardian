"""
Debug helper: generate 2 coach tips with verbose logging.
"""
import asyncio
import json
import os
import sys
import uuid
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OLLAMA_PRIMARY_MODEL", "tg-tutor:v5")
os.environ.setdefault("OLLAMA_LOCAL_FAST_MODEL", "tg-tutor:v5")
os.environ["COACH_TIP_ENABLED"] = "true"

from app.db.init_db import init_db, get_conn
from app import curriculum_loader as cl
from app.services import coach_service, llm_service
from app.services.ai_gateway import get_gateway

DEVICE_ID = f"debug_{uuid.uuid4().hex[:8]}"

SCENARIOS = [
    ("4-6", "يوسف", "ابني يبقى ساعات طويلة قدام التلفزيون، إزاي أقلّله الشاشات؟", "cyber"),
    ("4-6", "مريم", "بنتي بتعاند في الأكل كل يوم، أعمل إيه؟", "development"),
]


def setup():
    db_path = "/tmp/coach_debug.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["CONVERSATIONS_DB"] = db_path
    init_db()
    cl.load_curriculum()
    conn = get_conn()
    try:
        children = []
        for age_group, name, _, _ in SCENARIOS:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
                (DEVICE_ID, name, age_group),
            )
            children.append((cur.lastrowid, name, age_group))
        for (child_id, name, age_group), (_, _, question, domain) in zip(children, SCENARIOS):
            sid = f"sess_{child_id}"
            conn.execute(
                "INSERT INTO chat_sessions (id, device_id, metadata) VALUES (?, ?, ?)",
                (sid, DEVICE_ID, json.dumps({"child_id": child_id})),
            )
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, domain) VALUES (?, ?, ?, ?)",
                (sid, "user", question, domain),
            )
        conn.commit()
        return children
    finally:
        conn.close()


async def run_one(child_id, name, age_group):
    topic, domain = coach_service._recent_parent_topic(DEVICE_ID, child_id=child_id)
    print(f"\n=== {name} ===")
    print(f"topic={topic} domain={domain}")
    prompt = coach_service._build_coach_prompt(name, age_group, domain or "development", topic or "")
    print(f"prompt:\n{prompt}")
    result = await get_gateway().generate(
        prompt,
        options={"temperature": 0.5, "num_predict": 220},
        tier="local_fast",
        route_reason="debug",
    )
    raw = result.text or ""
    print(f"raw:\n{raw}")
    cleaned = coach_service._clean_generation(llm_service.clean_model_output(raw))
    print(f"cleaned:\n{cleaned}")
    print(f"_is_quality_ok={coach_service._is_quality_ok(cleaned, domain, topic or '')}")
    print(f"_core_matches_topic={coach_service._core_matches_topic(cleaned, topic or '', domain)}")
    tip = await coach_service.get_proactive_tip(DEVICE_ID, child_id, mark_shown=False)
    print(f"FINAL source={tip['source']}\ntext={tip['text']}")


async def main():
    children = setup()
    for child_id, name, age_group in children:
        await run_one(child_id, name, age_group)


if __name__ == "__main__":
    asyncio.run(main())
