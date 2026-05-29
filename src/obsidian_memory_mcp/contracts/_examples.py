"""Shared example payloads for MCP tool contracts."""

from __future__ import annotations

from obsidian_memory_mcp.errors import ErrorCode

SAMPLE_PROJECT = "occlave"
SAMPLE_CONTENT_HASH = "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887"
SAMPLE_UPDATED_HASH = "bef4b0b23bc6e4fcbf64cfd9d3405fceea27191c0b37db114d4e62ebccb8eaf7"
SAMPLE_WRITTEN_AT = "2026-05-28T10:00:00+00:00"


def project_request(**fields: object) -> dict[str, object]:
    return {"project": SAMPLE_PROJECT, **fields}


def read_tool_errors() -> tuple[ErrorCode, ...]:
    return (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_MISSING_FILE,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_INTERNAL,
    )


def write_create_errors() -> tuple[ErrorCode, ...]:
    return (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_FILE_EXISTS,
        ErrorCode.ERR_INTERNAL,
    )


def write_update_errors() -> tuple[ErrorCode, ...]:
    return (
        ErrorCode.ERR_INVALID_REQUEST,
        ErrorCode.ERR_INVALID_PROJECT,
        ErrorCode.ERR_MISSING_FILE,
        ErrorCode.ERR_GUARDRAIL_VIOLATION,
        ErrorCode.ERR_HASH_MISMATCH,
        ErrorCode.ERR_INTERNAL,
    )


def write_result(
    *,
    file_path: str,
    operation: str,
    content_hash: str = SAMPLE_UPDATED_HASH,
    file_size_bytes: int,
) -> dict[str, object]:
    return {
        "project": SAMPLE_PROJECT,
        "file_path": file_path,
        "operation": operation,
        "content_hash": content_hash,
        "file_size_bytes": file_size_bytes,
        "written_at": SAMPLE_WRITTEN_AT,
    }
