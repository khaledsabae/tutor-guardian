#!/usr/bin/env python3
"""Cut podcasts into 30-60 second Reels with Arabic text overlay and watermark.

Usage:
    python ops/scripts/podcast_to_reels.py --input docs/podcast.mp3 --output reels/

Features:
- Auto-detect silence points for natural cuts
- Arabic text overlay from transcript
- App watermark + Play Store link
- 9:16 vertical format for TikTok/YouTube Shorts/Instagram Reels
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent

# Default settings
DEFAULT_REEL_DURATION = 45  # seconds
DEFAULT_WATERMARK_TEXT = "المربّي — مجاني لوجه الله 🤍"
DEFAULT_STORE_LINK = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"


def detect_silence(audio_path: str, threshold: float = -30, duration: float = 0.5) -> list[float]:
    """Detect silence points in audio for natural cutting."""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={threshold}dB:d={duration}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    silence_points = []
    for line in result.stderr.split("\n"):
        if "silence_start" in line:
            try:
                time_str = line.split("silence_start:")[1].strip()
                silence_points.append(float(time_str))
            except (IndexError, ValueError):
                pass
    
    return silence_points


def create_reel(
    audio_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    text: str,
    watermark: str = DEFAULT_WATERMARK_TEXT,
    store_link: str = DEFAULT_STORE_LINK,
) -> bool:
    """Create a single reel with text overlay and watermark."""
    
    # Create text overlay filter
    text_filter = (
        f"drawtext=text='{text}':"
        f"fontsize=48:fontcolor=white:"
        f"borderw=3:bordercolor=black:"
        f"x=(w-text_w)/2:y=h/3:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    
    watermark_filter = (
        f"drawtext=text='{watermark}':"
        f"fontsize=24:fontcolor=white@0.8:"
        f"x=(w-text_w)/2:y=h-100:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    
    store_filter = (
        f"drawtext=text='{store_link}':"
        f"fontsize=20:fontcolor=white@0.6:"
        f"x=(w-text_w)/2:y=h-60:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    
    # Create gradient background + audio + text overlay
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x01696F:s=1080x1920:d={duration}",
        "-ss", str(start_time), "-t", str(duration), "-i", audio_path,
        "-filter_complex",
        f"[0:v]{text_filter},{watermark_filter},{store_filter}[outv];"
        f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[outa]",
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  Timeout creating reel", file=sys.stderr)
        return False


def extract_text_from_transcript(transcript_path: str, start: float, end: float) -> str:
    """Extract text from transcript for the given time range."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)
        
        # Simple transcript format: list of {start, end, text}
        texts = []
        for entry in transcript:
            if entry.get("start", 0) >= start and entry.get("end", 0) <= end:
                texts.append(entry.get("text", ""))
        
        return " ".join(texts)[:100]  # Limit to 100 chars for overlay
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Convert podcasts to Reels")
    parser.add_argument("--input", "-i", required=True, help="Input podcast MP3 file")
    parser.add_argument("--output", "-o", default="reels", help="Output directory")
    parser.add_argument("--duration", "-d", type=int, default=DEFAULT_REEL_DURATION, 
                       help=f"Reel duration in seconds (default: {DEFAULT_REEL_DURATION})")
    parser.add_argument("--max-reels", "-n", type=int, default=5, 
                       help="Maximum number of reels to generate")
    parser.add_argument("--transcript", "-t", help="Optional transcript JSON file")
    parser.add_argument("--watermark", "-w", default=DEFAULT_WATERMARK_TEXT, 
                       help="Watermark text")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get audio duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        total_duration = float(result.stdout.strip())
    except ValueError:
        print("Error: Could not determine audio duration", file=sys.stderr)
        return 1
    
    print(f"Input: {input_path.name}")
    print(f"Duration: {total_duration:.1f}s")
    print(f"Target reel duration: {args.duration}s")
    
    # Detect silence points for natural cuts
    print("Detecting silence points...")
    silence_points = detect_silence(str(input_path))
    print(f"Found {len(silence_points)} silence points")
    
    # Generate cuts
    cuts = []
    if silence_points:
        # Use silence points as cut markers
        prev = 0
        for sp in silence_points:
            if sp - prev >= args.duration * 0.8:  # At least 80% of target duration
                cuts.append((prev, min(sp, total_duration)))
                prev = sp
        # Add final segment if needed
        if total_duration - prev >= args.duration * 0.5:
            cuts.append((prev, total_duration))
    else:
        # No silence detected - cut at regular intervals
        num_cuts = min(args.max_reels, int(total_duration / args.duration) + 1)
        for i in range(num_cuts):
            start = i * args.duration
            end = min(start + args.duration, total_duration)
            if end - start >= args.duration * 0.5:
                cuts.append((start, end))
    
    # Limit to max reels
    cuts = cuts[:args.max_reels]
    print(f"Generating {len(cuts)} reels...")
    
    # Generate reels
    generated = 0
    for i, (start, end) in enumerate(cuts):
        duration = end - start
        
        # Get text for this segment
        if args.transcript:
            text = extract_text_from_transcript(args.transcript, start, end)
        else:
            text = f"المربّي — تربية إسلامية"
        
        output_file = output_dir / f"reel_{i+1:02d}.mp4"
        print(f"  Creating reel {i+1}/{len(cuts)}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")
        
        if create_reel(
            str(input_path),
            str(output_file),
            start,
            duration,
            text,
            args.watermark,
        ):
            generated += 1
            print(f"    ✓ Created: {output_file.name}")
        else:
            print(f"    ✗ Failed to create reel {i+1}")
    
    print(f"\nDone: {generated}/{len(cuts)} reels generated in {output_dir}/")
    return 0 if generated > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
