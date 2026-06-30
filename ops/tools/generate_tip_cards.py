#!/usr/bin/env python3
"""
generate_tip_cards.py — سكربت لتوليد كروت نصائح يومية مربعة (1024x1024) 
بهوية التطبيق البصرية المعتمدة (تصميم Glassmorphism راقي مع تدرج لوني وتنسيق عربي احترافي)
لكل نصيحة من الـ 30 نصيحة، لتكون جاهزة للنشر على إنستجرام وتيك توك وفيسبوك.
"""
import sys
import re
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# تحديد المسارات
ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
LOGO_PATH = DOCS_DIR / "marketing" / "launch_graphics" / "facebook_profile_logo.png"
OUTPUT_DIR = DOCS_DIR / "marketing" / "daily_tips_cards"

# الخطوط المستخدمة
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"

# التدرجات اللونية الفاخرة لكل فئة عمرية
GRADIENTS = {
    "رضّع": ("#014A4E", "#002022"),       # تركوازي داكن روحي للأعمار الأولى
    "دارج": ("#025257", "#002326"),       # تركوازي متوسط
    "مدرسي": ("#036167", "#002629"),      # أزرق مخضر
    "مراهق": ("#003336", "#001214"),      # عميق جداً للمراهقين
    "عابر": ("#014A4E", "#002022")       # تركوازي التطبيق الافتراضي
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
                    "text": text
                })
                
    return tips

def create_linear_gradient(width, height, color1, color2):
    """توليد صورة تدرج لوني عمودي عميق"""
    base = Image.new("RGBA", (width, height), color1)
    top = Image.new("RGBA", (width, height), color2)
    mask = Image.new("L", (width, height))
    mask_data = []
    for y in range(height):
        factor = int((y / height) * 255)
        mask_data.extend([factor] * width)
    mask.putdata(mask_data)
    return Image.composite(top, base, mask)

def wrap_arabic_text(text, font, max_width, draw) -> list[str]:
    """تقسيم النص العربي إلى سطور تتناسب مع العرض الأقصى بالبكسل مع الحفاظ على الاتجاه الصحيح"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        reshaped = arabic_reshaper.reshape(test_line)
        display = get_display(reshaped)
        width = draw.textlength(display, font=font)
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
                
    if current_line:
        lines.append(" ".join(current_line))
        
    # إعادة تشكيل وعكس كل سطر بشكل مستقل ليظهر بشكل صحيح
    final_lines = []
    for line in lines:
        reshaped = arabic_reshaper.reshape(line)
        display = get_display(reshaped)
        final_lines.append(display)
        
    return final_lines

def generate_card(tip: dict, output_path: Path):
    """توليد صورة الكارت بالمقاس 1024x1024 بالهوية البصرية الاحترافية"""
    width, height = 1024, 1024
    
    # 1. تحديد درجات الألوان المناسبة للفئة العمرية
    cat_key = "عابر"
    for k in GRADIENTS.keys():
        if k in tip["category"]:
            cat_key = k
            break
    color1, color2 = GRADIENTS[cat_key]
    
    # 2. إنشاء الخلفية المتدرجة
    img = create_linear_gradient(width, height, color1, color2)
    draw = ImageDraw.Draw(img)
    
    # 3. رسم كارت الـ Glassmorphism في المنتصف
    # مستطيل شبه شفاف بحواف مستديرة (تأثير الزجاج الفاخر)
    card_coords = [80, 100, width - 80, height - 120]
    # تعبئة بيضاء شفافة بتركيز 12%
    draw.rounded_rectangle(card_coords, radius=35, fill=(255, 255, 255, 30), outline=(255, 255, 255, 60), width=2)
    
    # 4. تحميل الخطوط وتجهيز النصوص
    font_title = ImageFont.truetype(FONT_BOLD_PATH, 38)
    font_body = ImageFont.truetype(FONT_REGULAR_PATH, 32)
    font_footer = ImageFont.truetype(FONT_BOLD_PATH, 28)
    font_sub_footer = ImageFont.truetype(FONT_REGULAR_PATH, 20)
    
    # أ) عنوان الفئة والترتيب
    title_text = f"💡 نصيحة اليوم التربوية ({tip['category']})"
    reshaped_title = get_display(arabic_reshaper.reshape(title_text))
    
    # رسم خط فاصل ناعم تحت العنوان
    draw.line([160, 210, width - 160, 210], fill=(255, 255, 255, 45), width=1)
    
    # ب) نص النصيحة (تقسيم ورسم في منتصف كارت الزجاج)
    # أقصى عرض للنص هو 750 بكسل
    wrapped_lines = wrap_arabic_text(tip["text"], font_body, 740, draw)
    
    # 5. حساب مواقع الرسم
    # رسم العنوان بالأعلى
    title_w = draw.textlength(reshaped_title, font=font_title)
    draw.text(((width - title_w) // 2, 140), reshaped_title, font=font_title, fill="#E6FAF8")
    
    # رسم النص في المنتصف العمودي تماماً
    line_height = 55
    total_text_h = len(wrapped_lines) * line_height
    # بداية الرسم العمودي
    start_y = 250 + (480 - total_text_h) // 2
    
    for i, line in enumerate(wrapped_lines):
        line_w = draw.textlength(line, font=font_body)
        draw.text(((width - line_w) // 2, start_y + (i * line_height)), line, font=font_body, fill="#FFFFFF")
        
    # ج) تذييل الكارت (اللوجو ورابط المتجر)
    # تحميل اللوجو المعتمد ودمجه بالأسفل
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = 90
        logo_resized = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        # موضع اللوجو (الركن السفلي الأيسر داخل كارت الزجاج)
        img.paste(logo_resized, (120, height - 230), logo_resized)
        
    # اسم التطبيق والرابط بجانب اللوجو
    app_title = get_display(arabic_reshaper.reshape("تطبيق المربّي الذكي"))
    app_link = get_display(arabic_reshaper.reshape("حمّله الآن مجاناً على Google Play"))
    
    # رسم اسم التطبيق بجانب اللوجو
    draw.text((230, height - 215), app_title, font=font_footer, fill="#2EC4B6")
    draw.text((230, height - 175), app_link, font=font_sub_footer, fill="#B5E2DF")
    
    # 6. حفظ الصورة النهائية بصيغة PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")

def main():
    print("🎨 بدء توليد كروت النصائح اليومية المربعة...")
    tips = parse_tips()
    
    success_count = 0
    for tip in tips:
        out_name = f"tip_{tip['id']}.png"
        out_path = OUTPUT_DIR / out_name
        
        try:
            generate_card(tip, out_path)
            success_count += 1
            print(f"  ✅ تم توليد: {out_name}")
        except Exception as e:
            print(f"  ❌ فشل توليد كارت النصيحة {tip['id']}: {e}")
            
    print(f"\n✨ اكتمل العمل! تم توليد {success_count} كارت نصيحة بنجاح في:\n📂 {OUTPUT_DIR.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
