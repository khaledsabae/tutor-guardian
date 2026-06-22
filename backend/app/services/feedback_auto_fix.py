"""
feedback_auto_fix — analyze app feedback and auto-apply safe, low-risk fixes.

This is intentionally conservative. It only acts on feedback that matches a
known, verifiable pattern (typo in a hardcoded string, broken URL, etc.).
Everything else is left for human review.
"""
import os
from pathlib import Path

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _ask(prompt: str) -> str:
    if not _DEEPSEEK_API_KEY:
        return "no_api_key"
    try:
        resp = httpx.post(
            _DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {_DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a conservative code reviewer. Only respond with 'APPLY:' followed by the exact change if the fix is trivial, safe, and verifiable. Otherwise respond with 'SKIP:' and reason."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"ERROR: {exc}"


def analyze_feedback_for_autofix(message: str) -> dict:
    """
    Returns {"action": "skip" | "apply", "details": str, "patch": str | None}.
    A patch is only returned for trivial string fixes with a clear file path.
    """
    if not message or len(message.strip()) < 10:
        return {"action": "skip", "details": "too short", "patch": None}

    prompt = f"""App feedback (Arabic parenting app):
{message.strip()}

Is this a trivial typo/bug in a hardcoded Arabic string or a clearly broken hardcoded URL?
If yes, provide file path (relative to project root) and the exact find/replace.
If no, say SKIP."""

    answer = _ask(prompt)
    if answer.startswith("APPLY:"):
        return {"action": "apply", "details": answer, "patch": answer[6:].strip()}
    return {"action": "skip", "details": answer, "patch": None}
