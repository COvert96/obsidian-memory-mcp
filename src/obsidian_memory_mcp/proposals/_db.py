"""Shared database bootstrap cache for proposal-related workflows."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool

from obsidian_memory_mcp.database._tables import create_fts_tables, metadata
from obsidian_memory_mcp.schema import SCHEMA_VERSION

_BOOTSTRAPPED_SCHEMA_PATHS: set[Path] = set()
_SCHEMA_BOOTSTRAP_LOCK = Lock()


def bootstrap_schema_once(
    connection: sqlite3.Connection,
    index_db_path: Path,
    *,
    database_existed: bool,
) -> None:
    if index_db_path.name == ":memory:":
        bind, cleanup = _connection_bind(connection)
        try:
            _bootstrap_with_bind(bind)
        finally:
            cleanup()
        return

    cache_key = index_db_path.resolve(strict=False)
    with _SCHEMA_BOOTSTRAP_LOCK:
        if database_existed and cache_key in _BOOTSTRAPPED_SCHEMA_PATHS:
            return
        bind, cleanup = _connection_bind(connection)
        try:
            _bootstrap_with_bind(bind)
        finally:
            cleanup()
        _BOOTSTRAPPED_SCHEMA_PATHS.add(cache_key)


def _bootstrap_with_bind(bind: Engine | Connection) -> None:
    if isinstance(bind, Engine):
        with bind.connect() as connection:
            _create_schema(connection)
        return
    _create_schema(bind)


def _create_schema(connection: Connection) -> None:
    metadata.create_all(bind=connection)
    create_fts_tables(connection)
    connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def _connection_bind(
    connection: sqlite3.Connection,
) -> tuple[Connection, Callable[[], None]]:
    proxy = _NonClosingSQLiteConnection(connection)
    engine = create_engine(
        "sqlite+pysqlite://",
        creator=lambda: proxy,
        poolclass=StaticPool,
    )
    sa_connection = engine.connect()

    def _cleanup() -> None:
        sa_connection.close()
        engine.dispose()

    return sa_connection, _cleanup


class _NonClosingSQLiteConnection:
    def __init__(self, wrapped: sqlite3.Connection):
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def close(self) -> None:
        return None
