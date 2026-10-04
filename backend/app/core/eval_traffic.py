"""How evaluation traffic is marked, so metrics can leave it out.

`ops/tools/eval_answers.py` creates one device per question, named
`EVAL_DEVICE_PREFIX + <item id>` (e.g. ``eval-harness-real-1234``). That device
id lands on every row the run writes: chat_sessions, api_tokens, and — when a
memory item creates a child — child_profiles and child_facts.

Since the harness was isolated (2026-10-04) it writes to a throwaway database
only. Before that, the 2026-09-24 baseline ran inside the production container
and wrote 92 such sessions into the production database; they are still there
(production data is not deleted by scripts). Any metric that counts devices,
sessions or questions must therefore exclude this prefix:

    from app.core.eval_traffic import EVAL_DEVICE_LIKE
    conn.execute("... WHERE device_id NOT LIKE ?", (EVAL_DEVICE_LIKE,))

or, in Python, `is_eval_device(device_id)`.

Deliberately dependency-free: scripts under ops/ import it after putting
`backend/` on sys.path, and it must not drag the app (or a database) in.
"""
from __future__ import annotations

EVAL_DEVICE_PREFIX = "eval-harness-"

# For `NOT LIKE ?`. The prefix holds no `%` or `_`, so it needs no ESCAPE.
EVAL_DEVICE_LIKE = EVAL_DEVICE_PREFIX + "%"


def is_eval_device(device_id: str | None) -> bool:
    return bool(device_id) and str(device_id).startswith(EVAL_DEVICE_PREFIX)
