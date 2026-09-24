"""Log-safe stand-ins for identifiers that double as credentials.

A device id is a bearer credential in this API (audit H5): whoever knows it
can mint a session for that family. Logs, Telegram alerts and error reports
therefore carry ``device_tag(device_id)`` — a short, stable sha256 prefix that
still lets an operator correlate lines for one device, and match a report
against the database with ``device_tag`` computed there, without the log
itself being a key to the account.
"""
import hashlib


def device_tag(device_id: str | None) -> str:
    if not device_id:
        return "-"
    return "d:" + hashlib.sha256(device_id.encode()).hexdigest()[:12]
