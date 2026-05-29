from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.database import engine_for, metadata


def test_engine_for_memory_enables_foreign_keys() -> None:
    engine = engine_for(":memory:")

    with engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        connection.exec_driver_sql("CREATE TABLE keepalive (id INTEGER PRIMARY KEY)")

    with engine.connect() as connection:
        table_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='keepalive'"
        ).scalar_one()

    assert int(foreign_keys) == 1
    assert int(table_count) == 1


def test_engine_for_file_sets_wal_mode_on_multiple_checkouts(tmp_path: Path) -> None:
    engine = engine_for(tmp_path / "index.sqlite3")

    with engine.connect() as first_connection:
        first_mode = first_connection.exec_driver_sql(
            "PRAGMA journal_mode"
        ).scalar_one()
    with engine.connect() as second_connection:
        second_mode = second_connection.exec_driver_sql(
            "PRAGMA journal_mode"
        ).scalar_one()

    assert str(first_mode).lower() == "wal"
    assert str(second_mode).lower() == "wal"


def test_metadata_create_all_is_idempotent(tmp_path: Path) -> None:
    engine = engine_for(tmp_path / "index.sqlite3")

    metadata.create_all(bind=engine)
    metadata.create_all(bind=engine)

    with engine.connect() as connection:
        table_names = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {
        "index_runs",
        "files",
        "sections",
        "blocks",
        "wikilinks",
        "index_errors",
        "write_audit",
    }.issubset(table_names)
    assert not any(name.startswith("proposal") for name in table_names)
