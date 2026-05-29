from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from alembic import command

from obsidian_memory_mcp.migrations import (
    MigrationError,
    MigrationOutcome,
    InstallState,
    _alembic_config,
    _default_alembic_ini_path,
    _find_project_root,
    _schema_matches_head,
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


def test_ensure_index_migrated_creates_full_schema_on_fresh_path(
    tmp_path: Path,
) -> None:
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
    )

    with patch(
        "obsidian_memory_mcp.migrations.migrate_index_database",
        return_value=outcome,
    ) as migrate:
        ensure_index_migrated(database_path)
        ensure_index_migrated(database_path)

    migrate.assert_called_once_with(database_path, alembic_ini_path=None)


def _legacy_schema_missing_write_audit(database_path: Path) -> None:
    config = _alembic_config(database_path, _default_alembic_ini_path())
    command.upgrade(config, "001_initial_schema")
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE alembic_version")
        connection.execute("DROP TABLE write_audit")
        connection.commit()


def test_ensure_index_migrated_upgrades_legacy_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    _legacy_schema_missing_write_audit(database_path)

    ensure_index_migrated(database_path)

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
            )
        }

    assert revision is not None
    assert revision[0] == "002_remove_proposals"
    assert "write_audit" in tables


def test_migrate_repairs_versioned_database_stamped_without_full_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "stamped.sqlite3"
    config = _alembic_config(database_path, _default_alembic_ini_path())
    command.upgrade(config, "001_initial_schema")
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE write_audit")
        connection.execute(
            "UPDATE alembic_version SET version_num = '002_remove_proposals'"
        )
        connection.commit()

    assert not _schema_matches_head(database_path)

    migrate_index_database(database_path)

    assert _schema_matches_head(database_path)
    with sqlite3.connect(database_path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "write_audit" in tables
    assert not any(name.startswith("proposal") for name in tables)
