from __future__ import annotations

import sqlite3

import pytest

from obsidian_memory_mcp.schema import (
    SCHEMA_VERSION,
    SchemaVersionError,
    bootstrap_schema,
)


def test_schema_bootstrap_creates_required_tables_indexes_and_user_version(
    tmp_path,
) -> None:
    connection = sqlite3.connect(tmp_path / "index.sqlite3")

    bootstrap_schema(connection)

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
        )
    }
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert {
        "index_runs",
        "files",
        "sections",
        "blocks",
        "wikilinks",
        "index_errors",
        "blocks_fts",
    }.issubset(tables)
    assert {
        "idx_files_freshness",
        "idx_sections_file_id",
        "idx_blocks_section_id",
        "idx_wikilinks_target",
        "idx_index_errors_run_id",
    }.issubset(indexes)
    assert user_version == SCHEMA_VERSION


def test_schema_creation_is_idempotent(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "index.sqlite3")

    bootstrap_schema(connection)
    bootstrap_schema(connection)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_schema_bootstrap_rejects_unsupported_user_version(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "index.sqlite3")
    connection.execute("PRAGMA user_version = 999")

    with pytest.raises(SchemaVersionError):
        bootstrap_schema(connection)
