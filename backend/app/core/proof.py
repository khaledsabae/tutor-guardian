"""The proven-token requirement for the most private and irreversible routes.

A token is *proven* when it was minted with proof of possession of its device
(routers/chat.py): the device's first token, or one minted while presenting an
earlier proven (or pre-proof) token. Account deletion and everything that reads
or erases child memory require it (PR #26 review, P1) — knowing a device id is
not owning the family's data.

A client holding an unproven or pre-proof token recovers by minting a new
session with its current token as proof (`POST /api/chat/sessions` with
`Authorization: Bearer <current token>`), then retrying — MOBILE_API.md §9.0.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

PROOF_REQUIRED = {
    "code": "proof_required",
    "message": "أعد فتح الجلسة من هذا الجهاز ثم حاول مرة أخرى.",
}


def require_proven_token(request: Request) -> None:
    if not getattr(request.state, "token_proven", False):
        raise HTTPException(status_code=403, detail=PROOF_REQUIRED)
