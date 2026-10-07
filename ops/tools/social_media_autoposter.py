#!/usr/bin/env python3
"""
social_media_autoposter.py — أداة النشر التلقائي لمنشورات التسويق والتربية اليومية.
تقرأ النصائح من knowledge_base/curriculum/daily_tips/*.json مع صورة عامة ملائمة
عبر Buffer API (لإنستجرام، فيسبوك، إكس، تيك توك) وTelegram Bot API (للقنوات).
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
import requests

# تحديد مسارات المشروع
ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
TIPS_DIR = ROOT / "knowledge_base" / "curriculum" / "daily_tips"
STATE_FILE = ROOT / "ops" / "tools" / "autoposter_state.json"

# تحميل ملف البيئة .env يدوياً لتجنب الاعتماديات الخارجية
def load_dotenv():
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

load_dotenv()

# قراءة إعدادات البيئة
BUFFER_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
API_BASE_URL = os.environ.get("API_BASE_URL", "https://tg-api.alsaba.cloud").strip()

# Curated age groups reuse only generic campaign graphics. Legacy tip_N cards
# contain obsolete text and must never be paired with curated tips.
AGE_CATEGORIES = {
    "prenatal-1": "الحمل وحتى عام", "0-3": "رضّع (0-3)",
    "2-3": "دارج (2-3)", "4-6": "ما قبل المدرسة (4-6)",
    "7-9": "مدرسي (7-9)", "10-12": "ما قبل المراهقة (10-12)",
    "13-15": "مراهق (13-15)", "16-18": "مراهق (16-18)",
}
IMAGE_MAPPING = {
    "prenatal-1": "social_announce_square.webp",
    "0-3": "social_announce_square.webp", "2-3": "social_announce_square.webp",
    "4-6": "social_feature_ai.webp", "7-9": "social_feature_ai.webp",
    "10-12": "social_feature_journey.webp", "13-15": "social_feature_journey.webp",
    "16-18": "social_feature_journey.webp",
}

def parse_tips() -> list[dict]:
    """Load curated Arabic text verbatim, ordered by stable source ID."""
    if not TIPS_DIR.is_dir():
        raise FileNotFoundError(f"Curated daily tips directory missing: {TIPS_DIR}")
    tips = []
    seen = set()
    for path in sorted(TIPS_DIR.glob("*.json")):
        tip = json.loads(path.read_text(encoding="utf-8"))
        tip_id = tip.get("id")
        if not isinstance(tip_id, str) or not tip_id.startswith("tip_") or tip_id in seen:
            raise ValueError(f"Invalid or duplicate curated tip ID in {path}")
        if not isinstance(tip.get("text"), str) or not tip["text"].strip():
            raise ValueError(f"Missing curated tip text in {path}")
        seen.add(tip_id)
        # Absent is_published is the original curated schema; explicit false is
        # a draft and must not be published by this consumer.
        if tip.get("is_published") is False:
            continue
        age = tip["age_group"]
        image = IMAGE_MAPPING.get(age)
        if image and not (DOCS_DIR / "marketing" / "launch_graphics" / image).is_file():
            image = None
        tips.append({"id": tip_id, "category": AGE_CATEGORIES.get(age, age),
                     "text": tip["text"], "image": image})
    return sorted(tips, key=lambda tip: tip["id"])

def select_next_tip(tips: list[dict], state: dict) -> dict | None:
    """Keep legacy state intact; cycle by curated ID, never by numeric offset."""
    if not tips:
        return None
    cursor = state.get("curated_last_posted_id")
    for index, tip in enumerate(tips):
        if tip["id"] == cursor:
            return tips[(index + 1) % len(tips)]
    # Migration (or a removed cursor): do not reset onto an already posted
    # curated ID. Integer history IDs belong to the separate legacy namespace.
    posted = {entry.get("tip_id") for entry in state.get("history", [])}
    return next((tip for tip in tips if tip["id"] not in posted), None)

def record_posted_tip(state: dict, tip: dict, telegram: bool, buffer: bool):
    """Append success without overwriting the legacy cursor or any old history."""
    state["curated_last_posted_id"] = tip["id"]
    state.setdefault("history", []).append({
        "tip_id": tip["id"], "posted_at": datetime.now(timezone.utc).isoformat(),
        "telegram": telegram, "buffer": buffer,
    })

def load_state() -> dict:
    """تحميل حالة النشر السابقة"""
    if STATE_FILE.exists():
        # Corrupt/unreadable state must stop the run, never erase posting history.
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_posted_id": 0, "history": []}

def save_state(state: dict):
    """حفظ حالة النشر الحالية"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_buffer_profiles() -> list[dict]:
    """جلب حسابات السوشيال ميديا المربوطة بـ Buffer عبر GraphQL API"""
    if not BUFFER_TOKEN:
        print("⚠️ BUFFER_ACCESS_TOKEN غير مضبوط في ملف .env")
        return []
    
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. جلب معرف المنظمة (Organization ID)
    org_query = {"query": "query { account { organizations { id } } }"}
    try:
        resp = requests.post(url, headers=headers, json=org_query, timeout=15)
        resp.raise_for_status()
        res_data = resp.json()
        orgs = res_data.get("data", {}).get("account", {}).get("organizations", [])
        if not orgs:
            print("❌ لم يتم العثور على أي منظمة (Organization) في حسابك على Buffer.")
            return []
        org_id = orgs[0]["id"]
    except Exception as e:
        print(f"❌ فشل جلب منظمة Buffer: {e}")
        return []
        
    # 2. جلب الحسابات (Channels) الخاصة بالمنظمة
    channels_query = {
        "query": """
        query GetChannels($orgId: OrganizationId!) {
          channels(input: { organizationId: $orgId }) {
            id
            service
            name
          }
        }
        """,
        "variables": {"orgId": org_id}
    }
    try:
        resp = requests.post(url, headers=headers, json=channels_query, timeout=15)
        resp.raise_for_status()
        res_data = resp.json()
        channels = res_data.get("data", {}).get("channels", [])
        return [{"id": c["id"], "service": c["service"], "name": c["name"]} for c in channels]
    except Exception as e:
        print(f"❌ فشل جلب حسابات Buffer: {e}")
        return []

def post_to_buffer(profiles: list[dict], text: str, image_url: str, now: bool) -> bool:
    """نشر المحتوى إلى الحسابات المحددة عبر Buffer GraphQL API"""
    if not BUFFER_TOKEN or not profiles:
        return False
    
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # سنقوم بإنشاء منشور لكل حساب على حدة لأن طفرة GraphQL createPost تتعامل مع قناة واحدة في كل مرة
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """
    
    success_count = 0
    for p in profiles:
        pid = p["id"]
        service = p["service"]
        post_input = {
            "text": text,
            "channelId": pid,
            "schedulingType": "automatic",
            "mode": "shareNow" if now else "addToQueue"
        }
        
        # إضافة الميتاداتا الخاصة بالمنصات لتفادي أخطاء النوع
        if service == "instagram":
            post_input["metadata"] = {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True
                }
            }
        elif service == "facebook":
            post_input["metadata"] = {
                "facebook": {
                    "type": "post"
                }
            }
            
        if image_url:
            post_input["assets"] = [{
                "image": {
                    "url": image_url
                }
            }]
            
        payload = {
            "query": mutation,
            "variables": {"input": post_input}
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            res_data = resp.json()
            errors = res_data.get("errors")
            if errors:
                print(f"❌ خطأ GraphQL أثناء النشر للحساب {pid} ({service}): {errors[0]['message']}")
                continue
                
            create_post_res = res_data.get("data", {}).get("createPost", {})
            if "message" in create_post_res:
                print(f"❌ فشل النشر للحساب {pid} ({service}): {create_post_res['message']}")
            else:
                success_count += 1
        except Exception as e:
            print(f"❌ فشل الإرسال إلى Buffer للحساب {pid} ({service}): {e}")
            
    if success_count > 0:
        print(f"✅ تم النشر بنجاح لـ {success_count} حسابات من أصل {len(profiles)} عبر Buffer.")
        return True
    return False

def post_to_telegram(text: str, image_path: Path | None) -> bool:
    """إرسال النصيحة مع الصورة مباشرة إلى قناة التليجرام"""
    if not TG_BOT_TOKEN or not TG_CHANNEL_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN أو TELEGRAM_CHANNEL_ID غير مضبوط في ملف .env")
        return False
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    
    # إرسال الصورة كملف محلي
    if image_path is None or not image_path.exists():
        print(f"❌ لم يتم العثور على ملف الصورة محلياً في: {image_path}")
        return False
        
    try:
        with open(image_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {
                "chat_id": TG_CHANNEL_ID,
                "caption": text,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, files=files, data=data, timeout=15)
            resp.raise_for_status()
            print("✅ تم النشر في قناة التليجرام بنجاح.")
            return True
    except Exception as e:
        print(f"❌ فشل النشر في تليجرام: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"تفاصيل الخطأ: {e.response.text}")
        return False

def format_post_text(tip: dict) -> str:
    """تنسيق نص المنشور لإضافة الهاشتاجات ورابط المتجر"""
    hashtags = "#المربّي #تربية_إسلامية #تربية_الأطفال #الأبوة_والأمومة"
    store_link = "حمّل «المربّي» مجانًا على Google Play 🤍\n👉 https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
    
    formatted = (
        f"💡 <b>نصيحة اليوم التربوية ({tip['category']}):</b>\n\n"
        f"{tip['text']}\n\n"
        f"{store_link}\n\n"
        f"{hashtags}"
    )
    return formatted

def main():
    parser = argparse.ArgumentParser(description="أداة النشر التلقائي لتطبيق المربي الذكي")
    parser.add_argument("--list-profiles", action="store_true", help="عرض الحسابات المربوطة بـ Buffer")
    parser.add_argument("--post-next", action="store_true", help="نشر النصيحة التالية في الطابور فوراً")
    parser.add_argument("--post-id", help="نشر نصيحة بمعرّفها الثابت، مثل tip_7-9_001")
    parser.add_argument("--test-post", action="store_true", help="إجراء منشور تجريبي للتحقق من الاتصال")
    parser.add_argument("--dry-run", action="store_true", help="محاكاة النشر دون إرسال البيانات الفعلي للأجهزة")
    parser.add_argument("--queue", action="store_true", help="إضافة المنشور لطابور الجدولة في Buffer بدلاً من النشر الفوري")
    args = parser.parse_args()

    # 1. جلب حسابات Buffer وعرضها
    if args.list_profiles:
        print("🔍 جلب حسابات Buffer المربوطة...")
        profiles = get_buffer_profiles()
        if not profiles:
            print("❌ لم يتم العثور على أي حسابات مربوطة بـ Buffer. تأكد من إعداد التوكن وربط الحسابات.")
            return
        print(f"🟢 تم العثور على {len(profiles)} حسابات:")
        for p in profiles:
            print(f"  • ID: {p['id']} | الخدمة: {p['service']} | الاسم: {p.get('name', p.get('formatted_username'))}")
        return

    # 2. فك شفرة النصائح
    tips = parse_tips()
    state = load_state()

    # تحديد أي نصيحة سنقوم بنشرها
    target_tip = None
    if args.post_id:
        # البحث عن نصيحة محددة بالرقم
        matching = [t for t in tips if t["id"] == args.post_id]
        if not matching:
            print(f"❌ لم يتم العثور على نصيحة بالرقم {args.post_id}")
            return
        target_tip = matching[0]
    elif args.test_post:
        target_tip = {
            "id": 0,
            "category": "تجربة اتصال",
            "text": "هذا منشور تجريبي للتأكد من ربط أتمتة تسويق تطبيق «المربّي الذكي» بنجاح! 🤍",
            "image": "social_announce_square.webp"
        }
    else:
        target_tip = select_next_tip(tips, state)
        if target_tip is None:
            print("❌ لا توجد نصائح متبقية للنشر.")
            return

    # تحضير النص والصورة
    post_text = format_post_text(target_tip)
    
    # Only generic launch graphics are eligible, never legacy text cards.
    image_name = target_tip["image"]
    local_image_path = None
    public_image_url = ""
    if image_name:
        candidate = DOCS_DIR / "marketing" / "launch_graphics" / image_name
        if candidate.is_file():
            local_image_path = candidate
            public_image_url = f"{API_BASE_URL}/docs/marketing/launch_graphics/{image_name}"

    print(f"📋 النصيحة المستهدفة: #{target_tip['id']} ({target_tip['category']})")
    print(f"🖼️ الصورة المحلية: {local_image_path.name if local_image_path else 'بدون صورة'}")
    print(f"🌐 الصورة العامة لـ Buffer: {public_image_url}")

    if args.dry_run:
        print("\n⚙️ [وضع المحاكاة - Dry Run] لن يتم إرسال أي منشورات.")
        print(f"--- النص المنشور ---\n{post_text}\n--------------------")
        return

    # تنفيذ النشر
    success = False
    
    # أ) النشر في تليجرام
    tg_success = post_to_telegram(post_text, local_image_path)
    
    # ب) النشر في Buffer
    buffer_success = False
    if BUFFER_TOKEN:
        print("🔗 جلب معرفات الحسابات النشطة في Buffer...")
        profiles = get_buffer_profiles()
        if profiles:
            buffer_success = post_to_buffer(profiles, post_text, public_image_url, now=not args.queue)
        else:
            print("⚠️ لا توجد حسابات نشطة في Buffer للنشر إليها.")
            
    success = tg_success or buffer_success

    # حفظ الحالة في حال نجاح العملية
    if success and not args.test_post:
        record_posted_tip(state, target_tip, tg_success, buffer_success)
        save_state(state)
        print(f"💾 تم حفظ الحالة بنجاح. آخر نصيحة تم نشرها: #{target_tip['id']}")

if __name__ == "__main__":
    main()
