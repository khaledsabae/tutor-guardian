"""Consecutive-failure circuit breaker — قاطع الدائرة.

Extracted from tier_router's cloud breaker so a second call site (the
auxiliary LLM tier: domain classifier + query rewriter) gets the same
semantics instead of a hand-rolled copy: N consecutive failures open the
circuit for a cool-down window, any success closes it.

Why it matters here: when a provider host is unreachable, every caller pays
the full connect timeout to rediscover that fact. The breaker turns the
second and later discoveries into 0ms.

Thread-safe — callers run inside asyncio.to_thread worker threads.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Opens after `failure_threshold` consecutive failures, for `cooldown_seconds`."""

    def __init__(self, name: str, *, failure_threshold: int = 2,
                 cooldown_seconds: float = 300.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._open_until = 0.0

    def record(self, ok: bool) -> None:
        """Report one attempt's outcome."""
        with self._lock:
            if ok:
                self._consecutive_failures = 0
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._open_until = time.monotonic() + self.cooldown_seconds
                logger.warning(
                    "%s circuit OPEN for %ds after %d consecutive failures",
                    self.name, int(self.cooldown_seconds), self._consecutive_failures,
                )

    def is_open(self) -> bool:
        """True while the cool-down window is still running — skip the call."""
        with self._lock:
            return time.monotonic() < self._open_until

    def reset(self) -> None:
        """Force the circuit closed (tests, manual recovery)."""
        with self._lock:
            self._consecutive_failures = 0
            self._open_until = 0.0
