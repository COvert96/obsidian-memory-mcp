from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.database import connect_index_db
from obsidian_memory_mcp.status import _count, get_index_status


def _config(vault: Path):
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: memory-index.sqlite3
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
    return ConfigLoader(vault).load()


def test_status_reports_health_counts_and_drift(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    first = vault / "wiki" / "first.md"
    second = vault / "wiki" / "second.md"
    first.write_text("# First\nbody", encoding="utf-8")
    second.write_text("# Second\nbody", encoding="utf-8")
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL, parser_version="old")

    second.unlink()
    first.write_text("# First\nchanged", encoding="utf-8")
    (vault / "wiki" / "third.md").write_text("# Third\nnew", encoding="utf-8")

    status = get_index_status(config, parser_version="new")

    assert status.total_markdown_files == 2
    assert status.indexed_files == 2
    assert status.unindexed_files == 1
    assert status.changed_files == 1
    assert status.deleted_indexed_files == 1
    assert status.total_sections == 2
    assert status.total_blocks == 2
    assert status.parser_version_drift == 2
    assert "Parser version drift exists." in status.warnings


def test_status_warns_when_more_than_ten_percent_of_files_have_errors(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "broken.md").write_text(
        "---\n: broken\n---\n# Broken\nbody", encoding="utf-8"
    )
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    status = get_index_status(config)

    assert status.files_with_errors == 1
    assert any("indexing errors" in warning for warning in status.warnings)


def test_status_reports_alembic_head_revision(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\nbody", encoding="utf-8")
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    status = get_index_status(config)

    assert status.schema_revision == "002_remove_proposals"


def test_count_rejects_unrecognized_table_names(
    tmp_path: Path, migrated_index_db: Path
) -> None:
    connection = connect_index_db(migrated_index_db)
    try:
        with pytest.raises(ValueError, match="Invalid count table"):
            _count(connection, "files; DROP TABLE files")
    finally:
        connection.close()
