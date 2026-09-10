#!/usr/bin/env python3
"""Read the real outcome of Buffer posts — did the network actually publish?

Buffer accepting a post only means it entered the queue. This asks Buffer what
happened afterwards, which is the only thing that answers "did it go out?".

  scripts/check_buffer_post_status.py                    # last 100 posts, per-channel summary
  scripts/check_buffer_post_status.py --id <post_id> ... # specific posts
  scripts/check_buffer_post_status.py --errors           # only the failures
"""
import argparse
import collections
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://api.buffer.com"


def load_token() -> str:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("BUFFER_ACCESS_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


TOKEN = load_token()


def gql(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        URL,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


POST_FIELDS = """
  id channelId status createdAt dueAt sentAt text
  error { message }
  assets { __typename ... on VideoAsset { source } ... on ImageAsset { source } }
"""


def channels() -> dict:
    org = gql("{ account { organizations { id } } }")["data"]["account"]["organizations"][0]["id"]
    data = gql(
        "query C($o: OrganizationId!){ channels(input:{organizationId:$o}){ id service name } }",
        {"o": org},
    )
    return org, {c["id"]: c for c in data["data"]["channels"]}


def describe(node: dict, chan: dict) -> str:
    kinds = {a["__typename"] for a in (node.get("assets") or [])}
    media = "video" if "VideoAsset" in kinds else ("image" if "ImageAsset" in kinds else "text")
    when = node.get("sentAt") or node.get("dueAt") or node.get("createdAt") or ""
    line = f"{node['status']:<10} {media:<6} {chan.get('service','?'):<10} {when[:16]}"
    err = (node.get("error") or {}).get("message")
    if err:
        line += f"\n    ✗ {err}"
    return line


def main() -> int:
    if not TOKEN:
        print("BUFFER_ACCESS_TOKEN not in .env", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", action="append", default=[], help="post id (repeatable)")
    ap.add_argument("--first", type=int, default=100, help="how many recent posts to scan")
    ap.add_argument("--errors", action="store_true", help="show only failed posts")
    args = ap.parse_args()

    org, chans = channels()

    if args.id:
        for pid in args.id:
            data = gql("query P($i: PostInput!){ post(input:$i){" + POST_FIELDS + "} }", {"i": {"id": pid}})
            node = (data.get("data") or {}).get("post")
            if not node:
                print(f"{pid}: not found — {data.get('errors')}")
                continue
            chan = chans.get(node.get("channelId"), {})
            print(describe(node, chan))
        return 0

    data = gql(
        "query P($i: PostsInput!, $f: Int){ posts(input:$i, first:$f){ edges { node { "
        + POST_FIELDS
        + "} } } }",
        {"i": {"organizationId": org}, "f": args.first},
    )
    nodes = [e["node"] for e in data["data"]["posts"]["edges"]]
    tally = collections.Counter()
    for n in sorted(nodes, key=lambda x: x.get("createdAt") or ""):
        chan = chans.get(n.get("channelId"), {})
        kinds = {a["__typename"] for a in (n.get("assets") or [])}
        media = "video" if "VideoAsset" in kinds else ("image" if "ImageAsset" in kinds else "text")
        tally[(chan.get("service", "?"), media, n["status"])] += 1
        if n["status"] == "error" or not args.errors:
            print(describe(n, chan))

    print(f"\n--- {len(nodes)} posts scanned ---")
    for (service, media, status), count in sorted(tally.items()):
        print(f"{service:<10} {media:<6} {status:<10} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
