"""Guard that Alembic head DDL stays aligned with SQLAlchemy Core metadata.

``metadata`` in ``database/_tables.py`` no longer creates the persistent schema;
this test is the safety net that keeps Core query models honest against
migration DDL.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import URL
from sqlalchemy.exc import SAWarning

from alembic import command


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


def test_migrated_schema_matches_metadata_at_head(tmp_path: Path) -> None:
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
