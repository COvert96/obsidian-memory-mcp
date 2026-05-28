"""Tests for the `mcp-memory audit writes` CLI subcommand."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from obsidian_memory_mcp.cli import main
from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.writes import WriteService
from obsidian_memory_mcp.writes._audit import WriteAuditRepository


def _write_config(vault: Path) -> None:
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


def _vault_with_two_writes(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    _write_config(vault)
    config = ConfigLoader(vault).load()
    audit = WriteAuditRepository(config)
    service = WriteService(
        config,
        clock=lambda: datetime(2026, 5, 28, 9, 0, 0, tzinfo=UTC),
        audit=audit,
        tool="write_memory",
        project="alpha",
    )
    service.create("Memory/first.md", "one")
    service.create("Memory/second.md", "two")
    return vault


def test_audit_writes_lists_both_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault_with_two_writes(tmp_path)

    exit_code = main(["audit", "writes", str(vault)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Memory/first.md" in output
    assert "Memory/second.md" in output
    assert "write_memory" in output


def test_audit_writes_filters_by_file_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault_with_two_writes(tmp_path)

    exit_code = main(["audit", "writes", str(vault), "--file-path", "Memory/first.md"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Memory/first.md" in output
    assert "Memory/second.md" not in output


def test_audit_writes_reports_empty_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    (vault / "Memory").mkdir(parents=True)
    _write_config(vault)

    exit_code = main(["audit", "writes", str(vault)])

    assert exit_code == 0
    assert "no audit entries" in capsys.readouterr().out.lower()
