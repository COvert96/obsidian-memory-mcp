"""Shared config field validation helpers."""

from __future__ import annotations

from typing import Any

from obsidian_memory_mcp.config.validation._errors import ConfigValidationError


def type_error(field: str, expected: str, actual: Any) -> ConfigValidationError:
    return ConfigValidationError(
        field=field,
        expected=expected,
        actual=actual,
        suggestion=f"Change '{field}' to the expected type or format: {expected}.",
    )


def validate_string_list(
    container: dict[str, Any],
    key: str,
    field_path: str,
    errors: list[ConfigValidationError],
    *,
    require_non_empty: bool = False,
) -> None:
    if key not in container:
        if require_non_empty:
            errors.append(
                ConfigValidationError(
                    field=field_path,
                    expected="a non-empty list of strings",
                    actual="<missing>",
                    suggestion=f"Add at least one path pattern to '{field_path}'.",
                )
            )
        return

    value = container[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(type_error(field_path, "a list of strings", value))
        return

    if require_non_empty and not value:
        errors.append(
            ConfigValidationError(
                field=field_path,
                expected="a non-empty list of strings",
                actual=value,
                suggestion=f"Add at least one path pattern to '{field_path}'.",
            )
        )


def validate_optional_string(
    container: dict[str, Any],
    key: str,
    field_path: str,
    errors: list[ConfigValidationError],
) -> None:
    if key not in container:
        return
    if not isinstance(container[key], str):
        errors.append(type_error(field_path, "a string", container[key]))


def validate_optional_positive_int(
    container: dict[str, Any],
    key: str,
    field_path: str,
    errors: list[ConfigValidationError],
) -> None:
    if key not in container:
        return
    value = container[key]
    if not isinstance(value, int) or value <= 0:
        errors.append(type_error(field_path, "a positive integer", value))


def find_context_pack_cycle(
    includes_by_name: dict[str, tuple[str, ...]],
) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(name: str) -> list[str]:
        if name in visiting:
            start = path.index(name)
            return [*path[start:], name]
        if name in visited:
            return []

        visiting.add(name)
        path.append(name)
        for child in includes_by_name.get(name, ()):
            cycle = visit(child)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(name)
        visited.add(name)
        return []

    for pack_name in includes_by_name:
        cycle = visit(pack_name)
        if cycle:
            return cycle
    return []
