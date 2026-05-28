"""Alembic migration orchestration for vault index databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import Script, ScriptDirectory
from sqlalchemy.engine import URL

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


class InstallState(Enum):
    LEGACY_SCHEMA = "legacy_schema"
    FRESH_DATABASE = "fresh_database"
    VERSIONED_DATABASE = "versioned_database"


@dataclass(frozen=True)
class MigrationOutcome:
    install_state: InstallState
    applied_migration_count: int
    stamped_existing_schema: bool


class MigrationError(RuntimeError):
    """Raised when Alembic migration setup or execution fails."""


def migrate_index_database(
    index_db_path: Path,
    *,
    alembic_ini_path: Path = _ALEMBIC_INI,
) -> MigrationOutcome:
    try:
        install_state = detect_install_state(index_db_path)
        config = _alembic_config(index_db_path, alembic_ini_path)

        if install_state is InstallState.LEGACY_SCHEMA:
            command.stamp(config, "head")
            return MigrationOutcome(
                install_state=install_state,
                applied_migration_count=0,
                stamped_existing_schema=True,
            )

        pending_count = _pending_migration_count(config, index_db_path)
        command.upgrade(config, "head")
        return MigrationOutcome(
            install_state=install_state,
            applied_migration_count=pending_count,
            stamped_existing_schema=False,
        )
    except MigrationError:
        raise
    except Exception as error:  # pragma: no cover - defensive translation path
        raise MigrationError(str(error)) from error


def detect_install_state(index_db_path: Path) -> InstallState:
    index_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(index_db_path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    has_alembic_version = "alembic_version" in tables
    has_files_table = "files" in tables
    if not has_alembic_version and has_files_table:
        return InstallState.LEGACY_SCHEMA
    if not has_alembic_version:
        return InstallState.FRESH_DATABASE
    return InstallState.VERSIONED_DATABASE


def _alembic_config(index_db_path: Path, alembic_ini_path: Path) -> Config:
    if not alembic_ini_path.exists():
        raise MigrationError(f"Alembic config file not found at '{alembic_ini_path}'.")

    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    config.attributes["index_db_location"] = str(index_db_path)
    config.set_main_option(
        "sqlalchemy.url",
        URL.create("sqlite+pysqlite", database=str(index_db_path)).render_as_string(
            hide_password=False
        ),
    )
    return config


def _pending_migration_count(config: Config, index_db_path: Path) -> int:
    current_revision = _current_revision(index_db_path)
    script_directory = ScriptDirectory.from_config(config)
    heads = script_directory.get_heads()

    if len(heads) != 1:
        raise MigrationError(
            "Expected exactly one Alembic head revision; branching is unsupported."
        )

    head_revision = heads[0]
    if current_revision == head_revision:
        return 0

    lineage = _linear_lineage(script_directory, head_revision)
    if current_revision is None:
        return len(lineage)
    if current_revision not in lineage:
        raise MigrationError(
            f"Current database revision '{current_revision}' is not in migration lineage."
        )
    return len(lineage) - lineage.index(current_revision) - 1


def _current_revision(index_db_path: Path) -> str | None:
    with sqlite3.connect(index_db_path) as connection:
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='alembic_version'
            LIMIT 1
            """
        ).fetchone()
        if table_exists is None:
            return None

        version_rows = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT version_num
                FROM alembic_version
                ORDER BY version_num
                """
            )
        )

    if not version_rows:
        return None
    if len(version_rows) > 1:
        raise MigrationError(
            "Multiple rows found in alembic_version; branching migrations are unsupported."
        )
    return version_rows[0]


def _linear_lineage(script_directory: ScriptDirectory, head_revision: str) -> list[str]:
    lineage_from_head: list[str] = []
    current: str | None = head_revision

    while current is not None:
        script = script_directory.get_revision(current)
        if script is None:
            raise MigrationError(f"Missing Alembic revision '{current}'.")
        lineage_from_head.append(script.revision)
        current = _next_down_revision(script)

    lineage_from_head.reverse()
    return lineage_from_head


def _next_down_revision(script: Script) -> str | None:
    down_revision = script.down_revision
    if down_revision is None:
        return None
    if isinstance(down_revision, tuple):
        raise MigrationError(
            "Merge revisions are unsupported for migration-count reporting."
        )
    return str(down_revision)
