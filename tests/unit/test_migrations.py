from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from obsidian_memory_mcp.migrations import (
    MigrationError,
    MigrationOutcome,
    InstallState,
    _alembic_config,
    _find_project_root,
    ensure_index_migrated,
    migrate_index_database,
)


def test_find_project_root_walks_up_to_repository_layout(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    nested_module = repository_root / "src" / "obsidian_memory_mcp" / "migrations.py"
    nested_module.parent.mkdir(parents=True)
    nested_module.touch()
    (repository_root / "alembic").mkdir()
    (repository_root / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    resolved = _find_project_root(nested_module)

    assert resolved == repository_root


def test_find_project_root_raises_when_layout_is_missing(tmp_path: Path) -> None:
    missing_layout_path = tmp_path / "src" / "obsidian_memory_mcp" / "migrations.py"

    with pytest.raises(MigrationError):
        _find_project_root(missing_layout_path)


def test_alembic_config_uses_script_location_relative_to_ini_path(
    tmp_path: Path,
) -> None:
    migration_root = tmp_path / "custom-layout"
    migration_root.mkdir()
    alembic_ini = migration_root / "alembic.ini"
    alembic_ini.write_text("[alembic]\n", encoding="utf-8")
    (migration_root / "alembic").mkdir()

    config = _alembic_config(tmp_path / "index.sqlite3", alembic_ini)

    assert Path(config.get_main_option("script_location")) == migration_root / "alembic"


def test_ensure_index_migrated_creates_full_schema_on_fresh_path(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"

    ensure_index_migrated(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
            )
        }
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert "files" in tables
    assert "write_audit" in tables
    assert revision is not None
    assert revision[0] == "002_remove_proposals"


def test_ensure_index_migrated_is_noop_when_already_at_head(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    ensure_index_migrated(database_path)

    with patch(
        "obsidian_memory_mcp.migrations.migrate_index_database",
        wraps=migrate_index_database,
    ) as migrate:
        ensure_index_migrated(database_path)

    migrate.assert_not_called()


def test_ensure_index_migrated_runs_migrate_only_once_per_path(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    outcome = MigrationOutcome(
        install_state=InstallState.FRESH_DATABASE,
        applied_migration_count=1,
        stamped_existing_schema=False,
    )

    with patch(
        "obsidian_memory_mcp.migrations.migrate_index_database",
        return_value=outcome,
    ) as migrate:
        ensure_index_migrated(database_path)
        ensure_index_migrated(database_path)

    migrate.assert_called_once_with(database_path, alembic_ini_path=None)


def test_ensure_index_migrated_stamps_legacy_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                vault_path TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.commit()

    ensure_index_migrated(database_path)

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert revision is not None
    assert revision[0] == "002_remove_proposals"
