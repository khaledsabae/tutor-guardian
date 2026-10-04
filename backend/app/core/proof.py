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

Both also refuse — `device_proof_cooldown`, with `available_at` — for 72 hours
after the device's push token was replaced without a proven session vouching
for it, even a session proven on the new token (device_proof, round 3).
`require_device_proof_irreversible` (account deletion) and the child routes
are also paused for the first 72 hours of an established device's first push
token (round 4); memory is not. Switching memory off stays open throughout.
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

DEVICE_PROOF_COOLDOWN = {
    "code": "device_proof_cooldown",
    "message": "لحماية بيانات أسرتك، تُتاح هذه الخطوة بعد 72 ساعة من ربط هذا الجهاز بحسابك "
               "لاستقبال الإشعارات. يمكنك إيقاف الذاكرة في أي وقت، وللمساعدة راسلنا على "
               f"{SUPPORT_EMAIL}.",
    "message_en": "To protect your family's data, this step becomes available 72 hours "
                  "after this device was linked to your account for notifications. You "
                  f"can turn memory off at any time. For help, email {SUPPORT_EMAIL}.",
    "support_email": SUPPORT_EMAIL,
}


def request_access(request: Request, irreversible: bool = False) -> device_proof.Access:
    """May the session behind this request use the protected routes? Cached per
    kind: `irreversible` (account and child deletion) or not."""
    cache = getattr(request.state, "device_access", None)
    if cache is None:
        cache = {}
        request.state.device_access = cache
    if irreversible not in cache:
        cache[irreversible] = device_proof.access(
            getattr(request.state, "device_id", None),
            getattr(request.state, "token", None), irreversible=irreversible)
    return cache[irreversible]


def request_proven(request: Request) -> bool:
    """Proven on the current push token and not in a cooldown — the test for
    every protected route, and for memory in answers and coach tips (F4)."""
    return request_access(request).ok


def _refuse(acc: device_proof.Access) -> HTTPException:
    if acc.reason == "cooldown":
        return HTTPException(status_code=403, detail={
            **DEVICE_PROOF_COOLDOWN, "available_at": acc.available_at})
    return HTTPException(status_code=403, detail=DEVICE_PROOF_REQUIRED)


def require_device_proof(request: Request) -> None:
    acc = request_access(request)
    if not acc.ok:
        raise _refuse(acc)


def require_device_proof_irreversible(request: Request) -> None:
    """Account deletion: a proof, and no cooldown of either kind."""
    acc = request_access(request, irreversible=True)
    if not acc.ok:
        raise _refuse(acc)


def require_device_proof_once_enrolled(request: Request) -> None:
    acc = request_access(request, irreversible=True)
    if acc.ok:
        return
    device_id = getattr(request.state, "device_id", None)
    if device_proof.required_for_every_device() or device_proof.ever_proven(device_id):
        raise _refuse(acc)
