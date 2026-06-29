#!/usr/bin/env python3
"""
social_media_autoposter.py — أداة النشر التلقائي لمنشورات التسويق والتربية اليومية.
تقرأ النصائح من docs/marketing/02_content_arsenal.md وتنشرها مع الصورة الملائمة
عبر Buffer API (لإنستجرام، فيسبوك، إكس، تيك توك) وTelegram Bot API (للقنوات).
"""
import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
import requests

# تحديد مسارات المشروع
ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
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

# تصنيف الصور لكل فئة عمرية
IMAGE_MAPPING = {
    "رضّع (0-3)": "social_announce_square.webp",
    "دارج (2-3)": "social_announce_square.webp",
    "ما قبل المدرسة (4-6)": "social_feature_ai.webp",
    "مدرسي (7-9)": "social_feature_ai.webp",
    "ما قبل المراهقة (10-12)": "social_feature_journey.webp",
    "مراهق (13-18)": "social_feature_journey.webp",
    "عابر للأعمار": "social_announce_square.webp"
}

def parse_tips() -> list[dict]:
    """يقرأ ويحلل ملف 02_content_arsenal.md لاستخراج النصائح وتصنيفاتها"""
    tips_file = DOCS_DIR / "marketing" / "02_content_arsenal.md"
    if not tips_file.exists():
        print(f"❌ لم يتم العثور على ملف النصائح في: {tips_file}")
        sys.exit(1)

    tips = []
    current_category = "عابر للأعمار"
    
    with open(tips_file, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            
            # استخراج التصنيف العمري
            cat_match = re.match(r"^\*\*(.*?)\*\*", line_str)
            if cat_match:
                current_category = cat_match.group(1).strip().rstrip(":")
                continue
                
            # استخراج رقم النصيحة ومحتواها
            tip_match = re.match(r"^(\d+)\.\s*(.*)", line_str)
            if tip_match:
                tip_id = int(tip_match.group(1))
                text = tip_match.group(2).strip()
                tips.append({
                    "id": tip_id,
                    "category": current_category,
                    "text": text,
                    "image": IMAGE_MAPPING.get(current_category, "social_announce_square.webp")
                })
                
    return tips

def load_state() -> dict:
    """تحميل حالة النشر السابقة"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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

def post_to_telegram(text: str, image_path: Path) -> bool:
    """إرسال النصيحة مع الصورة مباشرة إلى قناة التليجرام"""
    if not TG_BOT_TOKEN or not TG_CHANNEL_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN أو TELEGRAM_CHANNEL_ID غير مضبوط في ملف .env")
        return False
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    
    # إرسال الصورة كملف محلي
    if not image_path.exists():
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
    parser.add_argument("--post-id", type=int, help="نشر نصيحة محددة برقمها")
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
        # النشر التلقائي للخطوة التالية
        next_id = state["last_posted_id"] + 1
        if next_id > len(tips):
            # إعادة تشغيل الدورة من البداية
            next_id = 1
        
        matching = [t for t in tips if t["id"] == next_id]
        if not matching:
            print("❌ لا توجد نصائح متبقية للنشر.")
            return
        target_tip = matching[0]

    # تحضير النص والصورة
    post_text = format_post_text(target_tip)
    local_image_path = DOCS_DIR / "marketing" / "launch_graphics" / target_tip["image"]
    public_image_url = f"{API_BASE_URL}/docs/marketing/launch_graphics/{target_tip['image']}"

    print(f"📋 النصيحة المستهدفة: #{target_tip['id']} ({target_tip['category']})")
    print(f"🖼️ الصورة المحلية: {local_image_path.name}")
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
        state["last_posted_id"] = target_tip["id"]
        state["history"].append({
            "tip_id": target_tip["id"],
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "telegram": tg_success,
            "buffer": buffer_success
        })
        save_state(state)
        print(f"💾 تم حفظ الحالة بنجاح. آخر نصيحة تم نشرها: #{target_tip['id']}")

if __name__ == "__main__":
    main()
