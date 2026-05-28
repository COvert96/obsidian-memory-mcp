from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL
from sqlalchemy.exc import SAWarning


def _find_repo_root(start_path: Path) -> Path:
    search_root = start_path if start_path.is_dir() else start_path.parent
    for candidate in (search_root, *search_root.parents):
        if (candidate / "alembic.ini").is_file() and (candidate / "alembic").is_dir():
            return candidate
    raise RuntimeError("Unable to locate repository root for Alembic tests.")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def _alembic_config(database_path: Path) -> Config:
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        URL.create("sqlite+pysqlite", database=str(database_path)).render_as_string(
            hide_password=False
        ),
    )
    return config


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
        )
    }


def _index_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }


def test_alembic_upgrade_head_creates_full_schema_on_blank_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "index.sqlite3"
    config = _alembic_config(database_path)

    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        tables = _table_names(connection)
        indexes = _index_names(connection)
        stamped = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert {
        "index_runs",
        "files",
        "sections",
        "blocks",
        "wikilinks",
        "index_errors",
        "proposals",
        "proposal_events",
        "proposal_changesets",
        "proposal_changeset_members",
        "proposal_changeset_events",
        "write_audit",
        "blocks_fts",
        "alembic_version",
    }.issubset(tables)
    assert {
        "idx_files_freshness",
        "idx_sections_file_id",
        "idx_blocks_file_id",
        "idx_blocks_section_id",
        "idx_wikilinks_target",
        "idx_wikilinks_file_id",
        "idx_index_errors_run_id",
        "idx_index_errors_file_id",
        "idx_proposals_status_created",
        "idx_proposals_file_path",
        "idx_proposals_created",
        "idx_proposal_events_proposal_id",
        "idx_proposal_changesets_status_created",
        "idx_proposal_changeset_members_changeset",
        "idx_proposal_changeset_members_proposal",
        "idx_proposal_changeset_events_changeset_id",
    }.issubset(indexes)
    assert stamped is not None


def test_alembic_check_passes_after_head_is_applied(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    config = _alembic_config(database_path)
    command.upgrade(config, "head")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        command.check(config)

    cycle_warnings = [
        warning
        for warning in caught
        if (
            issubclass(warning.category, SAWarning)
            and "Cannot correctly sort tables" in str(warning.message)
        )
    ]
    assert cycle_warnings == []


def test_initial_migration_can_run_again_when_tables_already_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    config = _alembic_config(database_path)
    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE alembic_version")
        connection.commit()

    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        stamped = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert stamped is not None


def test_alembic_downgrade_drops_schema_objects(tmp_path: Path) -> None:
    database_path = tmp_path / "index.sqlite3"
    config = _alembic_config(database_path)
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    with sqlite3.connect(database_path) as connection:
        tables = _table_names(connection)

    assert "blocks_fts" not in tables
    assert "files" not in tables
    assert "write_audit" not in tables
