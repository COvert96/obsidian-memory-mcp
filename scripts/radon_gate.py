#!/usr/bin/env python3
"""Fail when radon reports cyclomatic complexity grade C+ or MI grade C."""

from __future__ import annotations

import json
import subprocess
import sys

# Modules below this MI are blocked (radon A starts at 20).
WATCH_MI_MIN = 20.0
# Functions at CC grade B with complexity 10 are reported as watch items.
WATCH_CC_MIN = 10


def _run_radon(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "radon", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def _modules_below_mi_threshold() -> list[tuple[str, float]]:
    raw = subprocess.run(
        [sys.executable, "-m", "radon", "mi", "src", "-j"],
        capture_output=True,
        text=True,
        check=False,
    )
    if raw.returncode not in {0, 1}:
        print(raw.stderr or raw.stdout, file=sys.stderr)
        sys.exit(raw.returncode)

    below: list[tuple[str, float]] = []
    for path, metrics in json.loads(raw.stdout or "{}").items():
        mi = float(metrics["mi"])
        if mi < WATCH_MI_MIN:
            below.append((path, mi))
    return sorted(below, key=lambda item: item[1])


def _high_complexity_blocks() -> str:
    return _run_radon("cc", "src", "-n", "B", "-s", "-j")


def main() -> int:
    complexity = _run_radon("cc", "src", "-n", "C", "-s")
    maintainability = _run_radon("mi", "src", "-n", "C", "-s")
    failures = [output for output in (complexity, maintainability) if output]
    if failures:
        print("Radon gate failed:", file=sys.stderr)
        for output in failures:
            print(output, file=sys.stderr)
        return 1

    low_mi = _modules_below_mi_threshold()
    if low_mi:
        print(
            f"Radon gate failed: module maintainability index below {WATCH_MI_MIN}:",
            file=sys.stderr,
        )
        for path, mi in low_mi:
            print(f"  {path}: {mi:.2f}", file=sys.stderr)
        return 1

    watch_cc = json.loads(_high_complexity_blocks() or "{}")
    watch_items = [
        entry
        for entries in watch_cc.values()
        for entry in entries
        if int(entry.get("complexity", 0)) >= WATCH_CC_MIN
    ]
    if watch_items:
        print(
            f"Radon watch: {len(watch_items)} block(s) at cyclomatic complexity "
            f">= {WATCH_CC_MIN} (grade B). Consider refactoring before adding branches.",
            file=sys.stderr,
        )

    print("Radon gate passed (no CC grade C+, no MI grade C, all modules MI >= 20).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
