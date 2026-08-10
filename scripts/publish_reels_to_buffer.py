#!/usr/bin/env python3
"""Publish generated tutor-guardian reels to Buffer (Instagram/TikTok/Facebook).

Flow:
  1. Read reels manifest at docs/marketing/reels_output/manifest.json.
  2. Pick the oldest reel with status != 'posted'.
  3. Parse caption from captions.md by matching the reel filename.
  4. Copy the MP4 to the remote VPS docs/marketing/reels_output/ so it has a public URL.
  5. Schedule the reel via Buffer GraphQL API to all connected channels.
  6. Mark the reel as posted in the local manifest.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
REELS_DIR = ROOT / "docs" / "marketing" / "reels_output"
CAPTIONS_FILE = REELS_DIR / "captions.md"
MANIFEST_FILE = REELS_DIR / "manifest.json"
REMOTE_HOST = os.environ.get("TUTOR_VPS_HOST", "root@72.62.44.131")
REMOTE_DIR = "/root/tutor-guardian/docs/marketing/reels_output"
PUBLIC_BASE_URL = os.environ.get("API_BASE_URL", "https://tg-api.alsaba.cloud")

def load_env() -> dict:
    env = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

_ENV = load_env()
BUFFER_TOKEN = _ENV.get("BUFFER_ACCESS_TOKEN", "")

def buffer_headers() -> dict:
    return {"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"}

def get_buffer_channels() -> list[dict]:
    if not BUFFER_TOKEN:
        raise RuntimeError("BUFFER_ACCESS_TOKEN not configured")
    url = "https://api.buffer.com"
    org_query = {"query": "query { account { organizations { id } } }"}
    resp = requests.post(url, headers=buffer_headers(), json=org_query, timeout=15)
    resp.raise_for_status()
    orgs = resp.json().get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        raise RuntimeError("No Buffer organization found")
    org_id = orgs[0]["id"]
    channels_query = {
        "query": "query GetChannels($orgId: OrganizationId!) { channels(input: { organizationId: $orgId }) { id service name } }",
        "variables": {"orgId": org_id},
    }
    resp = requests.post(url, headers=buffer_headers(), json=channels_query, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", {}).get("channels", [])

def parse_captions() -> dict[str, dict]:
    """Return {reel_filename_slug: {title, hook, caption, hashtags}}."""
    if not CAPTIONS_FILE.exists():
        return {}
    text = CAPTIONS_FILE.read_text(encoding="utf-8")
    out = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^## \d+\) ([^—]+)—(.+)", line.strip())
        if m:
            if current:
                key = re.sub(r"[^\w\-]", "_", current.get("title", "")).strip("_")[:80]
                if key:
                    out[key] = current
            current = {"title": m.group(1).strip(), "hook": m.group(2).strip()}
            continue
        if current is None:
            continue
        if line.startswith("**الهوك:**"):
            current["hook"] = line.replace("**الهوك:**", "").strip()
        elif line.startswith("**الكابشن:**"):
            current["caption"] = ""
        elif line.startswith("**هاشتاجات:**"):
            current["hashtags"] = line.replace("**هاشتاجات:**", "").strip()
        elif "caption" in current and current["caption"] == "" and line and not line.startswith("**"):
            current["caption"] = line.strip()
    if current:
        key = re.sub(r"[^\w\-]", "_", current.get("title", "")).strip("_")[:80]
        if key:
            out[key] = current
    return out

def find_caption_for_reel(filename: str, captions: dict) -> Optional[dict]:
    slug = Path(filename).stem.replace("reel_", "")
    for key, cap in captions.items():
        if key in slug or slug in key:
            return cap
    return None

def build_caption(cap: dict) -> str:
    lines = []
    if "hook" in cap:
        lines.append(cap["hook"])
    if "caption" in cap:
        lines.append(cap["caption"])
    lines.append("حمّل «المربّي الذكي» مجانًا على Google Play 🤍\n👉 https://play.google.com/store/apps/details?id=com.alsaba.almorabbi")
    if "hashtags" in cap:
        lines.append(cap["hashtags"])
    return "\n\n".join(lines)

def sync_to_vps(local_path: Path) -> str:
    """Copy local MP4 to remote VPS static dir and return public URL."""
    remote_path = f"{REMOTE_DIR}/{local_path.name}"
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", str(local_path), f"{REMOTE_HOST}:{remote_path}"],
        check=True,
    )
    return f"{PUBLIC_BASE_URL}/docs/marketing/reels_output/{local_path.name}"

def publish_to_buffer(video_url: str, caption: str, channels: list[dict], dry_run: bool = False) -> dict[str, str]:
    if dry_run:
        print(f"[DRY RUN] Would post to {len(channels)} channels: {video_url}\n{caption[:200]}")
        return {c["id"]: "dry-run" for c in channels}
    url = "https://api.buffer.com"
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id status } }
        ... on MutationError { message }
      }
    }
    """
    results = {}
    for ch in channels:
        service = ch["service"]
        metadata = {}
        if service == "instagram":
            metadata = {"instagram": {"type": "reel", "shouldShareToFeed": True}}
        elif service == "tiktok":
            metadata = {"tiktok": {}}
        elif service == "facebook":
            metadata = {"facebook": {"type": "reel"}}
        post_input = {
            "text": caption,
            "channelId": ch["id"],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [{"video": {"url": video_url}}],
            "metadata": metadata,
        }
        payload = {"query": mutation, "variables": {"input": post_input}}
        try:
            resp = requests.post(url, headers=buffer_headers(), json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errors"):
                results[ch["id"]] = f"error: {data['errors'][0]['message']}"
            else:
                res = data.get("data", {}).get("createPost", {})
                results[ch["id"]] = res.get("post", {}).get("id") or res.get("message", "unknown")
        except Exception as e:
            results[ch["id"]] = f"error: {e}"
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=1, help="Max reels to publish per run")
    args = parser.parse_args()

    if not MANIFEST_FILE.exists():
        print("No reels manifest found; run podcast_to_reel.py first.")
        return

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    rendered = manifest.get("rendered", [])
    captions = parse_captions()
    channels = get_buffer_channels()
    print(f"Buffer channels: {[(c['service'], c.get('name')) for c in channels]}")

    posted_count = 0
    for entry in rendered:
        if entry.get("status") == "posted":
            continue
        if posted_count >= args.limit:
            break
        filename = entry.get("file")
        local_path = REELS_DIR / filename
        if not local_path.exists():
            print(f"SKIP: {filename} not found locally")
            continue
        cap = find_caption_for_reel(filename, captions)
        caption_text = build_caption(cap) if cap else (
            "💡 نصيحة تربوية من «المربّي الذكي»\n\n"
            "حمّل «المربّي الذكي» مجانًا على Google Play 🤍\n"
            "👉 https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"
        )
        print(f"Publishing: {filename}")
        if not args.dry_run:
            video_url = sync_to_vps(local_path)
        else:
            video_url = f"{PUBLIC_BASE_URL}/docs/marketing/reels_output/{filename}"
        results = publish_to_buffer(video_url, caption_text, channels, dry_run=args.dry_run)
        print(f"Results: {results}")
        if not args.dry_run:
            entry["status"] = "posted"
            entry["posted_at"] = datetime.now(timezone.utc).isoformat()
            entry["buffer_results"] = results
            MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Marked {filename} as posted")
        posted_count += 1

if __name__ == "__main__":
    main()

