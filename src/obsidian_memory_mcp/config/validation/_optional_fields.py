"""Validation for optional top-level config fields."""

from __future__ import annotations

import warnings
from pathlib import PurePosixPath
from typing import Any

from obsidian_memory_mcp.config._models import ProjectConfig
from obsidian_memory_mcp.config.validation._errors import ConfigValidationError
from obsidian_memory_mcp.config.validation._rules import (
    type_error,
    validate_optional_positive_int,
)

_REMOVED_PROPOSAL_FIELDS: tuple[str, ...] = (
    "max_proposal_ttl_hours",
    "proposal_ttl_seconds",
    "proposal_retention_days",
)


def validate_optional_fields(
    data: dict[str, Any],
    errors: list[ConfigValidationError],
) -> None:
    if "tags_separator" in data and not isinstance(data["tags_separator"], str):
        errors.append(type_error("tags_separator", "a string", data["tags_separator"]))
    validate_optional_positive_int(
        data,
        "max_write_content_bytes",
        "max_write_content_bytes",
        errors,
    )
    validate_optional_positive_int(
        data,
        "max_proposal_content_bytes",
        "max_proposal_content_bytes",
        errors,
    )
    validate_memory_archive_path(data, errors)


def validate_memory_archive_path(
    data: dict[str, Any],
    errors: list[ConfigValidationError],
) -> None:
    if "memory_archive_path" not in data:
        return

    value = data["memory_archive_path"]
    if not isinstance(value, str) or not value:
        errors.append(
            type_error("memory_archive_path", "a non-empty relative path", value)
        )
        return

    parts = _archive_path_parts(value)
    if parts is None:
        _append_archive_path_error(
            errors,
            expected="a relative path under 'Memory/'",
            actual=value,
            suggestion="Use a path such as 'Memory/archive'.",
        )
        return

    if ".." in parts:
        _append_archive_path_error(
            errors,
            expected="a path without '..' traversal segments",
            actual=value,
            suggestion="Remove parent-directory traversal from the archive path.",
        )


def _archive_path_parts(value: str) -> tuple[str, ...] | None:
    normalized = value.replace("\\", "/")
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    is_under_memory = bool(parts) and parts[0] == "Memory"
    if PurePosixPath(normalized).is_absolute() or not is_under_memory:
        return None
    return parts


def _append_archive_path_error(
    errors: list[ConfigValidationError],
    *,
    expected: str,
    actual: str,
    suggestion: str,
) -> None:
    errors.append(
        ConfigValidationError(
            field="memory_archive_path",
            expected=expected,
            actual=actual,
            suggestion=suggestion,
        )
    )


def warn_removed_proposal_fields(data: dict[str, Any]) -> None:
    for field in _REMOVED_PROPOSAL_FIELDS:
        if field in data:
            warnings.warn(
                f"Config field '{field}' was removed in v0.2.0 and has no "
                "effect. Remove it from memory-mcp.yaml.",
                DeprecationWarning,
                stacklevel=3,
            )


def resolve_max_write_content_bytes(data: dict[str, Any]) -> int:
    if "max_write_content_bytes" in data:
        return int(data["max_write_content_bytes"])
    if "max_proposal_content_bytes" in data:
        warnings.warn(
            "Config key 'max_proposal_content_bytes' is deprecated; "
            "rename it to 'max_write_content_bytes'.",
            DeprecationWarning,
            stacklevel=4,
        )
        return int(data["max_proposal_content_bytes"])
    return ProjectConfig.DEFAULT_MAX_WRITE_CONTENT_BYTES
