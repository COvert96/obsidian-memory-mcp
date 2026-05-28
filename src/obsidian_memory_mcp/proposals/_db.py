"""Shared database bootstrap cache for proposal-related workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from obsidian_memory_mcp.schema import bootstrap_schema

_BOOTSTRAPPED_SCHEMA_PATHS: set[Path] = set()
_SCHEMA_BOOTSTRAP_LOCK = Lock()


def bootstrap_schema_once(
    connection: sqlite3.Connection,
    index_db_path: Path,
    *,
    database_existed: bool,
) -> None:
    if index_db_path.name == ":memory:":
        bootstrap_schema(connection)
        return

    cache_key = index_db_path.resolve(strict=False)
    with _SCHEMA_BOOTSTRAP_LOCK:
        if database_existed and cache_key in _BOOTSTRAPPED_SCHEMA_PATHS:
            return
        bootstrap_schema(connection)
        _BOOTSTRAPPED_SCHEMA_PATHS.add(cache_key)
