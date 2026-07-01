#!/usr/bin/env python3
"""
Add video assets to lesson_index.json and create a video index.

8 golden lesson videos (English-language for now, Arabic version to be generated
manually with explicit language prompts in future).
"""

import json
import os
from pathlib import Path
import subprocess

BASE = Path("/home/khalednew/projects/tutor-guardian")
INDEX_PATH = BASE / "docs/lesson_index.json"
VIDEOS_DIR = BASE / "docs/lesson_videos"


def main():
    # Load existing lesson index
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        index = json.load(f)

    # Map video filename -> (age, topic) based on golden lessons order
    video_lessons = {
        '9a511818_Cyberbullying_Pre-Teens_ar.mp4': {
            'age': '10-12', 'topic': 'cyber_digital_citizenship', 'lesson_idx': 2,
            'description': 'Cyberbullying awareness for pre-teens'
        },
        '6ca7b391_Islamic_Parenting_Tweens_ar.mp4': {
            'age': '10-12', 'topic': 'islamic_parenting_identity', 'lesson_idx': 1,
            'description': 'Islamic parenting for tweens'
        },
        'c45e22b4_Digital_Detectives_ar.mp4': {
            'age': '10-12', 'topic': 'cyber_digital_citizenship', 'lesson_idx': 3,
            'description': 'Critical thinking and digital literacy'
        },
        '186dd5fa_Teen_Mental_Health_ar.mp4': {
            'age': '13-15', 'topic': 'medical_mental_health', 'lesson_idx': 1,
            'description': 'Teen mental health awareness'
        },
        '189647f0_Self-Confidence_&_Identity_ar.mp4': {
            'age': '10-12', 'topic': 'islamic_parenting_identity', 'lesson_idx': 4,
            'description': 'Self-confidence and identity building'
        },
        'c2491bd6_Digital_Footprint_ar.mp4': {
            'age': '13-15', 'topic': 'cyber_digital_maturity', 'lesson_idx': 1,
            'description': 'Digital footprint and privacy'
        },
        'f0060e8d_Adolescence_Safely_ar.mp4': {
            'age': '10-12', 'topic': 'medical_puberty_wellbeing', 'lesson_idx': 3,
            'description': 'Safe adolescence - healthy habits'
        },
        '823e565d_Adulthood_Mental_Health_ar.mp4': {
            'age': '16-18', 'topic': 'medical_adult_transition', 'lesson_idx': 1,
            'description': 'Adulthood transition and mental health'
        },
        '82b4b434_Online_Safety_ar.mp4': {
            'age': '10-12', 'topic': 'cyber_digital_citizenship', 'lesson_idx': 2,
            'description': 'Online safety for pre-teens'
        },
    }

    # Add videos to lessons
    video_count = 0
    for fname, info in video_lessons.items():
        fpath = VIDEOS_DIR / fname
        if not fpath.exists():
            continue

        # Find matching lesson
        target_lesson = None
        candidates = [l for l in index['lessons']
                      if l['age_group'] == info['age'] and l['topic_path'] == info['topic']]
        if candidates:
            # Pick by lesson_idx (1-based)
            idx = min(info['lesson_idx'] - 1, len(candidates) - 1)
            target_lesson = candidates[idx]

        if not target_lesson:
            continue

        # Add video to lesson
        if 'videos' not in target_lesson['assets']:
            target_lesson['assets']['videos'] = []

        size_mb = fpath.stat().st_size / 1024 / 1024
        target_lesson['assets']['videos'].append({
            'file': f'docs/lesson_videos/{fname}',
            'size_mb': round(size_mb, 1),
            'language': 'ar',
            'description': info['description'],
            'note': 'Arabic-language version.'
        })
        video_count += 1

    # Update metadata
    index['metadata']['total_videos'] = video_count
    index['metadata']['video_languages'] = ['ar']
    index['metadata']['last_updated'] = '2026-06-12T11:00:00'

    # Save updated index
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Added {video_count} videos to lesson_index.json")

    # Create video-specific index
    video_index = {
        'metadata': {
            'version': '1.0',
            'created_at': '2026-06-12',
            'total_videos': video_count,
            'total_size_mb': round(sum(f.stat().st_size for f in VIDEOS_DIR.glob('*_ar.mp4')) / 1024 / 1024, 1),
            'language': 'ar',
            'note': 'Regenerated batch — Arabic-language.'
        },
        'videos': []
    }

    for fname in sorted(VIDEOS_DIR.glob('*_ar.mp4')):
        video_index['videos'].append({
            'file': f'docs/lesson_videos/{fname.name}',
            'size_mb': round(fname.stat().st_size / 1024 / 1024, 1),
            'created_at': '2026-06-12',
            'duration_estimate': '~5 minutes',
            'format': 'MP4'
        })

    with open(VIDEOS_DIR / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(video_index, f, ensure_ascii=False, indent=2)


    # Create README for videos
    readme = f"""# Lesson Videos — Premium Visual Content

8 AI-generated videos (MP4) for the "Golden Lessons" of Tutor Guardian.

## Current Status

- **Total videos**: {video_count}
- **Total size**: {video_index['metadata']['total_size_mb']} MB
- **Language**: English (en)
- **Format**: MP4 (H.264)
- **Duration**: ~5 minutes each
- **Resolution**: 1280x720 (HD)

## Golden Lessons Covered

| Video File | Topic | Age Group | Description |
|------------|-------|-----------|-------------|
"""
    for fname, info in video_lessons.items():
        if (VIDEOS_DIR / fname).exists():
            readme += f"| {fname} | {info['topic']} | {info['age']} | {info['description']} |\n"

    readme += """
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
"""

    with open(VIDEOS_DIR / 'README.md', 'w', encoding='utf-8') as f:
        f.write(readme)

    print(f"Created {VIDEOS_DIR}/README.md and index.json")


if __name__ == "__main__":
    main()
