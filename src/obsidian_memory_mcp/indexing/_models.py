"""Data models for indexing workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class IndexMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"


@dataclass(frozen=True)
class IndexRunResult:
    index_run_id: int
    mode: str
    status: str
    files_seen: int
    files_processed: int
    files_skipped: int
    files_deleted: int
    files_failed: int
    sections_indexed: int
    blocks_indexed: int
    errors: int
    duration_ms: int


@dataclass(frozen=True)
class FileCandidate:
    vault_path: str
    absolute_path: Path
    size_bytes: int
    mtime_ns: int


@dataclass
class _RunStats:
    files_seen: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_deleted: int = 0
    files_failed: int = 0
    sections_indexed: int = 0
    blocks_indexed: int = 0
    errors: int = 0


@dataclass(frozen=True)
class _FileIndexError:
    error_type: str
    message: str
