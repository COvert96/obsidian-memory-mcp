from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.migrations import MigrationError, _alembic_config, _find_project_root


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


def test_alembic_config_uses_script_location_relative_to_ini_path(tmp_path: Path) -> None:
    migration_root = tmp_path / "custom-layout"
    migration_root.mkdir()
    alembic_ini = migration_root / "alembic.ini"
    alembic_ini.write_text("[alembic]\n", encoding="utf-8")
    (migration_root / "alembic").mkdir()

    config = _alembic_config(tmp_path / "index.sqlite3", alembic_ini)

    assert Path(config.get_main_option("script_location")) == migration_root / "alembic"
