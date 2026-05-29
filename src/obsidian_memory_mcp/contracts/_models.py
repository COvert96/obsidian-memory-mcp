"""Public contract models for MCP tool metadata."""

from __future__ import annotations

from dataclasses import dataclass

from obsidian_memory_mcp.errors import ErrorCode


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    possible_errors: tuple[ErrorCode, ...]
    example_request: dict[str, object]
    example_response: dict[str, object]

