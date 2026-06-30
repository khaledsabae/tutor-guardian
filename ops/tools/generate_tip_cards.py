#!/usr/bin/env python3
"""
generate_tip_cards.py — توليد كروت نصائح يومية مربعة (1080x1080)
مطابقة لتصميم ShareableMomentCard الفاخر والمعتمد في كود تطبيق المربّي الذكي.
يستخدم خط Cairo الرسمي للتطبيق وصورة الخلفية الرسمية share_bg_celebration.webp ومكتبة PIL الأصلية (Raqm) ومكتبة qrcode.
"""
import sys
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

# تحديد المسارات
ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
LOGO_PATH = DOCS_DIR / "marketing" / "launch_graphics" / "facebook_profile_logo.png"
OUTPUT_DIR = DOCS_DIR / "marketing" / "daily_tips_cards"
BG_IMAGE_PATH = ROOT / "mobile" / "assets" / "images" / "generated" / "share_bg_celebration.webp"

# الخطوط الرسمية للتطبيق (Cairo تم تحميله من Google Fonts)
FONT_REGULAR_PATH = str(ROOT / "ops" / "tools" / "fonts" / "Cairo-Regular.ttf")
FONT_BOLD_PATH = str(ROOT / "ops" / "tools" / "fonts" / "Cairo-Bold.ttf")

# الألوان الرسمية للتطبيق (AppTheme & Design Tokens)
COLOR_PRIMARY = (13, 148, 136)       # AppTheme.primary (#0D9488)
COLOR_TEXT_PRIMARY = (30, 41, 59)    # AppTheme.textPrimary (#1E293B)

def strip_emojis(text: str) -> str:
    """تنظيف النص بالكامل من الإيموجي والرموز الخاصة لتفادي ظهور مربعات [ ] في مكتبة الخطوط"""
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"  # الرموز الخاصة خارج النطاق الأساسي
        "\u2600-\u27BF"          # رموز الزينة والقلوب والنجوم والأسهم
        "\u2300-\u23FF"          # الرموز التقنية
        "\u200d"                 # واصل عرض صفر
        "\ufe0f"                 # محدد الاختلافات
        "]+", 
        flags=re.UNICODE
    )
    # إزالة إيموجي الأرقام مثل 1️⃣ 2️⃣
    text = re.sub(r"\d️⃣", "", text)
    text = emoji_pattern.sub("", text)
    return text

def clean_text_for_rendering(text: str) -> str:
    """تنظيف وتجهيز النص للنشر: إزالة الماركداون والرموز التي تسبب مربعات فارغة واستبدالها بنصوص عربية نظيفة"""
    # 1. إزالة كود الماركداون للخط العريض والمائل
    text = text.replace("**", "").replace("*", "").replace("_", "")
    
    # 2. إزالة الإيموجي والرموز غير المعتمدة في الخطوط
    text = strip_emojis(text)
    
    # 3. استبدال الأسهم والواصلات الطويلة والشرطة المائلة برموز متوافقة 100% مع خط Cairo
    text = text.replace("→", " - ").replace("—", " - ").replace("–", " - ")
    text = text.replace("/", " - ").replace("+", " و ")
    
    # 4. استبدال الأقواس الإنجليزية بأقواس اقتباس عربية «» لمنع ظهور الـ []
    text = text.replace("(", "«").replace(")", "»")
    
    # 5. تنظيف أي مسافات متكررة
    text = re.sub(r"\s+", " ", text)
    return text.strip()

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

def create_gradient_overlay(width, height):
    """توليد قناع تدرج لوني أبيض ناعم للشفافية لمنع تداخل النص مع صورة الخلفية"""
    # تدرج يبدأ من 25% تعتيم أبيض في الأعلى وينتهي بـ 82% تعتيم أبيض في الأسفل
    base = Image.new("RGBA", (width, height), (255, 255, 255, 210)) # 82% opacity
    top = Image.new("RGBA", (width, height), (255, 255, 255, 64))   # 25% opacity
    mask = Image.new("L", (width, height))
    mask_data = []
    for y in range(height):
        # تدرج خطي رأسي
        factor = int((y / height) * 255)
        mask_data.extend([factor] * width)
    mask.putdata(mask_data)
    return Image.composite(base, top, mask)

def wrap_arabic_text(text, font, max_width, draw) -> list[str]:
    """تقسيم النص العربي إلى سطور تتناسب مع العرض الأقصى بالبكسل مع قياس العرض الفعلي بطريقة RTL"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        width = draw.textlength(test_line, font=font, direction="rtl")
        
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
        
    return lines

def generate_card(tip: dict, output_path: Path):
    """توليد صورة الكارت بالمقاس 1080x1080 بتصميم ShareableMomentCard الأصيل"""
    width, height = 1080, 1080
    
    # 1. تحميل صورة الخلفية الرسمية للتطبيق أو التراجع لخلفية متدرجة لو لم تكن موجودة
    if BG_IMAGE_PATH.exists():
        img = Image.open(BG_IMAGE_PATH).convert("RGBA")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    else:
        # خلفية متدرجة بديلة
        base_color = (COLOR_PRIMARY[0], COLOR_PRIMARY[1], COLOR_PRIMARY[2], 20)
        img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        top = Image.new("RGBA", (width, height), base_color)
        mask = Image.new("L", (width, height))
        mask.putdata([int((y / height) * 255) for y in range(height) for _ in range(width)])
        img = Image.composite(top, img, mask)
        
    # 2. تطبيق طبقة الشفافية المتدرجة البيضاء (Gradient Overlay) لضمان وضوح النص وقراءته
    overlay = create_gradient_overlay(width, height)
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    # 3. تحميل خط Cairo وتحديد الأحجام
    font_eyebrow = ImageFont.truetype(FONT_BOLD_PATH, 24)
    font_headline = ImageFont.truetype(FONT_BOLD_PATH, 42)
    font_body = ImageFont.truetype(FONT_BOLD_PATH, 32)
    font_footer_title = ImageFont.truetype(FONT_BOLD_PATH, 26)
    font_footer_sub = ImageFont.truetype(FONT_REGULAR_PATH, 18)
    
    # أ) رسم لوجو التطبيق الرسمي المعتمد في الأعلى
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_top_size = 120
        logo_top_resized = logo.resize((logo_top_size, logo_top_size), Image.Resampling.LANCZOS)
        # ممركز في الأعلى
        img.paste(logo_top_resized, (540 - 60, 80), logo_top_resized)
    
    # ب) رسم الـ Eyebrow (نصيحة اليوم) بداخل كبسولة/شيب تركوازي ناعم
    eyebrow_text = "نصيحة اليوم"
    eyebrow_w = draw.textlength(eyebrow_text, font=font_eyebrow, direction="rtl")
    # إحداثيات الكبسولة
    chip_x1 = 540 - (eyebrow_w // 2) - 24
    chip_y1 = 230
    chip_x2 = 540 + (eyebrow_w // 2) + 24
    chip_y2 = 230 + 44
    draw.rounded_rectangle([chip_x1, chip_y1, chip_x2, chip_y2], radius=22, fill=(COLOR_PRIMARY[0], COLOR_PRIMARY[1], COLOR_PRIMARY[2], 30)) # 12% opacity
    draw.text((540, 236), eyebrow_text, font=font_eyebrow, fill="#0D9488", direction="rtl", anchor="mt")
    
    # ج) رسم العنوان (Headline)
    clean_cat = clean_text_for_rendering(tip['category'])
    headline_text = f"وقفة في تربية أبنائنا «{clean_cat}»"
    draw.text((540, 310), headline_text, font=font_headline, fill="#1E293B", direction="rtl", anchor="mt")
    
    # د) رسم نص النصيحة (Body) بعد تنظيفه بالكامل من الإيموجي والماركداون والرموز غير المعتمدة
    clean_body_text = clean_text_for_rendering(tip["text"])
    wrapped_lines = wrap_arabic_text(clean_body_text, font_body, 900, draw)
    line_height = 58
    total_text_h = len(wrapped_lines) * line_height
    # رسم السطور ممركزة عمودياً بين 380 و 670
    start_y = 380 + (290 - total_text_h) // 2
    for i, line in enumerate(wrapped_lines):
        draw.text((540, start_y + (i * line_height)), line, font=font_body, fill="#1E293B", direction="rtl", anchor="mm")
        
    # هـ) تذييل الكارت البصري (Brand Footer)
    # دائرة الأيقونة المتدرجة للعلامة التجارية
    icon_circle_y = 700
    draw.ellipse([540 - 32, icon_circle_y, 540 + 32, icon_circle_y + 64], fill=COLOR_PRIMARY)
    # رسم نجمة خماسية بالخطوط بداخل الدائرة
    star_points = [
        (540, icon_circle_y + 16),
        (544, icon_circle_y + 28),
        (556, icon_circle_y + 28),
        (546, icon_circle_y + 36),
        (550, icon_circle_y + 48),
        (540, icon_circle_y + 40),
        (530, icon_circle_y + 48),
        (534, icon_circle_y + 36),
        (524, icon_circle_y + 28),
        (536, icon_circle_y + 28)
    ]
    draw.polygon(star_points, fill=(255, 255, 255, 255))
    
    # اسم التطبيق والرابط - نستخدم خط Cairo الرسمي
    footer_title = "المربّي - شريكك في رحلة التربية"
    footer_sub = "مجانًا لوجه الله - امسح الكود أو ابحث: «المربّي»"
    draw.text((540, 780), footer_title, font=font_footer_title, fill="#0D9488", direction="rtl", anchor="mt")
    draw.text((540, 820), footer_sub, font=font_footer_sub, fill="#0D9488", direction="rtl", anchor="mt")
    
    # و) رسم كود الـ QR
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data("https://play.google.com/store/apps/details?id=com.alsaba.almorabbi")
    qr.make(fit=True)
    qr_color = "#0D9488"
    qr_img = qr.make_image(fill_color=qr_color, back_color="white").convert("RGBA")
    qr_resized = qr_img.resize((116, 116), Image.Resampling.LANCZOS)
    
    # إطار الكود المستدير الفاخر
    qr_frame_coords = [540 - 58 - 8, 860 - 8, 540 + 58 + 8, 860 + 116 + 8]
    draw.rounded_rectangle(qr_frame_coords, radius=12, fill=(255, 255, 255, 255), outline=(COLOR_PRIMARY[0], COLOR_PRIMARY[1], COLOR_PRIMARY[2], 38), width=1)
    
    # لصق كود الـ QR بداخل الإطار
    img.paste(qr_resized, (540 - 58, 860), qr_resized)
    
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
