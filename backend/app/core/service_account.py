"""Reading a Google service-account JSON without taking a feature down with it.

Shared by push (Firebase) and support purchases (Play). Both read a file that
production bind-mounts from the host into /app/backend/secrets — and that file
has arrived 0600 root:root while the container runs as uid 10001, which made
`read_text()` raise PermissionError out of the push path on 2026-07-27. Both
features are optional, so an unreadable or malformed credential must disable
the feature, not raise.

Only the exception *type* is logged: a JSONDecodeError message can quote the
surrounding bytes, which here would be private-key material.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def read_service_account(path: Path, *, label: str, feature: str) -> Optional[dict]:
    """The parsed JSON object at [path], or None if it cannot be used.

    [label] names the credential and [feature] what goes dark without it, for
    the one log line ("Firebase credentials at … are unusable (…) — push
    disabled").
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError: JSONDecodeError, UnicodeDecodeError
        logger.error(
            "%s credentials at %s are unusable (%s) — %s disabled",
            label, path, type(exc).__name__, feature,
        )
        return None
    if not isinstance(data, dict):
        logger.error(
            "%s credentials at %s are unusable (not a JSON object) — %s disabled",
            label, path, feature,
        )
        return None
    return data
