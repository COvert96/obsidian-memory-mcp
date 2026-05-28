"""Internal helpers for monotonic timing."""

from __future__ import annotations

import time


def duration_ms(started: float) -> int:
    """Return non-negative elapsed milliseconds since a perf_counter timestamp."""
    return max(0, int((time.perf_counter() - started) * 1000))
