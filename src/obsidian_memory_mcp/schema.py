"""SQLite schema bootstrap for the derived markdown index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2


class SchemaVersionError(RuntimeError):
    """Raised when an existing index database has an unsupported schema version."""


def connect_index_db(index_db_path: Path) -> sqlite3.Connection:
    index_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(index_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if index_db_path.name != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")
    return connection


def bootstrap_schema(connection: sqlite3.Connection) -> None:
    """Bootstrap or validate the index schema.

    Call this outside an active transaction. sqlite3 executescript() commits any
    pending transaction before running the DDL below.
    """

    current_version = _user_version(connection)
    if current_version not in (0, SCHEMA_VERSION):
        raise SchemaVersionError(
            f"Unsupported index schema version {current_version}; expected {SCHEMA_VERSION}."
        )

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            parser_version TEXT NOT NULL,
            files_seen INTEGER NOT NULL DEFAULT 0,
            files_processed INTEGER NOT NULL DEFAULT 0,
            files_skipped INTEGER NOT NULL DEFAULT 0,
            files_deleted INTEGER NOT NULL DEFAULT 0,
            files_failed INTEGER NOT NULL DEFAULT 0,
            sections_indexed INTEGER NOT NULL DEFAULT 0,
            blocks_indexed INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_path TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            file_hash TEXT,
            raw_content_hash TEXT,
            normalized_content_hash TEXT,
            parser_version TEXT NOT NULL,
            indexed_at TEXT NOT NULL,
            deleted_at TEXT,
            last_run_id INTEGER,
            last_error_id INTEGER,
            FOREIGN KEY(last_run_id) REFERENCES index_runs(id),
            FOREIGN KEY(last_error_id) REFERENCES index_errors(id)
        );

        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            vault_path TEXT NOT NULL,
            section_key TEXT NOT NULL UNIQUE,
            section_path TEXT NOT NULL,
            heading TEXT,
            heading_slug TEXT NOT NULL,
            heading_ordinal INTEGER NOT NULL,
            level INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            vault_path TEXT NOT NULL,
            section_key TEXT NOT NULL,
            section_path TEXT NOT NULL,
            block_key TEXT NOT NULL UNIQUE,
            heading TEXT,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            token_count_estimate INTEGER NOT NULL,
            ordinal INTEGER NOT NULL,
            tags TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wikilinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            vault_path TEXT NOT NULL,
            section_key TEXT NOT NULL,
            target TEXT NOT NULL,
            alias TEXT,
            raw TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS index_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            file_id INTEGER,
            vault_path TEXT,
            error_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES index_runs(id),
            FOREIGN KEY(file_id) REFERENCES files(id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
            block_key UNINDEXED,
            vault_path UNINDEXED,
            section_path,
            heading,
            content,
            tags
        );

        CREATE INDEX IF NOT EXISTS idx_files_freshness
            ON files(vault_path, size_bytes, mtime_ns, parser_version, deleted_at);
        CREATE INDEX IF NOT EXISTS idx_sections_file_id
            ON sections(file_id);
        CREATE INDEX IF NOT EXISTS idx_blocks_file_id
            ON blocks(file_id);
        CREATE INDEX IF NOT EXISTS idx_blocks_section_id
            ON blocks(section_id);
        CREATE INDEX IF NOT EXISTS idx_wikilinks_target
            ON wikilinks(target);
        CREATE INDEX IF NOT EXISTS idx_wikilinks_file_id
            ON wikilinks(file_id);
        CREATE INDEX IF NOT EXISTS idx_index_errors_run_id
            ON index_errors(run_id);
        CREATE INDEX IF NOT EXISTS idx_index_errors_file_id
            ON index_errors(file_id);
        """
    )
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def _user_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])
