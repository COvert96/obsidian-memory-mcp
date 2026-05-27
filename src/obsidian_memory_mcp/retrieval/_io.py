"""Shared note IO primitives for retrieval services."""

from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


def resolve_existing_note(
    config: ProjectConfig,
    guardrails: GuardrailEvaluator,
    note_path: str,
) -> Path:
    resolved_path = guardrails.check_read(note_path)
    if resolved_path.is_file():
        return resolved_path

    relative = resolved_path.relative_to(config.vault_path).as_posix()
    raise ToolExecutionError(
        build_error(ErrorCode.ERR_MISSING_FILE, details={"file_path": relative})
    )


def read_text(config: ProjectConfig, path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError as error:
        relative = path.relative_to(config.vault_path).as_posix()
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_GUARDRAIL_VIOLATION,
                message=f"Path '{relative}' is not readable.",
                details={"path": relative, "suggestion": "Choose a readable note."},
            )
        ) from error
