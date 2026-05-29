"""Canonical content-hash helpers shared by read and write paths."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of `data`."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the raw bytes on disk at `path`."""
    return sha256_bytes(path.read_bytes())
