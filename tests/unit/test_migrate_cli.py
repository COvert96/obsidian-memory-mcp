from __future__ import annotations

import sqlite3
from pathlib import Path

from obsidian_memory_mcp.cli import main


def _write_config(
    vault: Path, *, index_db_location: str = "memory-index.sqlite3"
) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: {index_db_location}
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )


def _table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
            )
        }


def test_migrate_cli_applies_initial_migration_on_fresh_database(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    database_path = vault / "memory-index.sqlite3"

    exit_code = main(["migrate", str(vault)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Applied 1 migration(s)." in output
    assert {
        "alembic_version",
        "files",
        "blocks_fts",
        "write_audit",
    }.issubset(_table_names(database_path))


def test_migrate_cli_stamps_existing_v010_schema_without_running_upgrade(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    database_path = vault / "memory-index.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE files (id INTEGER PRIMARY KEY)")

    exit_code = main(["migrate", str(vault)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Stamped existing schema as current version." in output
    with sqlite3.connect(database_path) as connection:
        stamped = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert stamped is not None


def test_migrate_cli_reports_already_at_head_for_versioned_database(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)

    assert main(["migrate", str(vault)]) == 0
    _ = capsys.readouterr()

    exit_code = main(["migrate", str(vault)])

    assert exit_code == 0
    assert "Already at head." in capsys.readouterr().out


def test_migrate_cli_defaults_to_current_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault)
    monkeypatch.chdir(vault)

    exit_code = main(["migrate"])

    assert exit_code == 0


def test_migrate_cli_help_documents_the_three_auto_detect_cases(capsys) -> None:
    assert main(["migrate", "--help"]) == 0
    output = capsys.readouterr().out

    assert "alembic_version absent and files table present" in output
    assert "alembic_version absent and files table absent" in output
    assert "alembic_version table present" in output


def test_migrate_cli_exits_non_zero_when_migration_fails(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_config(vault, index_db_location=".")

    exit_code = main(["migrate", str(vault)])

    assert exit_code == 1
    assert "Migration failed:" in capsys.readouterr().out
