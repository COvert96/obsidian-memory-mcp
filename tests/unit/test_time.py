from __future__ import annotations

import time

from obsidian_memory_mcp._time import duration_ms


def test_duration_ms_never_returns_negative_values() -> None:
    started_in_future = time.perf_counter() + 1.0
    assert duration_ms(started_in_future) == 0

