# Lesson Videos — Premium Visual Content

8 AI-generated videos (MP4) for the "Golden Lessons" of Tutor Guardian.

## Current Status

- **Total videos**: 9
- **Total size**: 283.3 MB
- **Language**: English (en)
- **Format**: MP4 (H.264)
- **Duration**: ~5 minutes each
- **Resolution**: 1280x720 (HD)

## Golden Lessons Covered

| Video File | Topic | Age Group | Description |
|------------|-------|-----------|-------------|
| 9a511818_Cyberbullying_Pre-Teens.mp4 | cyber_digital_citizenship | 10-12 | Cyberbullying awareness for pre-teens |
| 6ca7b391_Islamic_Parenting_Tweens.mp4 | islamic_parenting_identity | 10-12 | Islamic parenting for tweens |
| c45e22b4_Digital_Detectives.mp4 | cyber_digital_citizenship | 10-12 | Critical thinking and digital literacy |
| 186dd5fa_Teen_Mental_Health.mp4 | medical_mental_health | 13-15 | Teen mental health awareness |
| 189647f0_Self-Confidence_&_Identity.mp4 | islamic_parenting_identity | 10-12 | Self-confidence and identity building |
| c2491bd6_Digital_Footprint.mp4 | cyber_digital_maturity | 13-15 | Digital footprint and privacy |
| f0060e8d_Adolescence_Safely.mp4 | medical_puberty_wellbeing | 10-12 | Safe adolescence - healthy habits |
| 823e565d_Adulthood_Mental_Health.mp4 | medical_adult_transition | 16-18 | Adulthood transition and mental health |
| 82b4b434_Online_Safety.mp4 | cyber_digital_citizenship | 10-12 | Online safety for pre-teens |

## Notes

1. **Language**: Videos are in English because NotebookLM Video Studio generates
   in English by default. Arabic-language versions will be generated in a future
   session with explicit `language=ar` parameters.

2. **Use case**: These videos can be integrated into the Flutter app as:
   - "Premium content" for parents who speak English
   - Educational English content for bilingual children
   - Reference material for teachers/educators

3. **Integration plan**:
   - Add `video_url` field to lesson JSON schema
   - Add `VideoPlayer` widget in `LessonDetailScreen`
   - Stream from CDN or include as bundled assets
   - Support offline caching

## Source

Generated via `notebooklm generate video` on 2026-06-09 from
notebook `94f191e6-cfbc-4655-a0d7-c8f7ad0f2287` (المربي).

See `final_lesson_map_v2.json` for the full lesson-to-asset mapping.
