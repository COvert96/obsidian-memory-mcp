"""WriteService — direct atomic file create/update with guardrail enforcement."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.utils import (
    escape_wikilink_alias_separator,
    sha256_bytes,
    sha256_file,
)
from obsidian_memory_mcp.writes._audit import WriteAuditRepository
from obsidian_memory_mcp.writes._io import atomic_write
from obsidian_memory_mcp.writes._models import WriteAuditEntry, WriteResult


def is_memory_path(file_path: str) -> bool:
    """Return True if file_path is under Memory/."""
    normalized = file_path.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    return len(path.parts) >= 2 and path.parts[0] == "Memory"


def require_memory_path(file_path: str, tool_name: str) -> None:
    """Raise ERR_INVALID_REQUEST if file_path is not under Memory/."""
    if is_memory_path(file_path):
        return
    raise ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=(
                f"{tool_name} only supports files under 'Memory/'. "
                f"Received '{file_path}'."
            ),
            details={"file_path": file_path, "required_prefix": "Memory/"},
        )
    )


class WriteService:
    """Create and update vault files atomically behind the write guardrails.

    When an `audit` repository is supplied, every successful write appends a
    `write_audit` row tagged with `tool` and `project`.  Audit logging is
    best-effort: a failure is logged to stderr and never aborts the write.
    """

    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        audit: WriteAuditRepository | None = None,
        tool: str | None = None,
        project: str | None = None,
    ) -> None:
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._clock = clock or _utc_now
        self._audit = audit
        self._tool = tool
        self._project = project

    def create(self, file_path: str, content: str) -> WriteResult:
        content_bytes = self._normalize_within_size_limit(content)

        resolved_path = self._guardrails.check_write(file_path)
        relative_path = resolved_path.relative_to(self._config.vault_path).as_posix()

        if resolved_path.exists():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_FILE_EXISTS,
                    details={"file_path": relative_path},
                )
            )

        return self._write(resolved_path, relative_path, content_bytes, "create")

    def update(
        self,
        file_path: str,
        content: str,
        expected_hash: str | None = None,
        *,
        defer_audit: bool = False,
    ) -> WriteResult:
        """Overwrite an existing file atomically.

        When ``defer_audit`` is set, the audit row is *not* appended here; the
        caller must append exactly one row afterwards (used by the supersession
        orchestrator, whose archive paths are known only after the write).
        """
        content_bytes = self._normalize_within_size_limit(content)

        resolved_path = self._guardrails.check_write(file_path)
        relative_path = resolved_path.relative_to(self._config.vault_path).as_posix()

        if not resolved_path.is_file():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_MISSING_FILE,
                    details={"file_path": relative_path},
                )
            )

        if expected_hash is not None and sha256_file(resolved_path) != expected_hash:
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_HASH_MISMATCH,
                    details={"file_path": relative_path},
                )
            )

        return self._write(
            resolved_path,
            relative_path,
            content_bytes,
            "update",
            record_audit=not defer_audit,
        )

    def record_supersession_audit(
        self, result: WriteResult, archived_paths: list[str]
    ) -> None:
        """Append the single audit row for a deferred supersession write."""
        self._record_audit(result, supersedes=json.dumps(archived_paths))

    def _normalize_within_size_limit(self, content: str) -> bytes:
        content_bytes = escape_wikilink_alias_separator(content).encode("utf-8")
        max_bytes = self._config.max_write_content_bytes
        if len(content_bytes) > max_bytes:
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_INVALID_REQUEST,
                    message=(
                        f"Content is {len(content_bytes)} bytes, which exceeds "
                        f"the configured limit of {max_bytes} bytes."
                    ),
                    details={"content_size": len(content_bytes), "limit": max_bytes},
                )
            )
        return content_bytes

    def _write(
        self,
        resolved_path: Path,
        relative_path: str,
        content_bytes: bytes,
        operation: str,
        *,
        record_audit: bool = True,
    ) -> WriteResult:
        atomic_write(resolved_path, content_bytes)
        result = WriteResult(
            file_path=relative_path,
            operation=operation,
            content_hash=sha256_bytes(content_bytes),
            file_size_bytes=len(content_bytes),
            written_at=self._now(),
        )
        if record_audit:
            self._record_audit(result)
        return result

    def _record_audit(
        self, result: WriteResult, *, supersedes: str | None = None
    ) -> None:
        if self._audit is None:
            return
        try:
            self._audit.append(
                WriteAuditEntry(
                    occurred_at=result.written_at,
                    tool=self._tool or "",
                    project=self._project or "",
                    file_path=result.file_path,
                    operation=result.operation,
                    content_hash=result.content_hash,
                    supersedes=supersedes,
                )
            )
        except Exception as error:  # noqa: BLE001 — audit must never abort a write
            print(f"write_audit append failed: {error}", file=sys.stderr)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
