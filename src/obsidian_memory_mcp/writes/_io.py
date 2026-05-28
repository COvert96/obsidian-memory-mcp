"""Atomic file write primitives — no domain imports."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def atomic_write(path: Path, content_bytes: bytes) -> None:
    """Write content_bytes to path atomically using temp file + os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_bytes(content_bytes)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
