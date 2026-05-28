"""Canonical content-hash helpers shared by read and write paths.

`read_note` and `WriteService.update()` must agree on how a file's
`content_hash` is computed, or optimistic-lock conflict detection silently
breaks.  Both compute the SHA-256 of the *raw file bytes* — never of decoded,
newline-normalized text — so this module is the single source of that algorithm.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of `data`."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the raw bytes on disk at `path`."""
    return sha256_bytes(path.read_bytes())
