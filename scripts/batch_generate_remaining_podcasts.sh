#!/usr/bin/env bash
set -euo pipefail

export HOME=/home/khalednew
REPO=/home/khalednew/projects/tutor-guardian
NOTEBOOK_ID=94f191e6-cfbc-4655-a0d7-c8f7ad0f2287
LOG=/tmp/batch_podcasts_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

cd "$REPO"

echo "=== Batch podcast generation started at $(date) ==="

# Source 440183bc: already generated, artifact 7d78d463-87bb-4e67-9333-9aa773259ae5
SOURCE_ID="440183bc-479c-49c1-bb07-fe35fa62295f"
ARTIFACT_ID="7d78d463-87bb-4e67-9333-9aa773259ae5"
LESSONS=(
  lesson_16-18_medical_adult_transition_02
  lesson_4-6_islamic_parenting_bond_01
  lesson_7-9_islamic_parenting_worship_02
)
echo "Downloading pre-generated artifact $ARTIFACT_ID for source $SOURCE_ID..."
./notebooklm_env/bin/notebooklm download audio -n "$NOTEBOOK_ID" --artifact "$ARTIFACT_ID" --force docs/source_${SOURCE_ID}_podcast.mp3 --json
for lesson in "${LESSONS[@]}"; do
  cp docs/source_${SOURCE_ID}_podcast.mp3 docs/${lesson}_podcast.mp3
  echo "Copied to $lesson"
done

# Remaining sources to generate
SOURCES=(
  "55fb8fb3-2eed-4eb2-9940-0a1e07d3e951"
  "bc41f39f-97ae-4af2-80dd-b070907a80e4"
  "dab0fff1-8180-4a3f-99ae-6791b243d690"
  "f7e6f02d-39fb-4888-ae4a-9e0644e75f5e"
)

# Map source to lessons
declare -A LESSON_MAP
LESSON_MAP[55fb8fb3-2eed-4eb2-9940-0a1e07d3e951]="lesson_13-15_medical_mental_health_02 lesson_16-18_medical_adult_transition_03 lesson_4-6_islamic_parenting_bond_02 lesson_7-9_islamic_parenting_worship_03"
LESSON_MAP[bc41f39f-97ae-4af2-80dd-b070907a80e4]="lesson_13-15_medical_mental_health_03 lesson_4-6_development_positive_parenting_01 lesson_4-6_islamic_parenting_bond_03 lesson_7-9_medical_emotional_health_01"
LESSON_MAP[dab0fff1-8180-4a3f-99ae-6791b243d690]="lesson_13-15_medical_mental_health_04 lesson_4-6_development_positive_parenting_02 lesson_7-9_development_digital_wellbeing_01 lesson_7-9_medical_emotional_health_02"
LESSON_MAP[f7e6f02d-39fb-4888-ae4a-9e0644e75f5e]="lesson_16-18_medical_adult_transition_01 lesson_4-6_islamic_parenting_adab_03 lesson_7-9_islamic_parenting_worship_01"

for SOURCE_ID in "${SOURCES[@]}"; do
  echo ""
  echo "=== Processing source: $SOURCE_ID at $(date) ==="

  # Skip if any target file already exists
  skip=false
  for lesson in ${LESSON_MAP[$SOURCE_ID]}; do
    if [ -f "docs/${lesson}_podcast.mp3" ]; then
      echo "SKIP: docs/${lesson}_podcast.mp3 already exists"
      skip=true
    fi
  done
  if [ "$skip" = true ]; then
    echo "Skipping source $SOURCE_ID (files already present)"
    continue
  fi

  echo "Generating audio..."
  ./notebooklm_env/bin/notebooklm generate audio -n "$NOTEBOOK_ID" -s "$SOURCE_ID" --prompt-file prompts/audio_prompt.txt --language ar_eg --wait --json > /tmp/gen_${SOURCE_ID}.json
  echo "Generation output:"
  cat /tmp/gen_${SOURCE_ID}.json

  if grep -q '"status": "completed"' /tmp/gen_${SOURCE_ID}.json; then
    echo "Downloading latest audio for source $SOURCE_ID..."
    ./notebooklm_env/bin/notebooklm download audio -n "$NOTEBOOK_ID" --latest --force docs/source_${SOURCE_ID}_podcast.mp3 --json
    for lesson in ${LESSON_MAP[$SOURCE_ID]}; do
      cp docs/source_${SOURCE_ID}_podcast.mp3 docs/${lesson}_podcast.mp3
      echo "Copied to docs/${lesson}_podcast.mp3"
    done
  else
    echo "ERROR: generation failed for $SOURCE_ID"
    break
  fi

  echo "Waiting 90 seconds before next source..."
  sleep 90
done

echo ""
echo "=== Updating registry at $(date) ==="

# Update registry: replace ⏳ لم يبدأ in audio column with ✅ ناجح for rows that now have files
python3 << 'PYEOF'
import re, os

repo = '/home/khalednew/projects/tutor-guardian'
registry = f'{repo}/docs/production_registry.md'

with open(registry, 'r') as f:
    lines = f.readlines()

updated = 0
new_lines = []
for line in lines:
    if '| age_' in line or '| demo' in line.lower():
        cols = [c.strip() for c in line.split('|')]
        if len(cols) >= 6:
            lesson_full = cols[1]
            match = re.search(r'lesson_(\d+-\d+_[\w_]+?)(?:\s*$|\s*\|)', lesson_full)
            if match:
                lesson_id = 'lesson_' + match.group(1)
                exact = f'{repo}/docs/{lesson_id}_podcast.mp3'
                base = lesson_id.rsplit('_', 1)[0]
                variant = f'{base}_b04_podcast.mp3'
                if (os.path.exists(exact) or os.path.exists(variant)) and ('⏳' in cols[4] or 'لم يبدأ' in cols[4]):
                    # cols: 0 empty, 1 lesson, 2 source, 3 text, 4 audio, 5 json, 6 notes
                    cols[4] = '✅ ناجح'
                    cols[6] = 'البودكاست تم توليده وتنزيله بنجاح'
                    new_line = '| ' + ' | '.join(cols[1:]) + '\n'
                    new_lines.append(new_line)
                    updated += 1
                    continue
    new_lines.append(line)

with open(registry, 'w') as f:
    f.writelines(new_lines)

print(f'Updated {updated} rows in registry')
PYEOF

echo ""
echo "=== Batch generation completed at $(date) ==="
echo "Log saved to $LOG"
