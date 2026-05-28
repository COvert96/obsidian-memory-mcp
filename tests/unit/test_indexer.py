from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.parser import PARSER_VERSION
from obsidian_memory_mcp.search_debug import debug_search


def _write_config(vault: Path) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
    deny: [".trash/**"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )


@pytest.fixture()
def index_config(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki").mkdir()
    (vault / ".mcp").mkdir()
    _write_config(vault)
    return ConfigLoader(vault).load()


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def test_incremental_lifecycle_handles_skip_change_tombstone_reappearance_and_fts_sync(
    index_config,
) -> None:
    alpha = index_config.vault_path / "wiki" / "alpha.md"
    beta = index_config.vault_path / "wiki" / "beta.md"
    alpha.write_text("# Alpha\noriginal alpha", encoding="utf-8")
    beta.write_text("# Beta\noriginal beta", encoding="utf-8")

    initial = run_index(index_config, mode=IndexMode.FULL)
    unchanged = run_index(index_config)
    alpha.write_text("# Alpha\nchanged alpha", encoding="utf-8")
    changed = run_index(index_config)
    beta.unlink()
    deleted = run_index(index_config)
    beta.write_text("# Beta\nreturned beta", encoding="utf-8")
    reappeared = run_index(index_config)

    connection = _connect(index_config.index_db_location)
    beta_row = connection.execute(
        "SELECT deleted_at FROM files WHERE vault_path = 'wiki/beta.md'"
    ).fetchone()
    orphaned_fts_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM blocks_fts
        LEFT JOIN blocks ON blocks.block_key = blocks_fts.block_key
        WHERE blocks.block_key IS NULL
        """
    ).fetchone()[0]

    assert initial.status == "success"
    assert initial.files_processed == 2
    assert unchanged.files_skipped == 2
    assert changed.files_processed == 1
    assert deleted.files_deleted == 1
    assert reappeared.files_processed == 1
    assert beta_row["deleted_at"] is None
    assert orphaned_fts_rows == 0
    assert (
        debug_search(index_config, "changed", limit=5)[0].vault_path == "wiki/alpha.md"
    )
    assert debug_search(index_config, "original", limit=5) == ()


def test_metadata_drift_with_unchanged_file_hash_updates_stat_without_reparse(
    index_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    note = index_config.vault_path / "wiki" / "alpha.md"
    note.write_text("# Alpha\nsame body", encoding="utf-8")
    run_index(index_config, mode=IndexMode.FULL)

    next_mtime = note.stat().st_mtime + 10
    os.utime(note, (next_mtime, next_mtime))

    def fail_if_parsed(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("unchanged content should not be reparsed")

    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.parse_markdown_bytes", fail_if_parsed
    )

    result = run_index(index_config)

    assert result.files_skipped == 1


def test_parser_version_change_triggers_reindex(index_config) -> None:
    note = index_config.vault_path / "wiki" / "alpha.md"
    note.write_text("# Alpha\nbody", encoding="utf-8")
    run_index(index_config, mode=IndexMode.FULL, parser_version="old")

    result = run_index(index_config, parser_version=PARSER_VERSION)

    assert result.files_processed == 1


def test_malformed_yaml_counts_as_processed_with_error_not_failed(index_config) -> None:
    note = index_config.vault_path / "wiki" / "alpha.md"
    note.write_text("---\n: broken\n---\n# Alpha\nbody", encoding="utf-8")

    result = run_index(index_config, mode=IndexMode.FULL)

    assert result.status == "success_with_errors"
    assert result.files_processed == 1
    assert result.files_failed == 0
    assert result.errors == 1


def test_nonfatal_file_error_does_not_abort_whole_run(
    index_config, monkeypatch
) -> None:
    good = index_config.vault_path / "wiki" / "good.md"
    bad = index_config.vault_path / "wiki" / "bad.md"
    good.write_text("# Good\nbody", encoding="utf-8")
    bad.write_text("# Bad\nbody", encoding="utf-8")

    def read_bytes(path: Path) -> bytes:
        if path.name == "bad.md":
            raise PermissionError("permission denied")
        return path.read_bytes()

    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.read_file_bytes", read_bytes
    )

    result = run_index(index_config, mode=IndexMode.FULL)

    assert result.status == "success_with_errors"
    assert result.files_processed == 1
    assert result.files_failed == 1


def test_unreadable_directory_does_not_abort_discovery(
    index_config, monkeypatch
) -> None:
    good_dir = index_config.vault_path / "wiki" / "good"
    blocked_dir = index_config.vault_path / "wiki" / "blocked"
    good_dir.mkdir(parents=True)
    blocked_dir.mkdir()
    (good_dir / "note.md").write_text("# Good\nbody", encoding="utf-8")
    (blocked_dir / "note.md").write_text("# Blocked\nbody", encoding="utf-8")
    original_scandir = os.scandir

    def scandir(path):  # noqa: ANN001
        if Path(path).name == "blocked":
            raise PermissionError("blocked directory")
        return original_scandir(path)

    monkeypatch.setattr("obsidian_memory_mcp.indexing.service.os.scandir", scandir)

    result = run_index(index_config, mode=IndexMode.FULL)

    assert result.status == "success"
    assert result.files_processed == 1


def test_incremental_retries_file_with_previous_error(
    index_config, monkeypatch
) -> None:
    note = index_config.vault_path / "wiki" / "flaky.md"
    note.write_text("# Flaky\nbody", encoding="utf-8")
    fail_once = True

    def read_bytes(path: Path) -> bytes:
        nonlocal fail_once
        if path == note and fail_once:
            fail_once = False
            raise PermissionError("temporary lock")
        return path.read_bytes()

    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.read_file_bytes", read_bytes
    )
    failed = run_index(index_config, mode=IndexMode.FULL)

    result = run_index(index_config)
    connection = _connect(index_config.index_db_location)
    row = connection.execute(
        "SELECT last_error_id FROM files WHERE vault_path = 'wiki/flaky.md'"
    ).fetchone()
    connection.close()

    assert failed.files_failed == 1
    assert result.files_processed == 1
    assert row["last_error_id"] is None


def test_unexpected_error_marks_run_failed_instead_of_leaving_it_running(
    index_config, monkeypatch
) -> None:
    note = index_config.vault_path / "wiki" / "alpha.md"
    note.write_text("# Alpha\nbody", encoding="utf-8")

    def fail_replace(*args, **kwargs):  # noqa: ANN002, ANN003
        raise KeyError("missing section")

    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.replace_file_index", fail_replace
    )

    result = run_index(index_config, mode=IndexMode.FULL)
    connection = _connect(index_config.index_db_location)
    row = connection.execute(
        "SELECT status, finished_at FROM index_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    connection.close()

    assert result.status == "failed"
    assert row["status"] == "failed"
    assert row["finished_at"] is not None


def test_cleanup_failures_are_logged_when_failure_recording_breaks(
    index_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    note = index_config.vault_path / "wiki" / "alpha.md"
    note.write_text("# Alpha\nbody", encoding="utf-8")

    def fail_replace(*args, **kwargs):  # noqa: ANN002, ANN003
        raise KeyError("missing section")

    def fail_record_error(*args, **kwargs):  # noqa: ANN002, ANN003
        raise TypeError("bad payload")

    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.replace_file_index", fail_replace
    )
    monkeypatch.setattr(
        "obsidian_memory_mcp.indexing.service.record_error", fail_record_error
    )
    logger = Mock()
    monkeypatch.setattr("obsidian_memory_mcp.indexing.service.LOGGER", logger)

    result = run_index(index_config, mode=IndexMode.FULL)

    assert result.status == "failed"
    logger.exception.assert_called_once_with(
        "Failed to persist index failure diagnostics."
    )
