import os
from PIL import Image, ImageOps

output_dir = '/home/khalednew/projects/tutor-guardian/play_assets'
os.makedirs(output_dir, exist_ok=True)

# 1. Copy App Icon
icon_src = '/home/khalednew/projects/tutor-guardian/frontend/icons/icon-512.png'
icon_dest = os.path.join(output_dir, 'app_icon.png')
try:
    img = Image.open(icon_src)
    img.save(icon_dest)
    print(f"Saved app icon to {icon_dest}")
except Exception as e:
    print(f"Error saving icon: {e}")

# 2. Process Feature Graphic (1024x500)
# We will scale the 1024x1024 raw feature graphic to 500x500 (preserving the full beautiful illustration),
# and pad the left and right sides to make it 1024x500.
# We will sample the background color from the left/right edges of the raw graphic.
fg_src = '/home/khalednew/.gemini/antigravity/brain/97d12e33-a11d-467b-8bdd-c413977425d9/feature_graphic_raw_1781172945743.png'
fg_dest = os.path.join(output_dir, 'feature_graphic.png')
try:
    img = Image.open(fg_src)
    # Resize to 500x500
    img_resized = img.resize((500, 500), Image.Resampling.LANCZOS)
    # Create background canvas 1024x500
    # Let's get the background color from top-left corner
    bg_color = img.getpixel((10, 10))
    bg = Image.new('RGBA', (1024, 500), bg_color)
    # Paste the resized image in the center
    offset = ((1024 - 500) // 2, 0)
    bg.paste(img_resized, offset)
    bg.save(fg_dest)
    print(f"Saved feature graphic to {fg_dest}")
except Exception as e:
    print(f"Error processing feature graphic: {e}")

# 3. Process Screenshots (1080x1920)
# We will paste the 1024x1024 screenshots into the center of a 1080x1920 canvas.
# The background color will match the screenshot's corner.
screenshots = [
    ('/home/khalednew/.gemini/antigravity/brain/97d12e33-a11d-467b-8bdd-c413977425d9/screenshot_1_raw_1781172970319.png', 'screenshot_1.png'),
    ('/home/khalednew/.gemini/antigravity/brain/97d12e33-a11d-467b-8bdd-c413977425d9/screenshot_2_raw_1781173002588.png', 'screenshot_2.png')
]

for src_path, dest_name in screenshots:
    dest_path = os.path.join(output_dir, dest_name)
    try:
        img = Image.open(src_path)
        bg_color = img.getpixel((10, 10))
        # Create vertical canvas
        bg = Image.new('RGBA', (1080, 1920), bg_color)
        # We can also slightly scale the screenshot so the phone fits nicely
        # The raw image is 1024x1024. Let's scale it to 1080x1080.
        img_resized = img.resize((1080, 1080), Image.Resampling.LANCZOS)
        # Paste in the center of the vertical canvas
        offset = (0, (1920 - 1080) // 2)
        bg.paste(img_resized, offset)
        bg.save(dest_path)
        print(f"Saved screenshot to {dest_path}")
    except Exception as e:
        print(f"Error processing screenshot {dest_name}: {e}")
