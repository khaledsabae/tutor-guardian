"""One shape for every timestamp the API returns: ISO 8601, UTC, with Z.

SQLite writes `datetime('now')` as 'YYYY-MM-DD HH:MM:SS' (UTC, no zone), Python
as '…+00:00' — clients parsed both, and a zone-less one reads as local time on
the phone. `iso_z` turns either (or a datetime) into 'YYYY-MM-DDTHH:MM:SSZ'
(PR #26 final review).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union


def iso_z(value: Union[str, datetime, None]) -> Optional[str]:
    """'YYYY-MM-DDTHH:MM:SSZ', or None. A value that is not a timestamp
    passes through unchanged."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T", 1))
        except ValueError:
            return text
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat() + "Z"


def now_z() -> str:
    return iso_z(datetime.now(timezone.utc))
