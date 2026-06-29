#!/usr/bin/env python3
"""
test_post_infographic.py — سكربت اختبار سريع لنشر أحد الانفوجرافات المائية 
على جميع الحسابات (تليجرام وبفر) فوراً.
"""
import sys
from pathlib import Path

# إضافة مسار الأدوات للاستيراد
sys.path.append(str(Path(__file__).resolve().parent))
from social_media_autoposter import get_buffer_profiles, post_to_buffer, post_to_telegram, BUFFER_TOKEN

# 1. إعدادات الصورة
image_name = "watermarked_3008837d-2d22-4220-81c3-5ce2b47e4e7e_Powering_the_Developing_Brain.jpg"
local_image_path = Path(__file__).resolve().parents[2] / "docs" / "marketing" / "watermarked_infographics" / image_name
public_image_url = f"https://tg-api.alsaba.cloud/docs/marketing/watermarked_infographics/{image_name}"

# 2. نص المنشور المرفق
caption = (
    "🧠 <b>تنمية وتطوير دماغ الطفل في المراحل المبكرة!</b>\n\n"
    "يقدم هذا الانفوجراف التربوي إرشادات هامة وتوجيهات عملية لدعم وتطوير دماغ الطفل وبناء قدراته الذهنية "
    "خلال مرحلة الطفولة المبكرة بناءً على الدراسات العلمية والتربوية المعتمدة.\n\n"
    "حمّل تطبيق «المربّي» مجانًا على Google Play 🤍\n"
    "👉 https://play.google.com/store/apps/details?id=com.alsaba.almorabbi\n\n"
    "#المربّي #تربية_إسلامية #تطوير_الطفل #صحة_الطفل #الأمومة #الأبوة"
)

def main():
    print("🚀 بدء نشر الانفوجراف التجريبي...")
    print(f"🖼️ الصورة المستهدفة: {image_name}")
    print(f"🌐 رابط الصورة لـ Buffer: {public_image_url}")
    
    if not local_image_path.exists():
        print(f"❌ لم يتم العثور على الصورة محلياً في: {local_image_path}")
        return

    # أ) النشر في تليجرام
    print("\n📤 جاري النشر على تليجرام...")
    tg_success = post_to_telegram(caption, local_image_path)
    
    # ب) النشر في Buffer
    buffer_success = False
    if BUFFER_TOKEN:
        print("\n📤 جاري النشر على Buffer (فيسبوك، إنستجرام، تيك توك)...")
        profiles = get_buffer_profiles()
        if profiles:
            buffer_success = post_to_buffer(profiles, caption, public_image_url, now=True)
            
    if tg_success or buffer_success:
        print("\n✨ انتهى اختبار النشر بنجاح!")
    else:
        print("\n⚠️ فشل النشر على جميع المنصات.")

if __name__ == "__main__":
    main()
