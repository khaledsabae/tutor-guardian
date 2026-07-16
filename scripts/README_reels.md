# Reels Production Pipeline

Generate 9:16 marketing Reels from tutor-guardian podcast episodes using only ffmpeg.

## What it does

`scripts/podcast_to_reel.py` turns one podcast + its report into a ready-to-post Reel:

- Extracts high-value takeaways from the lesson report (`*_report_lesson_*.md`).
- Picks a 30–60s audio clip (uses transcript if available, otherwise starts near the beginning).
- Burns Arabic subtitles in a large, mobile-first font with an outline for readability.
- Adds a blurred app screenshot as the background.
- Adds watermark: **المربّي الذكي — مجاني 100%**.
- Ends with a CTA card in the last 6 seconds:
  - التطبيق مجاني 100%
  - بلا إعلانات · بلا اشتراكات
  - رابط التحميل في البايو 👇
- Outputs 1080×1920 30fps MP4 in `docs/marketing/reels_output/`.

## Requirements

- ffmpeg + ffprobe (system packages)
- Python 3.10+
- A lesson report markdown with quoted key takeaways.
- Optional: a transcript JSON/SRT in `docs/marketing/transcripts/` for tighter subtitle timing.

## Usage

```bash
cd /home/khalednew/projects/tutor-guardian
python3 scripts/podcast_to_reel.py \
  --input docs/lesson_0-3_islamic_parenting_fitrah_01_podcast.mp3 \
  --report docs/lesson_assets/reports/6ef69d84-6b9a-475e-8b1e-47f643fadd24_report_lesson_0-3_islamic_parenting_fitrah_01.md \
  --title "صوت القرآن والأذان" \
  --duration 42
```

Options:

- `--input` / `-i`: source MP3 (required)
- `--report` / `-r`: report markdown (required)
- `--title` / `-t`: Reel title used in filename (required)
- `--output` / `-o`: output directory (default `docs/marketing/reels_output/`)
- `--duration` / `-d`: target duration in seconds (default 42)
- `--screenshot`: custom background image path (default: onboarding screenshot)

## Batch example

```bash
python3 scripts/podcast_to_reel.py \
  --input docs/lesson_2-3_islamic_tantrums_04_podcast.mp3 \
  --report docs/lesson_assets/reports/e23fb592-f18c-4b7d-bf5a-06f296a69c31_report_lesson_2-3_islamic_tantrums_04.md \
  --title "نوبات الغضب برفق" --duration 42
```

## Output samples

Five sample reels covering different ages/topics are already generated in `docs/marketing/reels_output/`:

- `reel_صوت_القرآن_والأذان.mp4`
- `reel_التدريب_على_المرحاض.mp4`
- `reel_نوبات_الغضب_برفق.mp4`
- `reel_كم_وقت_شاشة_يناسب_طفلك.mp4`
- `reel_الصلاة_محبّةً لا إلزاماً.mp4`

## Monetization rule

All generated content must include the free-app message. The product is **مجاني 100% لله**, so every Reel ends with:

> التطبيق مجاني 100% — بلا إعلانات · بلا اشتراكات — رابط التحميل في البايو

## Notes

- Render time is ~1.5–2 minutes per Reel on this machine because of complex ffmpeg drawtext on 1080×1920.
- For daily production at scale, run the script in the background or on a stronger runner.
- No OpenAI/Whisper dependency is required unless you want word-level transcript timing.
- The script never writes API tokens; any future API key stays in the project's `.env`.
