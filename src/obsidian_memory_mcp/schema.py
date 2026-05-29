"""SQLite schema bootstrap for the derived markdown index."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool

from obsidian_memory_mcp.database._tables import create_fts_tables, metadata

# TODO(phase-7b): Remove once Alembic owns schema versioning.
SCHEMA_VERSION = 4
SUPPORTED_SCHEMA_VERSIONS = frozenset({0, 2, 3, SCHEMA_VERSION})

_BOOTSTRAPPED_SCHEMA_PATHS: set[Path] = set()
_SCHEMA_BOOTSTRAP_LOCK = Lock()


class SchemaVersionError(RuntimeError):
    # TODO(phase-7b): Remove once Alembic owns migration/version errors.
    """Raised when an existing index database has an unsupported schema version."""


def connect_index_db(index_db_path: Path) -> sqlite3.Connection:
    index_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(index_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if index_db_path.name != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def bootstrap_schema(connection: sqlite3.Connection | Connection | Engine) -> None:
    """Bootstrap or validate the index schema."""
    sa_connection, cleanup = _sqlalchemy_connection(connection)
    current_version = _user_version(sa_connection)
    if current_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SchemaVersionError(
            f"Unsupported index schema version {current_version}; expected {SCHEMA_VERSION}."
        )

    try:
        metadata.create_all(bind=sa_connection)
        create_fts_tables(sa_connection)
        sa_connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
        sa_connection.commit()
    finally:
        cleanup()


def bootstrap_schema_once(
    connection: sqlite3.Connection,
    index_db_path: Path,
    *,
    database_existed: bool,
) -> None:
    """Bootstrap the schema at most once per resolved database path.

    Relocated from the deleted ``proposals`` package in Phase 8c; the retained
    ``write_audit`` repository is the sole caller. Retiring this runtime path so
    Alembic is the sole schema owner is tracked as Phase 8d.
    """
    if index_db_path.name == ":memory:":
        bootstrap_schema(connection)
        return

    cache_key = index_db_path.resolve(strict=False)
    with _SCHEMA_BOOTSTRAP_LOCK:
        if database_existed and cache_key in _BOOTSTRAPPED_SCHEMA_PATHS:
            return
        bootstrap_schema(connection)
        _BOOTSTRAPPED_SCHEMA_PATHS.add(cache_key)


def _user_version(connection: Connection) -> int:
    return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


class _NonClosingSQLiteConnection:
    def __init__(self, wrapped: sqlite3.Connection):
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def close(self) -> None:
        return None


def _sqlalchemy_connection(
    connection: sqlite3.Connection | Connection | Engine,
) -> tuple[Connection, Callable[[], None]]:
    if isinstance(connection, Connection):
        return connection, _noop
    if isinstance(connection, Engine):
        sa_connection = connection.connect()

        def _cleanup_engine_connection() -> None:
            sa_connection.close()

        return sa_connection, _cleanup_engine_connection

    proxy = _NonClosingSQLiteConnection(connection)
    engine = create_engine(
        "sqlite+pysqlite://",
        creator=lambda: proxy,
        poolclass=StaticPool,
        pool_reset_on_return=None,
        isolation_level="AUTOCOMMIT",
        skip_autocommit_rollback=True,
    )
    sa_connection = engine.connect()

    def _cleanup() -> None:
        sa_connection.close()
        engine.dispose()

    return sa_connection, _cleanup


def _noop() -> None:
    return None
