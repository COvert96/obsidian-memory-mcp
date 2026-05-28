"""SQLite persistence for the append-only write_audit log."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.pool import StaticPool

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.database._tables import write_audit
from obsidian_memory_mcp.proposals._db import bootstrap_schema_once
from obsidian_memory_mcp.schema import connect_index_db
from obsidian_memory_mcp.writes._models import WriteAuditEntry


class WriteAuditRepository:
    """Append and query write_audit rows in the configured index database.

    Each call opens, bootstraps, and closes its own connection — mirroring the
    proposal repositories' use of the configured index DB location.
    """

    def __init__(self, config: ProjectConfig) -> None:
        self._config = config

    def append(self, entry: WriteAuditEntry) -> None:
        with self._connection() as connection:
            connection.execute(
                insert(write_audit).values(
                    occurred_at=_to_iso(entry.occurred_at),
                    tool=entry.tool,
                    project=entry.project,
                    file_path=entry.file_path,
                    operation=entry.operation,
                    content_hash=entry.content_hash,
                    supersedes=entry.supersedes,
                )
            )
            connection.commit()

    def list(
        self,
        *,
        project: str | None = None,
        file_path: str | None = None,
        limit: int = 50,
    ) -> tuple[WriteAuditEntry, ...]:
        statement = select(write_audit)
        if project is not None:
            statement = statement.where(write_audit.c.project == project)
        if file_path is not None:
            statement = statement.where(write_audit.c.file_path == file_path)
        statement = statement.order_by(write_audit.c.id.desc()).limit(limit)
        with self._connection() as connection:
            rows = connection.execute(statement).mappings().all()
        return tuple(_entry_from_row(row) for row in rows)

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        index_db_path = self._config.index_db_location
        database_existed = index_db_path.exists()
        raw_connection = connect_index_db(index_db_path)
        try:
            bootstrap_schema_once(
                raw_connection,
                index_db_path,
                database_existed=database_existed,
            )
            engine = create_engine(
                "sqlite+pysqlite://",
                creator=lambda: _NonClosingSQLiteConnection(raw_connection),
                poolclass=StaticPool,
                pool_reset_on_return=None,
            )
            connection = engine.connect()
            try:
                yield connection
            finally:
                connection.close()
                engine.dispose()
        finally:
            raw_connection.close()


class _NonClosingSQLiteConnection:
    """Adapt a sqlite3 connection for SQLAlchemy without ceding its lifecycle."""

    def __init__(self, wrapped: sqlite3.Connection) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def close(self) -> None:
        return None


def _entry_from_row(row: Any) -> WriteAuditEntry:
    return WriteAuditEntry(
        occurred_at=_from_iso(str(row["occurred_at"])),
        tool=str(row["tool"]),
        project=str(row["project"]),
        file_path=str(row["file_path"]),
        operation=str(row["operation"]),
        content_hash=(
            str(row["content_hash"]) if row["content_hash"] is not None else None
        ),
        supersedes=str(row["supersedes"]) if row["supersedes"] is not None else None,
    )


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)
