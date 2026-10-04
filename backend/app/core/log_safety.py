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


def describe_rejected_id(value) -> str:
    """A device id the API refused, described without being repeated.

    Production holds ids that are mostly U+FFFD (a keystore decrypting with
    the wrong key) and one with spaces; such a client is refused on every
    session mint. This line lets an operator count them and tell one client
    retrying from many — the tag is stable per value — without the log
    carrying the value itself.
    """
    if not isinstance(value, str):
        return f"type={type(value).__name__}"
    fffd = value.count("\ufffd")
    space = sum(ch.isspace() for ch in value)
    non_ascii = sum(not ch.isascii() for ch in value) - fffd
    return (f"len={len(value)} bytes={len(value.encode('utf-8', 'surrogatepass'))} "
            f"fffd={fffd} space={space} other_non_ascii={non_ascii} "
            f"tag={device_tag(value) if value else '-'}")
