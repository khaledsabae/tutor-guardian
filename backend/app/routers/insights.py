from datetime import datetime, timezone, timedelta
import json
import logging
from fastapi import APIRouter, HTTPException, Query, Request
from app.db.init_db import get_conn
from app.services.ai_gateway import get_gateway

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])

def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="توثيق الجهاز مطلوب.")
    return device_id

@router.get("/parenting")
async def get_parenting_insights(
    request: Request,
    child_id: int = Query(..., ge=1)
):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        # 1. Verify child ownership
        child = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id)
        ).fetchone()
        if not child:
            raise HTTPException(status_code=404, detail="الطفل غير موجود.")
            
        # 2. Get routine events summary (last 7 days)
        since = (datetime.now(timezone.utc) - timedelta(days=6)).strftime("%Y-%m-%d")
        events = conn.execute(
            """
            SELECT e.*
            FROM routine_events e
            JOIN child_daily_routines r ON e.routine_id = r.id
            WHERE r.device_id = ? AND r.child_id = ? AND r.routine_date >= ?
            """,
            (device_id, child_id, since),
        ).fetchall()
        
        total_sleep = 0
        feed_count = 0
        feed_amount = 0
        diaper_count = 0
        for e in events:
            et = e["event_type"]
            if et == "sleep":
                try:
                    start = datetime.fromisoformat(e["started_at"])
                    end = datetime.fromisoformat(e["ended_at"]) if e["ended_at"] else start
                    total_sleep += int((end - start).total_seconds() / 60)
                except Exception:
                    pass
            elif et == "feed":
                feed_count += 1
                if e["amount_ml"] is not None:
                    feed_amount += e["amount_ml"]
            elif et == "diaper":
                diaper_count += 1

        # 3. Get recent parent questions from chat history
        chats = conn.execute(
            """
            SELECT m.content FROM chat_messages m
            JOIN chat_sessions s ON m.session_id = s.id
            WHERE s.device_id = ? AND m.role = 'user'
            ORDER BY m.id DESC LIMIT 5
            """,
            (device_id,)
        ).fetchall()
        chat_texts = [c["content"] for c in chats]

        # 4. Build AI insights prompt
        prompt = f"""
أنت مساعد وخبير تربوي ذكي للأطفال في العالم العربي الإسلامي.
بناءً على البيانات التالية للطفل/الطفلة {child["name"]} (العمر: {child["age_group"]}):

1. ملخص الروتين الأسبوعي للطفل (آخر 7 أيام):
- إجمالي دقائق النوم: {total_sleep} دقيقة
- عدد الرضعات/التغذية: {feed_count} رضعات
- إجمالي كمية الحليب: {feed_amount} مل
- عدد مرات تغيير الحفاظ: {diaper_count} مرات

2. المواضيع والأسئلة الأخيرة التي طرحها الوالدان في المحادثة مع المساعد التربوي الذكي:
{chr(10).join("- " + t for t in chat_texts) if chat_texts else "لا توجد أسئلة سابقة"}

قم بتحليل هذه البيانات وتقديم 3 إلى 4 توصيات تربوية ذكية وعملية مخصصة وموجهة للأهل باللغة العربية الفصحى البسيطة والدافئة.
قم بصياغة الاستجابة بتنسيق JSON حصراً كقائمة من الكائنات بالبنية التالية:
[
  {{
    "title": "عنوان قصير وجذاب ومحدد للبطاقة (مثلاً: تنظيم أوقات النوم)",
    "description": "نصيحة عملية ملموسة وداعمة مبنية مباشرة على الأرقام والبيانات المذكورة أعلاه",
    "category": "النوم" أو "التغذية" أو "السلوك" أو "أخرى",
    "type": "positive" (إذا كانت البيانات ممتازة) أو "tip" (نصيحة عامة) أو "warning" (إذا كان هناك خلل مثل قلة النوم)
  }}
]
أجب بتنسيق JSON فقط دون أي كلام أو هوامش إضافية قبل أو بعد الـ JSON. لا تكتب علامات الفتح والإغلاق الخاصة بـ markdown.
"""
        fallback_insights = [
            {
                "title": "تنظيم أوقات النوم",
                "description": "يُنصح بالحفاظ على جدول نوم منتظم للطفل لمساعدته على الاسترخاء بشكل أفضل في الليل.",
                "category": "النوم",
                "type": "tip"
            },
            {
                "title": "متابعة التغذية والرضاعة",
                "description": "تأكد من تقديم الرضعات أو الوجبات بانتظام ومتابعة كميات الحليب المناسبة لنمو الطفل.",
                "category": "التغذية",
                "type": "positive"
            },
            {
                "title": "ترطيب وحماية الطفل",
                "description": "متابعة تكرار تغيير الحفاظ بشكل دوري يحمي بشرة طفلك ويحافظ على راحته ونشاطه.",
                "category": "أخرى",
                "type": "tip"
            }
        ]

        try:
            result = await get_gateway().generate(
                prompt, tier="local_fast", route_reason="parenting_insights"
            )
            text = result.text.strip()
            if text.startswith("```json"):
                text = text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
            elif text.startswith("```"):
                text = text.split("```", 1)[1].rsplit("```", 1)[0].strip()
            insights = json.loads(text)
            if not isinstance(insights, list) or len(insights) == 0:
                insights = fallback_insights
        except Exception as e:
            logger.warning("Failed to generate parenting insights: %s", e)
            insights = fallback_insights

        return {"insights": insights}
    finally:
        conn.close()
