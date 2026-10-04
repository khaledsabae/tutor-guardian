"""Guards for the routes that need a session proven to hold its phone.

The proof itself is an FCM challenge (services/device_proof.py, MOBILE_API.md
§9.0): the server sends a single-use code to the device's current push token
and the session posts it back. Knowing a device id — e.g. decoded from an old
child token — is not owning the family's data.

`require_device_proof` — always: account deletion, everything that reads,
changes or erases child memory, and switching memory ON. (Switching it OFF
never needs a proof: stopping is always allowed.)

`require_device_proof_once_enrolled` — the destructive child routes (delete a
child, reset its progress). No build on Play can answer a challenge yet, so
requiring it of every device would take child deletion away from every family
until they update. It is required once the device has ever proven — every
device that has memory has, because nothing writes memory without a proof —
and for every device once the forced-update floor reaches the build that can
prove (device_proof.required_for_every_device).
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.contact import SUPPORT_EMAIL
from app.services import device_proof

DEVICE_PROOF_REQUIRED = {
    "code": "device_proof_required",
    "message": "نحتاج أن نتأكد أن هذا الطلب من هاتفك قبل هذه الخطوة. حاول مرة أخرى.",
    "message_en": "We need to confirm this request comes from your phone before this "
                  "step. Please try again.",
    "support_email": SUPPORT_EMAIL,
}


def request_proven(request: Request) -> bool:
    """Is the session behind this request proven? Cached on the request."""
    cached = getattr(request.state, "device_proven", None)
    if cached is not None:
        return cached
    proven = device_proof.is_proven(getattr(request.state, "device_id", None),
                                    getattr(request.state, "token", None))
    request.state.device_proven = proven
    return proven


def require_device_proof(request: Request) -> None:
    if not request_proven(request):
        raise HTTPException(status_code=403, detail=DEVICE_PROOF_REQUIRED)


def require_device_proof_once_enrolled(request: Request) -> None:
    if request_proven(request):
        return
    device_id = getattr(request.state, "device_id", None)
    if device_proof.required_for_every_device() or device_proof.ever_proven(device_id):
        raise HTTPException(status_code=403, detail=DEVICE_PROOF_REQUIRED)
