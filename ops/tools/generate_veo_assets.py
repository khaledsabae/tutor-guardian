#!/usr/bin/env python3
"""
Tutor Guardian - Google Veo Video Generation Tool
=================================================
This tool generates high-quality camera zoom-in/fly-through video clips
and aerial connectors for the landing page using Google's Veo model.

Requirements:
1. Google GenAI SDK: pip install google-genai
2. A valid GEMINI_API_KEY or Vertex AI credentials set in your environment.
"""

import os
import sys
import time
from pathlib import Path
from google import genai
from google.genai import types

# Load local .env variables
def load_env():
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

load_env()

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("\n[!] Error: GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
    print("Please add it to your .env file or export it in your shell environment.")
    print("Example:\n  export GEMINI_API_KEY='your_api_key_here'\n")
    sys.exit(1)

# Initialize GenAI Client
client = genai.Client(api_key=API_KEY)

# Define prompts for each scene
scenes = {
    "hero": {
        "prompt": "Isometric low-poly 3D clay diorama of a cozy family home under a soft glowing dome of protection. The camera slowly glides forward, pushing into the glowing home's cozy window, entering inside smoothly.",
        "output": "frontend/assets/hero_clip.mp4"
    },
    "medical": {
        "prompt": "Isometric low-poly 3D clay diorama of a warm children's bedroom. A mother is reading a story to a child in bed. The camera slowly pushes in towards the bed and the glowing lamp.",
        "output": "frontend/assets/medical_clip.mp4"
    },
    "islamic": {
        "prompt": "Isometric low-poly 3D clay diorama of a library with bookshelves. Father and child reading on a rug. The camera glides forward through the room towards the window showing the crescent moon.",
        "output": "frontend/assets/islamic_clip.mp4"
    },
    "cyber": {
        "prompt": "Isometric low-poly 3D clay diorama of a modern living room. Children playing on a laptop protected by a blue glowing grid bubble. The camera glides forward, pushing inside the protective shield.",
        "output": "frontend/assets/cyber_clip.mp4"
    },
    "finale": {
        "prompt": "Isometric low-poly 3D clay render of a floating modern smartphone showing a family dashboard. The camera zooms in closely, focusing on the screen's family illustration.",
        "output": "frontend/assets/finale_clip.mp4"
    }
}

# Define connector prompts (transitions)
connectors = [
    {
        "prompt": "Cinematic camera flight pulling out from a cozy room, rising into the sky and flying over a beautiful miniature landscape, then descending towards a warm children's bedroom.",
        "output": "frontend/assets/conn_hero_medical.mp4"
    },
    {
        "prompt": "Cinematic camera flight flying up out of a bedroom, rising over an library roof and gliding forward, descending into a cozy library room where books are stacked.",
        "output": "frontend/assets/conn_medical_islamic.mp4"
    },
    {
        "prompt": "Cinematic camera flight gliding out of a library window into the starry sky, flying above a miniature village and descending into a modern family living room.",
        "output": "frontend/assets/conn_islamic_cyber.mp4"
    },
    {
        "prompt": "Cinematic camera flight flying up out of a living room, ascending into a warm pastel-colored floating space, arriving in front of a giant floating smartphone.",
        "output": "frontend/assets/conn_cyber_finale.mp4"
    }
]

def generate_video(prompt, output_path):
    print(f"\n[+] Generating video for: {output_path}")
    print(f"    Prompt: {prompt}")
    
    try:
        # Use Veo 3.1 model for high-quality video generation
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                resolution="720p",
            ),
        )

        print("    Waiting for Veo generation to complete (polling)...")
        while not operation.done:
            time.sleep(15)
            operation = client.operations.get(operation)

        # Download result
        generated_video = operation.response.generated_videos[0]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Download and save the video
        client.files.download(file=generated_video.video)
        generated_video.video.save(output_path)
        print(f"    Successfully saved video to {output_path}")
        
    except Exception as e:
        print(f"    [!] Error generating video: {e}")

def main():
    print("=" * 60)
    print("Tutor Guardian - Google Veo Video Asset Generator")
    print("=" * 60)
    
    # Generate main scene clips
    for name, data in scenes.items():
        if os.path.exists(data["output"]):
            print(f"[o] {data['output']} already exists. Skipping.")
            continue
        generate_video(data["prompt"], data["output"])
        
    # Generate connector transition clips
    for i, conn in enumerate(connectors):
        if os.path.exists(conn["output"]):
            print(f"[o] {conn['output']} already exists. Skipping.")
            continue
        generate_video(conn["prompt"], conn["output"])

    print("\n[+] Asset generation complete. Update frontend/index.html to use the generated clips.")

if __name__ == "__main__":
    main()
