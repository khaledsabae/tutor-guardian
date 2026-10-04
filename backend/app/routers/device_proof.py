"""Device proof — the FCM challenge behind the protected routes (MOBILE_API.md §9.0).

    GET  /api/device-proof           is this session proven right now?
    POST /api/device-proof/start     send a code to the device's current push token
    POST /api/device-proof/complete  post the code back; this session is proven

Errors carry a stable `code`, an Arabic `message`, an English `message_en`,
and — where the automatic path cannot work — the support address:
    {"detail": {"code": "no_push_token", "message": "…", "message_en": "…",
                "support_email": "…"}}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.contact import SUPPORT_EMAIL
from app.services import device_proof

router = APIRouter(tags=["device-proof"])

_MESSAGES: dict[str, tuple[str, str]] = {
    "no_push_token": (
        "لم يُسجَّل هذا الهاتف لدينا لاستقبال الرسائل بعد، فلا يمكننا التحقق منه. "
        "أعد فتح التطبيق وهو متصل بالإنترنت ثم حاول مرة أخرى. "
        f"وإن تكررت المشكلة فراسلنا على {SUPPORT_EMAIL}.",
        "This phone isn't registered with us to receive messages yet, so we can't "
        "verify it. Reopen the app while connected to the internet and try again. "
        f"If it keeps happening, email us at {SUPPORT_EMAIL}.",
    ),
    "push_unavailable": (
        "تعذّر إرسال رمز التحقق الآن. حاول بعد قليل، "
        f"وإن تكررت المشكلة فراسلنا على {SUPPORT_EMAIL}.",
        "We couldn't send the verification code just now. Try again shortly. "
        f"If it keeps happening, email us at {SUPPORT_EMAIL}.",
    ),
    "proof_rate_limited": (
        "محاولات تحقق كثيرة. انتظر قليلًا ثم حاول مرة أخرى.",
        "Too many verification attempts. Wait a little and try again.",
    ),
    "proof_failed": (
        "تعذّر التحقق من هذا الهاتف. حاول مرة أخرى.",
        "We couldn't verify this phone. Please try again.",
    ),
}
_WITH_SUPPORT = {"no_push_token", "push_unavailable"}


def _error(exc: device_proof.ProofError) -> HTTPException:
    ar, en = _MESSAGES[exc.code]
    detail: dict = {"code": exc.code, "message": ar, "message_en": en}
    if exc.reason:
        detail["reason"] = exc.reason
    if exc.code in _WITH_SUPPORT:
        detail["support_email"] = SUPPORT_EMAIL
    return HTTPException(status_code=exc.status, detail=detail)


def _caller(request: Request) -> tuple[str, str]:
    device_id = getattr(request.state, "device_id", None)
    token = getattr(request.state, "token", None)
    if not device_id or not token:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id, token


@router.get("/device-proof", summary="Is this session proven to hold its phone?")
def proof_status(request: Request):
    device_id, token = _caller(request)
    return device_proof.status(device_id, token)


@router.post("/device-proof/start", status_code=202,
             summary="Send a one-time code to this device's current push token")
def proof_start(request: Request):
    device_id, token = _caller(request)
    try:
        return device_proof.start(device_id, token)
    except device_proof.ProofError as exc:
        raise _error(exc) from exc


class ProofCompleteIn(BaseModel):
    challenge_id: str = Field(min_length=8, max_length=64)
    code: str = Field(min_length=1, max_length=128)


@router.post("/device-proof/complete",
             summary="Post the code back; this session is then proven")
def proof_complete(body: ProofCompleteIn, request: Request):
    device_id, token = _caller(request)
    try:
        return device_proof.complete(device_id, token, body.challenge_id, body.code)
    except device_proof.ProofError as exc:
        raise _error(exc) from exc
