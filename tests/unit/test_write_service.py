"""Unit tests for WriteService create/update and path predicate helpers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.writes import (
    WriteService,
    is_memory_path,
    require_memory_path,
)
from obsidian_memory_mcp.writes._audit import WriteAuditRepository
from obsidian_memory_mcp.writes._models import WriteAuditEntry, WriteResult

_FIXED_TIME = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)


def _fixed_clock() -> datetime:
    return _FIXED_TIME


def _service(vault_root: Path) -> WriteService:
    return WriteService(ConfigLoader(vault_root).load())


def _service_with_fixed_clock(vault_root: Path) -> WriteService:
    return WriteService(ConfigLoader(vault_root).load(), clock=_fixed_clock)


def _auditing_service(
    vault_root: Path,
    audit: WriteAuditRepository,
) -> WriteService:
    return WriteService(
        ConfigLoader(vault_root).load(),
        clock=_fixed_clock,
        audit=audit,
        tool="write_memory",
        project="alpha",
    )


def _existing_memory_file(vault_root: Path, name: str, content: str) -> Path:
    (vault_root / "Memory").mkdir(exist_ok=True)
    target = vault_root / "Memory" / name
    target.write_text(content, encoding="utf-8")
    return target


class _FailingAudit(WriteAuditRepository):
    """A repository whose append always fails, to test best-effort isolation."""

    def append(self, entry: WriteAuditEntry) -> None:
        raise RuntimeError("audit backend unavailable")


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
    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION
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


# ---------------------------------------------------------------------------
# WriteService.update — happy paths
# ---------------------------------------------------------------------------


def test_update_overwrites_file_without_hash(vault_root: Path) -> None:
    target = _existing_memory_file(vault_root, "note.md", "old")
    service = _service_with_fixed_clock(vault_root)

    result = service.update("Memory/note.md", "new content")

    assert target.read_text(encoding="utf-8") == "new content"
    assert result.operation == "update"
    assert result.file_path == "Memory/note.md"
    assert result.file_size_bytes == len("new content".encode("utf-8"))
    assert result.written_at == _FIXED_TIME
    assert result.content_hash == hashlib.sha256(b"new content").hexdigest()


def test_update_succeeds_when_expected_hash_matches(vault_root: Path) -> None:
    target = _existing_memory_file(vault_root, "note.md", "old")
    current_hash = hashlib.sha256(b"old").hexdigest()
    service = _service(vault_root)

    result = service.update("Memory/note.md", "fresh", expected_hash=current_hash)

    assert target.read_text(encoding="utf-8") == "fresh"
    assert result.content_hash == hashlib.sha256(b"fresh").hexdigest()


def test_update_allows_empty_content(vault_root: Path) -> None:
    target = _existing_memory_file(vault_root, "note.md", "old")
    service = _service(vault_root)

    result = service.update("Memory/note.md", "")

    assert target.stat().st_size == 0
    assert result.content_hash == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# WriteService.update — failure cases (fixed check order)
# ---------------------------------------------------------------------------


def test_update_raises_hash_mismatch_and_leaves_file_untouched(
    vault_root: Path,
) -> None:
    target = _existing_memory_file(vault_root, "note.md", "current")
    service = _service(vault_root)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.update("Memory/note.md", "new", expected_hash="0" * 64)

    assert exc_info.value.error.code is ErrorCode.ERR_HASH_MISMATCH
    assert target.read_text(encoding="utf-8") == "current"


def test_update_raises_guardrail_violation_for_denied_path(vault_root: Path) -> None:
    service = _service(vault_root)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.update("wiki/denied.md", "content")

    assert exc_info.value.error.code is ErrorCode.ERR_GUARDRAIL_VIOLATION


def test_update_raises_missing_file_when_target_absent(vault_root: Path) -> None:
    service = _service(vault_root)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.update("Memory/absent.md", "content")

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_update_missing_file_takes_precedence_over_hash_mismatch(
    vault_root: Path,
) -> None:
    """Existence is checked before the hash, so a missing file wins (FR-8)."""
    service = _service(vault_root)

    with pytest.raises(ToolExecutionError) as exc_info:
        service.update("Memory/absent.md", "content", expected_hash="0" * 64)

    assert exc_info.value.error.code is ErrorCode.ERR_MISSING_FILE


def test_update_rejects_content_over_size_limit_before_other_checks(
    vault_root: Path,
) -> None:
    config = ConfigLoader(vault_root).load()
    tiny_limit_config = ProjectConfig(
        vault_path=config.vault_path,
        index_db_location=config.index_db_location,
        context_packs=config.context_packs,
        write_constraints=config.write_constraints,
        max_write_content_bytes=10,
    )
    service = WriteService(tiny_limit_config)

    # wiki/ is guardrail-denied and absent, yet oversized content is rejected first.
    with pytest.raises(ToolExecutionError) as exc_info:
        service.update("wiki/denied.md", "x" * 100, expected_hash="0" * 64)

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert "exceeds" in exc_info.value.error.message


# ---------------------------------------------------------------------------
# Audit logging (US-006)
# ---------------------------------------------------------------------------


def test_create_appends_one_audit_row(vault_root: Path) -> None:
    audit = WriteAuditRepository(ConfigLoader(vault_root).load())
    service = _auditing_service(vault_root, audit)

    service.create("Memory/created.md", "content")

    rows = audit.list()
    assert len(rows) == 1
    assert rows[0].tool == "write_memory"
    assert rows[0].project == "alpha"
    assert rows[0].file_path == "Memory/created.md"
    assert rows[0].operation == "create"
    assert rows[0].content_hash == hashlib.sha256(b"content").hexdigest()
    assert rows[0].occurred_at == _FIXED_TIME


def test_update_appends_one_audit_row(vault_root: Path) -> None:
    _existing_memory_file(vault_root, "note.md", "old")
    audit = WriteAuditRepository(ConfigLoader(vault_root).load())
    service = _auditing_service(vault_root, audit)

    service.update("Memory/note.md", "new")

    rows = audit.list()
    assert len(rows) == 1
    assert rows[0].operation == "update"
    assert rows[0].file_path == "Memory/note.md"


def test_audit_failure_does_not_roll_back_the_write(vault_root: Path) -> None:
    audit = _FailingAudit(ConfigLoader(vault_root).load())
    service = _auditing_service(vault_root, audit)

    result = service.create("Memory/resilient.md", "content")

    assert (vault_root / "Memory" / "resilient.md").read_text(encoding="utf-8") == (
        "content"
    )
    assert result.operation == "create"


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
