#!/usr/bin/env python3
"""
watermark_infographics.py — سكربت لإضافة لوجو التطبيق تلقائياً وعلامة مائية على الانفوجرافات
المولدة مسبقاً وتصديرها لمجلد التسويق لتكون جاهزة للنشر.
"""
import sys
from pathlib import Path
from PIL import Image

# تحديد المسارات
ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = ROOT / "docs" / "marketing" / "launch_graphics" / "facebook_profile_logo.png"
INFOGRAPHICS_DIR = ROOT / "docs" / "lesson_assets" / "infographics"
OUTPUT_DIR = ROOT / "docs" / "marketing" / "watermarked_infographics"

def watermark_image(image_path: Path, logo_path: Path, output_path: Path):
    """إضافة اللوجو كعلامة مائية في الزاوية السفلية اليمنى للصورة"""
    try:
        # 1. فتح الصورة الأصلية واللوجو
        img = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")
        
        # 2. تحديد مقاس اللوجو (مثلاً 10% من عرض الصورة الأصلية)
        target_width = int(img.width * 0.10)
        # الحفاظ على نسبة العرض إلى الارتفاع
        aspect_ratio = logo.height / logo.width
        target_height = int(target_width * aspect_ratio)
        
        # التأكد من حجم مناسب (مثلاً لا يقل عن 80x80 ولا يزيد عن 150x150)
        target_width = max(80, min(target_width, 150))
        target_height = max(80, min(target_height, 150))
        
        logo_resized = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 3. حساب موقع اللوجو (الزاوية السفلية اليمنى مع هامش 20 بكسل)
        margin = 20
        position_x = img.width - target_width - margin
        position_y = img.height - target_height - margin
        
        # 4. دمج اللوجو مع الصورة باستخدام قناع الشفافية (Alpha Mask)
        img.paste(logo_resized, (position_x, position_y), logo_resized)
        
        # 5. حفظ الصورة النهائية بصيغة PNG أو JPEG (التحويل لـ RGB إذا حفظنا كـ JPEG)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(output_path, "JPEG", quality=90)
        print(f"  ✅ تم بنجاح: {output_path.name}")
        return True
    except Exception as e:
        print(f"  ❌ فشل معالجة {image_path.name}: {e}")
        return False

def main():
    if not LOGO_PATH.exists():
        print(f"❌ لم يتم العثور على لوجو التطبيق في: {LOGO_PATH}")
        sys.exit(1)
        
    if not INFOGRAPHICS_DIR.exists():
        print(f"❌ لم يتم العثور على مجلد الانفوجرافات في: {INFOGRAPHICS_DIR}")
        sys.exit(1)
        
    print("🎨 بدء إضافة العلامة المائية على الانفوجرافات...")
    # البحث عن كل ملفات الصور في مجلد الانفوجرافات
    image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    image_files = []
    for ext in image_extensions:
        image_files.extend(list(INFOGRAPHICS_DIR.glob(ext)))
        
    if not image_files:
        print("⚠️ لم يتم العثور على أي صور في مجلد الانفوجرافات.")
        return
        
    print(f"🔍 تم العثور على {len(image_files)} صورة. جاري المعالجة والتصدير...")
    
    success_count = 0
    for img_path in image_files:
        # تحديد اسم ومسار المخرجات
        out_name = f"watermarked_{img_path.stem}.jpg"
        out_path = OUTPUT_DIR / out_name
        
        if watermark_image(img_path, LOGO_PATH, out_path):
            success_count += 1
            
    print(f"\n✨ انتهى العمل بنجاح! تم معالجة وتصدير {success_count} صورة إلى:\n📂 {OUTPUT_DIR.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
