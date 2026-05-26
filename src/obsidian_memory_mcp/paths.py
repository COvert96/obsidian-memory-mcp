from __future__ import annotations

from pathlib import Path, PureWindowsPath
from urllib.parse import unquote

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


def normalize_vault_path(vault_root: str | Path, requested_path: str | Path) -> Path:
    """Resolve a requested path and prove that it stays inside the vault."""

    vault = _normalized_vault_root(vault_root)
    raw_path = str(requested_path).strip()
    if not raw_path:
        raise _guardrail_violation(
            requested_path=raw_path,
            message="Requested path is empty and cannot be resolved inside the vault.",
            suggestion="Provide a relative path such as 'wiki/note.md'.",
        )

    normalized_text = unquote(raw_path).replace("\\", "/")
    path_parts = tuple(
        part for part in normalized_text.split("/") if part not in {"", "."}
    )
    if ".." in path_parts:
        raise _guardrail_violation(
            requested_path=raw_path,
            message=f"Requested path '{raw_path}' contains '..' and may escape vault '{vault}'.",
            suggestion="Remove parent-directory traversal and use a path inside the vault.",
        )

    candidate = _candidate_path(vault, normalized_text)
    resolved_path = _resolve_symlink_segments(candidate)
    if not resolved_path.is_relative_to(vault):
        raise _guardrail_violation(
            requested_path=raw_path,
            message=f"Requested path '{raw_path}' resolves to '{resolved_path}' and escapes vault '{vault}'.",
            suggestion="Choose a path inside the configured vault root.",
        )

    return resolved_path


def _candidate_path(vault: Path, normalized_path: str) -> Path:
    requested = Path(normalized_path)
    if _is_absolute_path(normalized_path, requested):
        return requested
    return vault / normalized_path


def _normalized_vault_root(vault_root: str | Path) -> Path:
    vault = Path(vault_root)
    if vault.is_absolute() and not vault.is_symlink():
        return vault
    return vault.resolve(strict=False)


def _resolve_symlink_segments(path: Path) -> Path:
    if not path.is_absolute():
        path = path.absolute()

    current = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        current = current / part
        try:
            if not current.exists():
                return current.joinpath(*parts[index + 1 :])
            if current.is_symlink():
                current = current.resolve(strict=True)
        except OSError:
            current = current.resolve(strict=False)
    return current


def _is_absolute_path(normalized_path: str, requested: Path) -> bool:
    if requested.is_absolute() or PureWindowsPath(normalized_path).is_absolute():
        return True
    return normalized_path.startswith(("/", "//"))


def _guardrail_violation(
    *, requested_path: str, message: str, suggestion: str
) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            message=message,
            details={
                "requested_path": requested_path,
                "suggestion": suggestion,
            },
        )
    )
