"""WriteService — direct atomic file create with guardrail enforcement."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.wikilinks import escape_wikilink_alias_separator
from obsidian_memory_mcp.writes._io import atomic_write
from obsidian_memory_mcp.writes._models import WriteResult


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
    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._clock = clock or _utc_now

    def create(self, file_path: str, content: str) -> WriteResult:
        normalized_content = escape_wikilink_alias_separator(content)
        content_bytes = normalized_content.encode("utf-8")

        max_bytes = self._config.max_write_content_bytes
        if len(content_bytes) > max_bytes:
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_INVALID_REQUEST,
                    message=(
                        f"Content is {len(content_bytes)} bytes, which exceeds "
                        f"the configured limit of {max_bytes} bytes."
                    ),
                    details={
                        "content_size": len(content_bytes),
                        "limit": max_bytes,
                    },
                )
            )

        resolved_path = self._guardrails.check_write(file_path)
        relative_path = resolved_path.relative_to(self._config.vault_path).as_posix()

        if resolved_path.exists():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_FILE_EXISTS,
                    details={"file_path": relative_path},
                )
            )

        atomic_write(resolved_path, content_bytes)

        return WriteResult(
            file_path=relative_path,
            operation="create",
            content_hash=hashlib.sha256(content_bytes).hexdigest(),
            file_size_bytes=len(content_bytes),
            written_at=self._now(),
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
