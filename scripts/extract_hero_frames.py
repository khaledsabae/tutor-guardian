#!/usr/bin/env python3
"""
Extract, resize, and compress video frames from Flow video for canvas scroll scrubbing.
"""
import os
import shutil
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    downloads_dir = Path.home() / "Downloads"
    frontend_dir = root_dir / "frontend"
    assets_dir = frontend_dir / "assets"
    frames_dir = assets_dir / "hero_frames"
    
    # 1. Source files from downloads
    video_src = downloads_dir / "Protective_shield_materializes__1080p_20260913155201.mp4"
    img1_src = downloads_dir / "Gemini_Generated_Image_sdn98vsdn98vsdn9.jpeg"
    img2_src = downloads_dir / "Gemini_Generated_Image_th4h12th4h12th4h.jpeg"
    
    if not video_src.exists():
        print(f"Error: Video file not found at {video_src}")
        return 1
        
    assets_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy source assets
    dest_video = assets_dir / "hero_flow.mp4"
    dest_img1 = assets_dir / "hero_start.jpg"
    dest_img2 = assets_dir / "hero_end.jpg"
    
    print(f"Copying video to {dest_video}...")
    shutil.copy2(video_src, dest_video)
    
    if img1_src.exists():
        print(f"Copying start image to {dest_img1}...")
        shutil.copy2(img1_src, dest_img1)
    if img2_src.exists():
        print(f"Copying end image to {dest_img2}...")
        shutil.copy2(img2_src, dest_img2)
        
    # Clean previous frames if any
    for existing in frames_dir.glob("frame_*.jpg"):
        existing.unlink()
        
    # Extract 96 frames evenly spaced across the 8-second video
    # 96 frames / 8s = 12 fps
    # Scale to 1280x720 (crisp on high-DPI canvas while very light ~35KB per frame)
    print("Extracting 96 optimized frames via ffmpeg...")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(dest_video),
        "-vf", "fps=12,scale=1280:720:flags=lanczos",
        "-q:v", "4",  # High JPEG quality, small size
        str(frames_dir / "frame_%03d.jpg")
    ]
    subprocess.run(cmd, check=True)
    
    frame_count = len(list(frames_dir.glob("frame_*.jpg")))
    print(f"Successfully extracted {frame_count} frames into {frames_dir}")
    
    # Calculate total size
    total_bytes = sum(f.stat().st_size for f in frames_dir.glob("frame_*.jpg"))
    print(f"Total size of all frames: {total_bytes / (1024 * 1024):.2f} MB")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
