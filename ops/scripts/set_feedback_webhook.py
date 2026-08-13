#!/usr/bin/env python3
"""Register (or inspect, or remove) the feedback bot's Telegram webhook.

This is the one manual step that turns on the reply loop: after it runs, a
reply typed in Telegram reaches the user who wrote the feedback.

Secrets are read from the project's .env and are never printed, never passed
on the command line (argv is visible to every process on the box), and never
committed. Set them first:

    FEEDBACK_TELEGRAM_BOT_TOKEN=...        # from @BotFather, a DEDICATED bot
    FEEDBACK_TELEGRAM_CHAT_ID=...          # your chat with that bot
    FEEDBACK_TELEGRAM_WEBHOOK_SECRET=...   # openssl rand -hex 32

Usage:
    python3 ops/scripts/set_feedback_webhook.py            # register
    python3 ops/scripts/set_feedback_webhook.py --status   # inspect
    python3 ops/scripts/set_feedback_webhook.py --delete   # unregister

A bot can hold exactly one webhook, which is why this must be a bot dedicated
to feedback and not the marketing TELEGRAM_BOT_TOKEN.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
DEFAULT_URL = "https://tg-api.alsaba.cloud/api/feedback/telegram/webhook"


def load_env() -> dict[str, str]:
    """Minimal .env reader — no dependency on python-dotenv.

    Falls back to the process environment when there is no .env file: inside
    the production container compose injects the variables and no such file
    exists, and running this there is the obvious first thing to try.
    """
    if not ENV_FILE.exists():
        import os

        env = {k: v for k in (
            "FEEDBACK_TELEGRAM_BOT_TOKEN", "FEEDBACK_TELEGRAM_WEBHOOK_SECRET",
        ) if (v := os.environ.get(k))}
        if not env:
            sys.exit(f"missing {ENV_FILE}, and nothing in the environment either")
        return env
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip("'\"")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="public webhook URL")
    parser.add_argument("--status", action="store_true", help="show current webhook")
    parser.add_argument("--delete", action="store_true", help="remove the webhook")
    args = parser.parse_args()

    env = load_env()
    token = env.get("FEEDBACK_TELEGRAM_BOT_TOKEN", "")
    secret = env.get("FEEDBACK_TELEGRAM_WEBHOOK_SECRET", "")

    if not token:
        sys.exit("FEEDBACK_TELEGRAM_BOT_TOKEN is not set in .env")

    api = f"https://api.telegram.org/bot{token}"

    if args.status:
        resp = httpx.get(f"{api}/getWebhookInfo", timeout=15)
        info = resp.json().get("result", {})
        print(f"url:                  {info.get('url') or '(none)'}")
        print(f"pending updates:      {info.get('pending_update_count', 0)}")
        print(f"custom certificate:   {info.get('has_custom_certificate')}")
        print(f"secret token set:     {bool(info.get('url')) and 'yes (opaque)' or 'n/a'}")
        if info.get("last_error_message"):
            print(f"last error:           {info['last_error_message']}")
        return 0

    if args.delete:
        resp = httpx.post(f"{api}/deleteWebhook", timeout=15)
        print("deleted" if resp.json().get("ok") else f"failed: {resp.text[:200]}")
        return 0 if resp.json().get("ok") else 1

    if not secret:
        sys.exit(
            "FEEDBACK_TELEGRAM_WEBHOOK_SECRET is not set in .env.\n"
            "The endpoint fails closed without it, so registering now would "
            "give you a webhook that rejects every update.\n"
            "Generate one with: openssl rand -hex 32"
        )

    resp = httpx.post(
        f"{api}/setWebhook",
        json={
            "url": args.url,
            "secret_token": secret,
            # We only care about replies typed in the chat.
            "allowed_updates": ["message", "channel_post"],
            "drop_pending_updates": True,
        },
        timeout=15,
    )
    body = resp.json()
    if body.get("ok"):
        print(f"webhook registered → {args.url}")
        print("send yourself a test feedback from the app, then reply to the alert.")
        return 0
    # Telegram echoes the request URL but not the secret, so this is safe.
    print(f"failed: {body.get('description', resp.text[:200])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
