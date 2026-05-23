from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    ERR_CONTEXT_EXCEEDS_BUDGET = "ERR_CONTEXT_EXCEEDS_BUDGET"
    ERR_GUARDRAIL_VIOLATION = "ERR_GUARDRAIL_VIOLATION"
    ERR_INTERNAL = "ERR_INTERNAL"
    ERR_INVALID_PROJECT = "ERR_INVALID_PROJECT"
    ERR_INVALID_REQUEST = "ERR_INVALID_REQUEST"
    ERR_MISSING_FILE = "ERR_MISSING_FILE"
    ERR_SECTION_NOT_FOUND = "ERR_SECTION_NOT_FOUND"
    ERR_STALE_PROPOSAL = "ERR_STALE_PROPOSAL"


@dataclass(frozen=True)
class ErrorDefinition:
    http_status: int
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
    def __init__(self, error: ErrorResponse):
        super().__init__(error.message)
        self.error = error


ERROR_CATALOG: dict[ErrorCode, ErrorDefinition] = {
    ErrorCode.ERR_INVALID_REQUEST: ErrorDefinition(
        http_status=400,
        message_template="Request payload failed schema validation.",
        recovery_suggestion="Check the documented request schema and retry with the required fields and types.",
    ),
    ErrorCode.ERR_INVALID_PROJECT: ErrorDefinition(
        http_status=404,
        message_template="Project '{project}' is not configured.",
        recovery_suggestion="Use a configured project identifier from the server config and retry.",
    ),
    ErrorCode.ERR_MISSING_FILE: ErrorDefinition(
        http_status=404,
        message_template="File '{file_path}' does not exist in the project vault.",
        recovery_suggestion="Verify the relative path and ensure the file exists within the configured vault root.",
    ),
    ErrorCode.ERR_SECTION_NOT_FOUND: ErrorDefinition(
        http_status=404,
        message_template="Heading '{heading_name}' was not found in '{file_path}'.",
        recovery_suggestion="Retry with a case-insensitive heading that exists in the target note.",
    ),
    ErrorCode.ERR_GUARDRAIL_VIOLATION: ErrorDefinition(
        http_status=403,
        message_template="The requested file operation violates configured guardrails.",
        recovery_suggestion="Choose a path inside the vault and within the allowed read/write constraints.",
    ),
    ErrorCode.ERR_STALE_PROPOSAL: ErrorDefinition(
        http_status=409,
        message_template="The proposal is stale and can no longer be applied safely.",
        recovery_suggestion="Recreate the proposal against the latest file contents before approving it.",
    ),
    ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET: ErrorDefinition(
        http_status=422,
        message_template="The requested context pack exceeds the configured token budget.",
        recovery_suggestion="Use a smaller pack, disable strict budgeting, or remove files until the estimate fits.",
    ),
    ErrorCode.ERR_INTERNAL: ErrorDefinition(
        http_status=500,
        message_template="The server encountered an unexpected internal error.",
        recovery_suggestion="Retry if the failure is transient, otherwise inspect logs or contact the operator.",
    ),
}


TOOL_ERROR_CODES: dict[str, tuple[ErrorCode, ...]] = {
    "read_note": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_MISSING_FILE,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_INTERNAL,
    ),
    "read_section": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_MISSING_FILE,
        ErrorCode.ERR_SECTION_NOT_FOUND,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_INTERNAL,
    ),
    "search_notes": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_INTERNAL,
    ),
    "get_context_pack": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET,
        ErrorCode.ERR_INTERNAL,
    ),
    "propose_memory_update": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_INTERNAL,
    ),
    "list_proposals": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_INTERNAL,
    ),
    "approve_proposal": (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_STALE_PROPOSAL,
        ErrorCode.ERR_MISSING_FILE,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_INTERNAL,
    ),
}


def build_error(
    code: ErrorCode,
    *,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> ErrorResponse:
    definition = ERROR_CATALOG[code]
    return ErrorResponse(
        code=code,
        message=message or definition.message_template,
        details=details or {},
    )