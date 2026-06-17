#!/usr/bin/env bash
# Generate audio for ONE source, download it, and copy to its lessons
set -euo pipefail

export HOME=/home/khalednew
REPO=/home/khalednew/projects/tutor-guardian
NOTEBOOK_ID=94f191e6-cfbc-4655-a0d7-c8f7ad0f2287
SOURCE_ID=$1
shift
LESSONS="$@"
LOG=/tmp/podcast_gen_${SOURCE_ID}.log
exec > >(tee -a "$LOG") 2>&1

cd "$REPO"

echo "=== Source $SOURCE_ID started at $(date) ==="

# Generate audio and wait
./notebooklm_env/bin/notebooklm generate audio -n "$NOTEBOOK_ID" -s "$SOURCE_ID" --prompt-file prompts/audio_prompt.txt --language ar_eg --wait --json > /tmp/gen_${SOURCE_ID}.json
echo "Generation result:"
cat /tmp/gen_${SOURCE_ID}.json

if grep -q '"status": "completed"' /tmp/gen_${SOURCE_ID}.json; then
    echo "Downloading audio..."
    ./notebooklm_env/bin/notebooklm download audio -n "$NOTEBOOK_ID" --latest --force docs/source_${SOURCE_ID}_podcast.mp3 --json
    for lesson in $LESSONS; do
        cp docs/source_${SOURCE_ID}_podcast.mp3 docs/${lesson}_podcast.mp3
        echo "Copied to docs/${lesson}_podcast.mp3"
    done
    echo "=== Source $SOURCE_ID completed at $(date) ==="
else
    echo "=== Source $SOURCE_id FAILED at $(date) ==="
    exit 1
fi
