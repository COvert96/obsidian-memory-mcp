"""Domain error model: error codes, structured responses, and catalog definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    ERR_CONTEXT_EXCEEDS_BUDGET = "ERR_CONTEXT_EXCEEDS_BUDGET"
    ERR_FILE_EXISTS = "ERR_FILE_EXISTS"
    ERR_GUARDRAIL_VIOLATION = "ERR_GUARDRAIL_VIOLATION"
    ERR_INTERNAL = "ERR_INTERNAL"
    ERR_INVALID_PROJECT = "ERR_INVALID_PROJECT"
    ERR_INVALID_REQUEST = "ERR_INVALID_REQUEST"
    ERR_MISSING_FILE = "ERR_MISSING_FILE"
    ERR_SECTION_NOT_FOUND = "ERR_SECTION_NOT_FOUND"
    ERR_STALE_PROPOSAL = "ERR_STALE_PROPOSAL"


@dataclass(frozen=True)
class ErrorDefinition:
    message_template: str
    recovery_suggestion: str


@dataclass(frozen=True)
class ErrorResponse:
    code: ErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


class ToolExecutionError(Exception):
    """Raised by domain code when a tool call cannot be completed.

    FastMCP catches this naturally and surfaces it as a ``CallToolResult``
    with ``isError=True``.  The error code is included in the exception
    message so the structured code survives FastMCP's wrapping and remains
    visible to clients.
    """

    def __init__(self, error: ErrorResponse) -> None:
        super().__init__(f"[{error.code.value}] {error.message}")
        self.error = error


ERROR_CATALOG: dict[ErrorCode, ErrorDefinition] = {
    ErrorCode.ERR_INVALID_REQUEST: ErrorDefinition(
        message_template="Request payload failed schema validation.",
        recovery_suggestion=(
            "Check the documented request schema and retry with the required fields and types."
        ),
    ),
    ErrorCode.ERR_INVALID_PROJECT: ErrorDefinition(
        message_template="Project '{project}' is not configured.",
        recovery_suggestion=(
            "Use a configured project identifier from the server config and retry."
        ),
    ),
    ErrorCode.ERR_MISSING_FILE: ErrorDefinition(
        message_template="File '{file_path}' does not exist in the project vault.",
        recovery_suggestion=(
            "Verify the relative path and ensure the file exists within the configured vault root."
        ),
    ),
    ErrorCode.ERR_SECTION_NOT_FOUND: ErrorDefinition(
        message_template="Heading '{heading_name}' was not found in '{file_path}'.",
        recovery_suggestion=(
            "Retry with a case-insensitive heading that exists in the target note."
        ),
    ),
    ErrorCode.ERR_GUARDRAIL_VIOLATION: ErrorDefinition(
        message_template="The requested file operation violates configured guardrails.",
        recovery_suggestion=(
            "Choose a path inside the vault and within the allowed read/write constraints."
        ),
    ),
    ErrorCode.ERR_STALE_PROPOSAL: ErrorDefinition(
        message_template="The proposal is stale and can no longer be applied safely.",
        recovery_suggestion=(
            "Recreate the proposal against the latest file contents before approving it."
        ),
    ),
    ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET: ErrorDefinition(
        message_template="The requested context pack exceeds the configured token budget.",
        recovery_suggestion=(
            "Use a smaller pack, disable strict budgeting, or remove files until the estimate fits."
        ),
    ),
    ErrorCode.ERR_FILE_EXISTS: ErrorDefinition(
        message_template=(
            "File '{file_path}' already exists. Use write_memory or write_note only for new files; "
            "call update_memory or update_note to modify an existing file."
        ),
        recovery_suggestion="Verify the path or use the appropriate update tool.",
    ),
    ErrorCode.ERR_INTERNAL: ErrorDefinition(
        message_template="The server encountered an unexpected internal error.",
        recovery_suggestion=(
            "Retry if the failure is transient, otherwise inspect logs or contact the operator."
        ),
    ),
}


def build_error(
    code: ErrorCode,
    *,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> ErrorResponse:
    """Construct an `ErrorResponse` from a catalog entry.

    If `message` is omitted, the catalog's `message_template` is formatted
    using `details` as the substitution mapping.  Missing placeholder keys are
    left as-is rather than raising `KeyError`.
    """
    definition = ERROR_CATALOG[code]
    resolved_details = details or {}
    resolved_message = message or definition.message_template.format_map(
        _SafeFormatMap(resolved_details)
    )
    return ErrorResponse(code=code, message=resolved_message, details=resolved_details)


class _SafeFormatMap(dict[str, Any]):
    """dict subclass that returns the placeholder text for missing keys."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
