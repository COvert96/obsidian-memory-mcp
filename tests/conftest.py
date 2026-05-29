"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from obsidian_memory_mcp.migrations import ensure_index_migrated


@pytest.fixture()
def migrated_index_db(tmp_path: Path) -> Iterator[Path]:
    """Create a temp file index DB migrated to Alembic head."""
    database_path = tmp_path / "index.sqlite3"
    ensure_index_migrated(database_path)
    yield database_path
