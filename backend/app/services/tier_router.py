"""Quality-tier routing — decides whether a request deserves the cloud
quality model or the fast local chain.

Policy (cheap heuristics, evaluated top-down):
  cloud_quality when the answer is high-stakes or hard:
    • severity متوسط/شديد
    • fiqh / islamic_parenting domain (precision matters religiously)
    • multi-domain questions (synthesis)
    • long questions or deep conversations
    • weak retrieval (the local 3B can't compensate for thin context)
  otherwise local_fast.

A tiny circuit breaker keeps UX intact when the free cloud tier rate-limits:
after N consecutive cloud failures we route everything local for a
cool-down window. The gateway reports outcomes via record_cloud_result().
"""
from __future__ import annotations

import logging
import threading
import time

from app.config.llm_config import LLM

logger = logging.getLogger(__name__)

_FAILURE_THRESHOLD = 2
_COOLDOWN_SECONDS = 300

_lock = threading.Lock()
_consecutive_failures = 0
_circuit_open_until = 0.0


def record_cloud_result(ok: bool) -> None:
    """Called by the gateway after each cloud-provider attempt."""
    global _consecutive_failures, _circuit_open_until
    with _lock:
        if ok:
            _consecutive_failures = 0
            return
        _consecutive_failures += 1
        if _consecutive_failures >= _FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + _COOLDOWN_SECONDS
            logger.warning(
                "cloud tier circuit OPEN for %ds after %d consecutive failures",
                _COOLDOWN_SECONDS, _consecutive_failures,
            )


def circuit_open() -> bool:
    with _lock:
        return time.monotonic() < _circuit_open_until


def cloud_available() -> bool:
    return bool(
        LLM.cloud_tier_enabled
        and LLM.azure_endpoint
        and LLM.azure_api_key
    )


def choose_tier(
    query_text: str,
    domains: list[str],
    severity: str,
    retrieved_units: list[dict],
    history_len: int = 0,
) -> tuple[str, str]:
    """Returns (tier, reason). tier ∈ {"cloud_quality", "local_fast"}."""
    if not cloud_available():
        return ("local_fast", "cloud_disabled")
    if circuit_open():
        return ("local_fast", "cloud_circuit_open")
    if severity in ("متوسط", "شديد"):
        return ("cloud_quality", f"severity:{severity}")
    if any(d in ("fiqh", "islamic_parenting") for d in domains):
        return ("cloud_quality", "domain:fiqh")
    if len(domains) >= 2:
        return ("cloud_quality", "multi_domain")
    if len(query_text) > 200 or history_len >= 4:
        return ("cloud_quality", "long_or_deep_context")
    distances = [
        u.get("distance") for u in retrieved_units
        if isinstance(u.get("distance"), (int, float))
    ]
    if distances and min(distances) > 0.70:
        return ("cloud_quality", "weak_retrieval")
    return ("local_fast", "default")
