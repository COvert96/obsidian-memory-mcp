"""SQLAlchemy engine and connection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.pool import StaticPool


class _CursorProtocol(Protocol):
    def execute(self, statement: str) -> object: ...

    def close(self) -> None: ...


@runtime_checkable
class _DBAPIConnectionProtocol(Protocol):
    def cursor(self) -> _CursorProtocol: ...


def engine_for(path: Path | str) -> Engine:
    database_path = str(path)
    in_memory = database_path == ":memory:"

    kwargs: dict[str, object] = {}
    if in_memory:
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(
        URL.create("sqlite+pysqlite", database=database_path),
        **kwargs,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite_pragmas(
        dbapi_connection: object, connection_record: object
    ) -> None:  # noqa: ARG001
        if not isinstance(dbapi_connection, _DBAPIConnectionProtocol):
            raise TypeError("Expected DBAPI connection with cursor().")
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            if not in_memory:
                cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine


def get_connection(path: Path | str) -> Connection:
    return engine_for(path).connect()
