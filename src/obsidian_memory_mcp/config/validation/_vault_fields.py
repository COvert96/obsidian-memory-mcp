"""Validation for vault path and index database location."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from obsidian_memory_mcp.config.validation._errors import ConfigValidationError
from obsidian_memory_mcp.config.validation._parsers import resolve_config_path
from obsidian_memory_mcp.config.validation._rules import type_error

_REQUIRED_FIELDS = (
    "vault_path",
    "index_db_location",
    "context_packs",
    "write_constraints",
)


def missing_required_field_errors(data: dict[str, Any]) -> list[ConfigValidationError]:
    return [
        ConfigValidationError(
            field=field_name,
            expected="present",
            actual="<missing>",
            suggestion=f"Add required field '{field_name}' to memory-mcp.yaml.",
        )
        for field_name in _REQUIRED_FIELDS
        if field_name not in data
    ]


def validated_vault_path(
    data: dict[str, Any],
    errors: list[ConfigValidationError],
) -> Path | None:
    if "vault_path" not in data:
        return None

    vault_path = data["vault_path"]
    if not isinstance(vault_path, str):
        errors.append(type_error("vault_path", "a string absolute path", vault_path))
        return None

    candidate = Path(vault_path)
    if not candidate.is_absolute():
        errors.append(
            ConfigValidationError(
                field="vault_path",
                expected="an absolute path",
                actual=vault_path,
                suggestion="Use '/full/path' instead.",
            )
        )
        return None

    resolved = candidate.resolve(strict=False)
    if not resolved.is_dir():
        errors.append(
            ConfigValidationError(
                field="vault_path",
                expected="an existing directory",
                actual=vault_path,
                suggestion=(
                    "Create the vault directory or point vault_path at an existing vault."
                ),
            )
        )
        return None

    return resolved


def validate_index_db_location(
    data: dict[str, Any],
    vault_path: Path | None,
    errors: list[ConfigValidationError],
) -> None:
    if "index_db_location" not in data:
        return

    index_db_location = data["index_db_location"]
    if not isinstance(index_db_location, str) or not index_db_location:
        errors.append(
            type_error(
                "index_db_location", "a non-empty string path", index_db_location
            )
        )
        return

    if vault_path is None:
        return

    resolved = resolve_config_path(vault_path, index_db_location)
    if not resolved.is_relative_to(vault_path):
        errors.append(
            ConfigValidationError(
                field="index_db_location",
                expected="a path inside vault_path",
                actual=index_db_location,
                suggestion="Use a relative path such as 'memory-index.sqlite3'.",
            )
        )
