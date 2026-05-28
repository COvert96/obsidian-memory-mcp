"""Unit tests for WriteAuditRepository append and query."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.writes._audit import WriteAuditRepository
from obsidian_memory_mcp.writes._models import WriteAuditEntry


def _repository(vault_root: Path) -> WriteAuditRepository:
    return WriteAuditRepository(ConfigLoader(vault_root).load())


def _entry(**overrides: object) -> WriteAuditEntry:
    base: dict[str, object] = {
        "occurred_at": datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC),
        "tool": "write_memory",
        "project": "alpha",
        "file_path": "Memory/note.md",
        "operation": "create",
        "content_hash": "a" * 64,
        "supersedes": None,
    }
    base.update(overrides)
    return WriteAuditEntry(**base)  # type: ignore[arg-type]


def test_append_persists_a_row_that_can_be_queried_back(vault_root: Path) -> None:
    repository = _repository(vault_root)
    repository.append(_entry())

    rows = repository.list()

    assert len(rows) == 1
    row = rows[0]
    assert row.tool == "write_memory"
    assert row.project == "alpha"
    assert row.file_path == "Memory/note.md"
    assert row.operation == "create"
    assert row.content_hash == "a" * 64
    assert row.supersedes is None
    assert row.occurred_at == datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)


def test_list_returns_most_recent_first_and_honours_filters(vault_root: Path) -> None:
    repository = _repository(vault_root)
    repository.append(_entry(file_path="Memory/one.md", operation="create"))
    repository.append(_entry(file_path="Memory/two.md", operation="update"))

    assert [row.file_path for row in repository.list()] == [
        "Memory/two.md",
        "Memory/one.md",
    ]
    assert [row.operation for row in repository.list(file_path="Memory/one.md")] == [
        "create"
    ]
    assert repository.list(project="absent") == ()


def test_list_respects_limit(vault_root: Path) -> None:
    repository = _repository(vault_root)
    for index in range(3):
        repository.append(_entry(file_path=f"Memory/note-{index}.md"))

    assert len(repository.list(limit=2)) == 2
