"""The one notification in this feature that cannot wait until evening.

Everything else the child surface sends is batched: one digest, once a day,
and a frequency cap that skips any device already contacted in the last
twenty hours. That is right for "your son says he did his mission". It is
wrong for "your son was asked for his photo by a stranger tonight".

Three things stood between this alert and the parent's phone, and all three
are handled here rather than assumed away:

**The channel.** `push_sender` hard-codes `almorabbi_reengagement` on every
message it sends. A grooming alert arriving on a channel named "re-engagement"
sits next to marketing nudges, and a parent who silences those silences this.
So this sends on `almorabbi_safety`, which a parent can keep on while muting
everything else.

**The frequency cap.** `recently_pushed_since` is per-device, not per-kind. A
parent who got the 9pm mission digest would not get a 9:30pm safety alert at
all. This path never consults it.

**Priority.** `priority="high"` is already set on everything, so it was never
a distinction. The channel is.

Still batched in one respect: this addresses the parent's device token, and
there is no path from here to the child. Rule 4 is absolute.
"""
from __future__ import annotations

from typing import Any

from app.services import push_sender

ALERT_KIND = "license_alert"

# A second Android channel. Notification channels are created client-side on
# first use; the app declares this one so a parent can mute re-engagement and
# keep safety.
SAFETY_CHANNEL = "almorabbi_safety"

_TITLE = "موقف يستاهل كلمة النهارده"

# The body says a conversation is waiting, not what happened.
#
# In many of these families the parent's phone is the phone the child uses, so
# "sent to the parent" is a claim about the token and not about who reads the
# lock screen. A body naming what a stranger asked for is a body the child may
# read about themselves — and worse, one they may learn to delete.
_BODY = "ابنك عدّى على موقف في رخصة الإنترنت. افتح «اليوم» تلاقي إزاي تفتح الكلام فيه."


def send_alert(device_id: str, *, talking_point: str = "",
               critical: bool = False) -> dict[str, Any]:
    """Send the parent a safety alert. Bypasses the daily cap by design.

    `talking_point` travels in the data payload rather than the body, so the
    guidance is there when the parent opens the app without being on a lock
    screen a child can read.
    """
    return push_sender.send_to_device(
        device_id,
        _TITLE,
        _BODY,
        data={
            "kind": ALERT_KIND,
            "type": ALERT_KIND,
            "link": "/license",
            "critical": "1" if critical else "0",
            # Trimmed: FCM caps the whole data payload at 4KB, and the full
            # text is on the screen the link opens anyway.
            "talking_point": talking_point[:300],
        },
        channel_id=SAFETY_CHANNEL,
    )
