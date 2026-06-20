import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

BASE = "/home/khalednew/projects/tutor-guardian/docs/marketing/screenshots"
RAW = f"{BASE}/raw"
OUT = f"{BASE}/final"
os.makedirs(OUT, exist_ok=True)

HEAD_FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
SUB_FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

TEAL = (13, 148, 136)        # #0D9488
TEAL_DEEP = (15, 118, 110)
CREAM = (250, 247, 242)
WHITE = (255, 255, 255)
AMBER = (245, 158, 11)

# (raw file, headline, subline, band color)
SHOTS = [
    ("02_onboarding_welcome.png", "مجاني بالكامل، لوجه الله", "بلا إعلانات ولا اشتراكات", AMBER),
    ("01_home.png", "منهج تربية متكامل لطفلك", "من الحمل حتى ١٨ سنة", TEAL),
    ("03_paths.png", "مسارات من ٢٨ يومًا", "لكل مرحلة عمرية ومجال", TEAL),
    ("04_journey.png", "سجّل رحلة نموّ طفلك", "محطات إيمانية وتحدّيات", (126, 87, 194)),
    ("05_features.png", "أكثر من مجرد قراءة", "دروس + بودكاست + فيديو", TEAL),
    ("06_assistant.png", "مساعد تربوي يجيبك فورًا", "عن تحدّياتك اليومية", TEAL),
    ("07_quran.png", "ركن القرآن والأذكار", "لطفلك ولك", (46, 125, 50)),
]


def ar(t):
    # PIL + Noto Naskh renders reshaped (connected) forms correctly LTR;
    # applying bidi here would wrongly reverse it.
    return arabic_reshaper.reshape(t)


def center_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


BAND_H = 360
W = 1080
H = 2400

hf = ImageFont.truetype(HEAD_FONT, 70)
sf = ImageFont.truetype(SUB_FONT, 42)

made = 0
for i, (fn, head, sub, band) in enumerate(SHOTS, 1):
    src = f"{RAW}/{fn}"
    if not os.path.exists(src):
        print("MISSING", fn)
        continue
    shot = Image.open(src).convert("RGB")
    # crop the status bar (~78px) off the top
    shot = shot.crop((0, 100, shot.width, shot.height))
    # scale shot to fit width W and the remaining height
    target_h = H - BAND_H
    sw, sh = shot.size
    scale = W / sw
    nh = int(sh * scale)
    shot = shot.resize((W, nh))
    if nh > target_h:
        shot = shot.crop((0, 0, W, target_h))
        nh = target_h

    canvas = Image.new("RGB", (W, H), CREAM)
    # header band
    band_img = Image.new("RGB", (W, BAND_H), band)
    canvas.paste(band_img, (0, 0))
    d = ImageDraw.Draw(canvas)
    center_text(d, W / 2, 120, ar(head), hf, WHITE)
    center_text(d, W / 2, 235, ar(sub), sf, (255, 255, 255))
    # paste screenshot below band, centered vertically in remaining space
    y = BAND_H + max(0, (target_h - nh) // 2)
    canvas.paste(shot, (0, y))
    out = f"{OUT}/{i:02d}_{fn}"
    canvas.save(out, quality=92)
    made += 1
    print(f"  ✓ {os.path.basename(out)}  ({head})")

print(f"\ncomposed {made} final screenshots in {OUT}/")
