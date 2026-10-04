"""«ادعم المربّي» — support purchases and the transparency page.

  GET  /api/support/transparency  (public) → this month's cost, what supporters
       covered, and the share. Aggregates only; no donor is ever named.
  POST /api/support/verify        (Bearer, 5/min per IP and per device) → body
       {product_id, purchase_token, price_micros?, currency?}. Verifies with
       Play, records, consumes.

Whether the app shows any of this is decided by ``/api/app-config``
(``donations_enabled``), which is off unless ``DONATIONS_ENABLED=true`` *and*
the Play service account loads. See ``app/services/donations.py`` for the
policy citation, the ledger's privacy shape and the rough-USD method.

Status codes the app acts on: 200 recorded · 202 pending at Play · 400 Play
says it is not a purchase, or a product this server never sold · 503 anything
else, which the app retries on the next launch. A 5xx is the safe default:
the purchase stays unconsumed, so nothing is lost — at worst Play refunds it.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services import donations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


class VerifyIn(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    # Play tokens run to a few hundred characters; the cap only stops abuse.
    purchase_token: str = Field(..., min_length=8, max_length=4096)
    # What the store showed the parent. Kept only on test purchases (never
    # counted); a real purchase is priced from Play's order or left unpriced.
    price_micros: Optional[int] = Field(None, ge=0, le=10_000_000_000_000)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)


@router.get("/transparency")
def get_transparency() -> dict:
    return donations.transparency()


@router.post("/verify")
def verify_purchase(body: VerifyIn, request: Request):
    if not getattr(request.state, "device_id", None):
        raise HTTPException(status_code=401, detail="مطلوب توثيق")
    try:
        result = donations.record_purchase(
            body.product_id, body.purchase_token,
            client_price_micros=body.price_micros,
            client_currency=body.currency,
        )
    except donations.UnknownProduct:
        raise HTTPException(status_code=400, detail="unknown_product")
    except donations.InvalidPurchase:
        raise HTTPException(status_code=400, detail="invalid_purchase")
    except donations.VerificationUnavailable:
        # Retryable. The app keeps the purchase unconsumed and re-sends it on
        # the next launch; if it never succeeds, Play refunds it after 3 days.
        raise HTTPException(status_code=503, detail="verification_unavailable")
    except Exception as exc:  # noqa: BLE001 — config, credentials, a bad reply
        # Never a 400: a 400 tells the app the purchase is bad, and it would
        # stop retrying a purchase that may be perfectly good. Logged by type
        # only — exception text can quote a URL, and the URL holds the token.
        logger.error("support verify failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="verification_unavailable")
    if result.get("pending"):
        return JSONResponse(status_code=202, content=result)
    return result
