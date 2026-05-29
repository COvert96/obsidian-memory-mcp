from __future__ import annotations

import sqlite3

import pytest

from obsidian_memory_mcp.schema import (
    SCHEMA_VERSION,
    SchemaVersionError,
    bootstrap_schema,
)


class _RollbackTrackingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1
        super().rollback()


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
        "write_audit",
        "blocks_fts",
    }.issubset(tables)
    assert not any(name.startswith("proposal") for name in tables)
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


def test_schema_bootstrap_preserves_files_error_foreign_keys(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "index.sqlite3")

    bootstrap_schema(connection)

    files_foreign_keys = {
        str(row[2]) for row in connection.execute("PRAGMA foreign_key_list('files')")
    }
    index_error_foreign_keys = {
        str(row[2])
        for row in connection.execute("PRAGMA foreign_key_list('index_errors')")
    }

    assert "index_errors" in files_foreign_keys
    assert "files" in index_error_foreign_keys


def test_schema_bootstrap_rejects_unsupported_user_version(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "index.sqlite3")
    connection.execute("PRAGMA user_version = 999")

    with pytest.raises(SchemaVersionError):
        bootstrap_schema(connection)


def test_schema_bootstrap_does_not_rollback_externally_owned_connection(
    tmp_path,
) -> None:
    connection = sqlite3.connect(
        tmp_path / "index.sqlite3",
        factory=_RollbackTrackingConnection,
    )

    bootstrap_schema(connection)

    assert connection.rollback_calls == 0
