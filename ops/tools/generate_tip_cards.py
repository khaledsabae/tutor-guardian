#!/usr/bin/env python3
"""
generate_tip_cards.py — توليد كروت نصائح يومية مربعة (1080x1080)
مطابقة لتصميم ShareableMomentCard الفاخر والمعتمد في كود تطبيق المربّي الذكي.
يستخدم خط Cairo الرسمي للتطبيق وصورة الخلفية الرسمية share_bg_celebration.webp ومكتبة PIL الأصلية (Raqm) ومكتبة qrcode.
"""
import sys
import re
from pathlib import Path

# الرسم وحده يحتاج Pillow وqrcode — parse_tips() لا، فيبقى الملف قابلًا للاستيراد
# والاختبار بدونهما. الغياب يُبلَّغ عنه بصوت عالٍ في main() لا هنا.
_MISSING_LIBS = []
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None
    _MISSING_LIBS.append("Pillow (مع Raqm)")
try:
    import qrcode
except ImportError:
    qrcode = None
    _MISSING_LIBS.append("qrcode")

# تحديد المسارات
ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
TIPS_FILE = DOCS_DIR / "marketing" / "02_content_arsenal.md"
LOGO_PATH = DOCS_DIR / "marketing" / "launch_graphics" / "facebook_profile_logo.png"
OUTPUT_DIR = DOCS_DIR / "marketing" / "daily_tips_cards"
BG_IMAGE_PATH = ROOT / "mobile" / "assets" / "images" / "generated" / "share_bg_celebration.webp"

# الخطوط الرسمية للتطبيق (Cairo تم تحميله من Google Fonts)
FONT_REGULAR_PATH = str(ROOT / "ops" / "tools" / "fonts" / "Cairo-Regular.ttf")
FONT_BOLD_PATH = str(ROOT / "ops" / "tools" / "fonts" / "Cairo-Bold.ttf")

# الألوان الرسمية للتطبيق (AppTheme & Design Tokens)
COLOR_PRIMARY = (13, 148, 136)       # AppTheme.primary (#0D9488)
COLOR_TEXT_PRIMARY = (30, 41, 59)    # AppTheme.textPrimary (#1E293B)

# النص كله (العنوان والمتن) يبقى بين خطّي الإطار الداخليين في صورة الخلفية
# (x≈108 و≈970 على مقاس 1080) — 820 يترك هامشًا ~20px من كل جهة.
TEXT_MAX_WIDTH = 820
# بين العنوان (ينتهي y≈370) وأيقونة التذييل (y=700) يتّسع المتن لخمسة سطور لا أكثر.
BODY_MAX_LINES = 5

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
    # الصيغة المركّبة ﷺ (U+FDFA) غير موجودة في Cairo فتخرج مربعًا فارغًا في الكارت (النصيحة 20)
    # — نكتبها كاملة، وهي نفس المعنى.
    text = text.replace("ﷺ", "صلى الله عليه وسلم")
    
    # 3. استبدال الأسهم والواصلات الطويلة والشرطة المائلة برموز متوافقة 100% مع خط Cairo
    text = text.replace("→", " - ").replace("—", " - ").replace("–", " - ")
    text = text.replace("/", " - ").replace("+", " و ")
    
    # 4. استبدال الأقواس الإنجليزية بأقواس اقتباس عربية «» لمنع ظهور الـ []
    #    وإن كان ما بين القوسين مقتبسًا أصلًا («…») نكتفي باقتباسه، وإلا خرج الاقتباس مزدوجًا ««…»»
    text = re.sub(r"\(\s*(«[^«»]*»)\s*\)", r"\1", text)
    text = text.replace("(", "«").replace(")", "»")
    
    # 5. تنظيف أي مسافات متكررة
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_tips(tips_file: Path | None = None) -> list[dict]:
    """يقرأ قسم «## أ) بنك كروت النصائح» فقط من 02_content_arsenal.md ويستخرج النصائح وتصنيفاتها.

    نفس منطق social_media_autoposter.parse_tips (in_tips_bank): الملف فيه أكثر من
    قائمة مرقّمة — النصائح ثم سكربتات الريلز (قسم «ب»، البنود 1–12). عدّ كل سطر
    مرقّم كان يكتب سكربتات «ب» فوق كروت tip_1…tip_12: ظهر على tip_11.png «ليه
    التطبيق ده مجاني؟…» (ملاحظة تسويقية داخلية) بينما النص المنشور معه نصيحة لعب
    10 دقائق. كرت tip_N لازم يحمل نصيحة N نفسها التي ينشرها الـautoposter.

    تكرار رقم نصيحة خطأ فادح (ValueError) لا تجاوز صامت: كرتان لرقم واحد يعني
    إحداهما تُكتب فوق الأخرى.
    """
    tips_file = tips_file or TIPS_FILE
    if not tips_file.exists():
        print(f"❌ لم يتم العثور على ملف النصائح في: {tips_file}")
        sys.exit(1)

    tips = []
    first_seen_at: dict[int, int] = {}  # رقم النصيحة -> رقم السطر الذي ظهر فيه أول مرة
    current_category = "عابر للأعمار"
    in_tips_bank = False

    with open(tips_file, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            # عنوان قسم: لا نلتقط إلا بنك النصائح (أ)
            if line_str.startswith("## "):
                in_tips_bank = line_str.startswith("## أ)")
                continue
            if not in_tips_bank:
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
                if tip_id in first_seen_at:
                    raise ValueError(
                        f"❌ رقم النصيحة {tip_id} مكرر في {tips_file.name} "
                        f"(السطران {first_seen_at[tip_id]} و{lineno}) — كرتان لرقم واحد "
                        f"تكتب إحداهما فوق الأخرى"
                    )
                first_seen_at[tip_id] = lineno
                tips.append({
                    "id": tip_id,
                    "category": current_category,
                    "text": text
                })

    if not tips:
        raise ValueError(
            f"❌ لا نصائح تحت عنوان «## أ)» في {tips_file.name} — "
            f"هل تغيّر عنوان القسم؟ (autoposter يعتمد عليه أيضًا)"
        )
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

def blend_rounded_rect(img, box, radius, fill=None, outline=None, width=1):
    """يرسم مستطيلًا مستدير الزوايا بلون RGBA شفاف *دمجًا حقيقيًا* فوق الصورة (في مكانها).

    الرسم المباشر `ImageDraw.rounded_rectangle(fill=(r, g, b, 30))` على صورة RGBA يستبدل
    البكسل بقيمته (ألفا 30) ولا يدمجه — فيخرج PNG فيه بكسلات شبه شفافة، وأي منصّة
    تُسقط قناة ألفا (تحويل لـJPEG مثلًا) تعرض الكبسولة تركوازية صلبة، فيختفي النص
    التركوازي فوقها. هنا الشكل يُرسم على طبقة شفافة ثم تُدمج بـalpha_composite،
    فتبقى كل بكسلات الصورة معتمة (ألفا 255).
    """
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    img.alpha_composite(layer)

def fit_bold_font(draw, text, start_size, max_width, min_size=30):
    """أكبر خط Cairo عريض (≤ start_size) يتّسع فيه `text` داخل max_width — وإلا ValueError لا تجاوز للإطار"""
    for size in range(start_size, min_size - 1, -1):
        font = ImageFont.truetype(FONT_BOLD_PATH, size)
        if draw.textlength(text, font=font, direction="rtl") <= max_width:
            return font
    raise ValueError(f"النص لا يتّسع في {max_width}px حتى بخط {min_size}: {text}")

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
    
    # ب) رسم الـ Eyebrow (نصيحة اليوم) بداخل كبسولة/شيب.
    # الكبسولة فاتحة (أبيض ~92%) بحدّ تركوازي خفيف ونص تركوازي، وتُدمج بـalpha_composite
    # (blend_rounded_rect) لا بالرسم المباشر. لونها فاتح عمدًا: الخلفية هنا تركوازية-رمادية
    # متوسطة، وتينت تركوازي 12% فوقها يترك النص التركوازي بتباين ~1.7:1 (شبه مختفٍ).
    eyebrow_text = "نصيحة اليوم"
    eyebrow_w = draw.textlength(eyebrow_text, font=font_eyebrow, direction="rtl")
    # إحداثيات الكبسولة
    chip_x1 = 540 - (eyebrow_w // 2) - 24
    chip_y1 = 230
    chip_x2 = 540 + (eyebrow_w // 2) + 24
    chip_y2 = 230 + 44
    blend_rounded_rect(
        img, [chip_x1, chip_y1, chip_x2, chip_y2], radius=22,
        fill=(255, 255, 255, 235),
        outline=(COLOR_PRIMARY[0], COLOR_PRIMARY[1], COLOR_PRIMARY[2], 110), width=2,
    )
    draw.text((540, (chip_y1 + chip_y2) // 2), eyebrow_text, font=font_eyebrow, fill="#0D9488", direction="rtl", anchor="mm")

    # ج) رسم العنوان (Headline) — يصغر الخط تلقائيًا لو العنوان أعرض من الإطار
    # (ما قبل المراهقة «10-12» كان 901px على خط 42 فيعبر خطّ الإطار الجانبي)
    clean_cat = clean_text_for_rendering(tip['category'])
    headline_text = f"وقفة في تربية أبنائنا «{clean_cat}»"
    font_headline = fit_bold_font(draw, headline_text, 42, TEXT_MAX_WIDTH)
    draw.text((540, 310), headline_text, font=font_headline, fill="#1E293B", direction="rtl", anchor="mt")

    # د) رسم نص النصيحة (Body) بعد تنظيفه بالكامل من الإيموجي والماركداون والرموز غير المعتمدة
    clean_body_text = clean_text_for_rendering(tip["text"])
    wrapped_lines = wrap_arabic_text(clean_body_text, font_body, TEXT_MAX_WIDTH, draw)
    if len(wrapped_lines) > BODY_MAX_LINES:
        raise ValueError(
            f"نص النصيحة {tip['id']} يلتف على {len(wrapped_lines)} سطور (الأقصى {BODY_MAX_LINES}) — "
            f"سيتداخل مع التذييل؛ اختصره"
        )
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
    draw.rounded_rectangle(qr_frame_coords, radius=12, fill=(255, 255, 255, 255))
    # حدّ الإطار تركوازي 15% — يُدمج (لا يُرسم مباشرة) لنفس سبب كبسولة الـEyebrow
    blend_rounded_rect(img, qr_frame_coords, radius=12, outline=(COLOR_PRIMARY[0], COLOR_PRIMARY[1], COLOR_PRIMARY[2], 38), width=1)

    # لصق كود الـ QR بداخل الإطار
    img.paste(qr_resized, (540 - 58, 860), qr_resized)

    # 6. حفظ الصورة النهائية بصيغة PNG — معتمة بالكامل وبلا قناة ألفا: أي بكسل شبه شفاف
    # هنا يعني أن شكلًا شفافًا رُسم مباشرة (استخدم blend_rounded_rect)، وكان هذا سبب
    # اختفاء نص الكبسولة على المنصّات التي تُسقط الألفا — نرفضه بدل أن نحفظه.
    lowest_alpha = img.getchannel("A").getextrema()[0]
    if lowest_alpha != 255:
        raise RuntimeError(
            f"الكارت يحوي بكسلات شبه شفافة (أدنى ألفا {lowest_alpha}) — ارسم الأشكال الشفافة بـblend_rounded_rect"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output_path, "PNG")

def main():
    if _MISSING_LIBS:
        sys.exit(f"❌ توليد الكروت يحتاج مكتبات غير مثبّتة: {' و'.join(_MISSING_LIBS)}")
    print("🎨 بدء توليد كروت النصائح اليومية المربعة...")
    tips = parse_tips()

    success_count = 0
    failed_ids = []
    for tip in tips:
        out_name = f"tip_{tip['id']}.png"
        out_path = OUTPUT_DIR / out_name

        try:
            generate_card(tip, out_path)
            success_count += 1
            print(f"  ✅ تم توليد: {out_name}")
        except Exception as e:
            failed_ids.append(tip["id"])
            print(f"  ❌ فشل توليد كارت النصيحة {tip['id']}: {e}")

    print(f"\n✨ اكتمل العمل! تم توليد {success_count} كارت نصيحة بنجاح في:\n📂 {OUTPUT_DIR.relative_to(ROOT)}")
    if failed_ids:
        # كرت قديم باقٍ على القرص = كرت لا يطابق نص النصيحة المنشورة معه؛ فلا نخرج بـ0
        sys.exit(f"❌ فشل توليد {len(failed_ids)} كارت (أرقام: {failed_ids}) — الكروت القديمة لهذه الأرقام ما زالت على القرص")

if __name__ == "__main__":
    main()
