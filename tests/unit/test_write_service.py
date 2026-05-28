"""Unit tests for WriteService.create() and path predicate helpers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader, GuardrailEvaluator
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.writes._models import WriteResult
from obsidian_memory_mcp.writes._service import (
    WriteService,
    is_memory_path,
    require_memory_path,
)

_FIXED_TIME = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)


def _fixed_clock() -> datetime:
    return _FIXED_TIME


def _service(vault_root: Path) -> WriteService:
    return WriteService(ConfigLoader(vault_root).load())


def _service_with_fixed_clock(vault_root: Path) -> WriteService:
    return WriteService(ConfigLoader(vault_root).load(), clock=_fixed_clock)


# ---------------------------------------------------------------------------
# is_memory_path / require_memory_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("Memory/note.md", True),
        ("Memory/sub/note.md", True),
        ("Memory/", False),  # no file part
        ("wiki/note.md", False),
        ("", False),
        ("memory/note.md", False),  # case-sensitive
        ("Memory\\note.md", True),  # Windows backslash normalised
    ],
)
def test_is_memory_path(path: str, expected: bool) -> None:
    assert is_memory_path(path) is expected


def test_require_memory_path_passes_for_memory_file() -> None:
    require_memory_path("Memory/note.md", "write_memory")  # no exception


def test_require_memory_path_raises_for_non_memory_file() -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        require_memory_path("wiki/note.md", "write_memory")
    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "write_memory" in exc_info.value.error.message


# ---------------------------------------------------------------------------
# WriteService.create — happy path
# ---------------------------------------------------------------------------


def test_create_writes_file_and_returns_result(vault_root: Path) -> None:
    service = _service_with_fixed_clock(vault_root)
    result = service.create("Memory/new-note.md", "# Hello\nWorld")

    target = vault_root / "Memory" / "new-note.md"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "# Hello\nWorld"
    assert isinstance(result, WriteResult)
    assert result.file_path == "Memory/new-note.md"
    assert result.operation == "create"
    assert result.file_size_bytes == len("# Hello\nWorld".encode("utf-8"))
    assert result.written_at == _FIXED_TIME


def test_create_content_hash_matches_written_bytes(vault_root: Path) -> None:
    content = "# Test\nsome content"
    service = _service(vault_root)
    result = service.create("Memory/hash-test.md", content)

    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert result.content_hash == expected_hash


def test_create_empty_content_produces_zero_byte_file(vault_root: Path) -> None:
    service = _service(vault_root)
    result = service.create("Memory/empty.md", "")

    target = vault_root / "Memory" / "empty.md"
    assert target.is_file()
    assert target.stat().st_size == 0
    assert result.file_size_bytes == 0
    expected_hash = hashlib.sha256(b"").hexdigest()
    assert result.content_hash == expected_hash


def test_create_auto_creates_parent_directories(vault_root: Path) -> None:
    service = _service(vault_root)
    service.create("Memory/deep/sub/dir/note.md", "content")

    assert (vault_root / "Memory" / "deep" / "sub" / "dir" / "note.md").is_file()


# ---------------------------------------------------------------------------
# WriteService.create — failure cases
# ---------------------------------------------------------------------------


def test_create_raises_file_exists_when_target_already_exists(
    vault_root: Path,
) -> None:
    (vault_root / "Memory").mkdir(exist_ok=True)
    target = vault_root / "Memory" / "existing.md"
    target.write_text("original", encoding="utf-8")

    service = _service(vault_root)
    with pytest.raises(ToolExecutionError) as exc_info:
        service.create("Memory/existing.md", "new content")

    assert exc_info.value.error.code is ErrorCode.ERR_FILE_EXISTS
    assert target.read_text(encoding="utf-8") == "original"


def test_create_raises_file_exists_when_target_is_a_directory(
    vault_root: Path,
) -> None:
    (vault_root / "Memory" / "dir-target").mkdir(parents=True, exist_ok=True)

    service = _service(vault_root)
    with pytest.raises(ToolExecutionError) as exc_info:
        service.create("Memory/dir-target", "content")

    assert exc_info.value.error.code is ErrorCode.ERR_FILE_EXISTS


def test_create_raises_guardrail_violation_for_denied_path(vault_root: Path) -> None:
    service = _service(vault_root)
    with pytest.raises(ToolExecutionError) as exc_info:
        service.create("wiki/private.md", "content")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_create_raises_invalid_request_when_content_exceeds_limit(
    vault_root: Path,
) -> None:
    config = ConfigLoader(vault_root).load()
    tiny_limit_config = config.__class__(
        vault_path=config.vault_path,
        index_db_location=config.index_db_location,
        context_packs=config.context_packs,
        write_constraints=config.write_constraints,
        max_write_content_bytes=10,
    )
    service = WriteService(tiny_limit_config)
    with pytest.raises(ToolExecutionError) as exc_info:
        service.create("Memory/big.md", "x" * 100)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "exceeds" in exc_info.value.error.message


def test_create_guardrail_checked_before_existence(vault_root: Path) -> None:
    """A path that violates the guardrail AND exists should raise guardrail, not file-exists."""
    (vault_root / "wiki").mkdir(exist_ok=True)
    (vault_root / "wiki" / "denied.md").write_text("content", encoding="utf-8")

    service = _service(vault_root)
    with pytest.raises(ToolExecutionError) as exc_info:
        service.create("wiki/denied.md", "content")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_write_result_as_response_serializes_written_at_as_iso_string() -> None:
    result = WriteResult(
        file_path="Memory/note.md",
        operation="create",
        content_hash="abc123",
        file_size_bytes=7,
        written_at=_FIXED_TIME,
    )
    response = result.as_response()

    assert response["written_at"] == _FIXED_TIME.isoformat()
    assert isinstance(response["written_at"], str)
