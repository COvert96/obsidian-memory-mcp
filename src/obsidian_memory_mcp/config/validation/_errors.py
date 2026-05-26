from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from obsidian_memory_mcp.errors import (
    ErrorCode,
    ErrorResponse,
    ToolExecutionError,
    build_error,
)


@dataclass(frozen=True)
class ConfigValidationError:
    field: str
    expected: str
    actual: Any
    suggestion: str

    @property
    def message(self) -> str:
        return (
            f"Field '{self.field}' must be {self.expected}. "
            f"Got {self.actual!r}. {self.suggestion}"
        )


class ConfigValidationException(ToolExecutionError):
    def __init__(
        self,
        error: ErrorResponse,
        validation_errors: list[ConfigValidationError] | None = None,
    ):
        super().__init__(error)
        self.validation_errors = validation_errors or []


def validation_error_response(errors: list[ConfigValidationError]) -> ErrorResponse:
    field_names = ", ".join(error.field for error in errors[:5])
    if len(errors) > 5:
        field_names = f"{field_names}, ..."

    return build_error(
        ErrorCode.ERR_INVALID_PROJECT,
        message=f"Project config is invalid. Fix these field(s): {field_names}.",
        details={
            "errors": [error.message for error in errors],
            "suggestion": "Fix all listed fields, then run 'mcp-memory config validate' again.",
        },
    )
