"""Validation for read/write guardrail policies."""

from __future__ import annotations

from typing import Any

from obsidian_memory_mcp.config.validation._errors import ConfigValidationError
from obsidian_memory_mcp.config.validation._rules import type_error, validate_string_list


def validate_write_constraints(
    data: dict[str, Any],
    errors: list[ConfigValidationError],
) -> None:
    if "write_constraints" not in data:
        return

    write_constraints = data["write_constraints"]
    if not isinstance(write_constraints, dict):
        errors.append(
            type_error(
                "write_constraints",
                "an object with read/write policies",
                write_constraints,
            )
        )
        return

    for operation in ("read", "write"):
        policy = write_constraints.get(operation, {})
        if not isinstance(policy, dict):
            errors.append(
                type_error(f"write_constraints.{operation}", "an object", policy)
            )
            continue
        validate_string_list(
            policy, "allow", f"write_constraints.{operation}.allow", errors
        )
        validate_string_list(
            policy, "deny", f"write_constraints.{operation}.deny", errors
        )
