"""Tool contracts: canonical definitions of each MCP tool's interface."""

from __future__ import annotations

from obsidian_memory_mcp.contracts._models import ToolContract
from obsidian_memory_mcp.contracts._registry import TOOL_CONTRACTS
from obsidian_memory_mcp.errors import ErrorCode

TOOL_ERROR_CODES: dict[str, tuple[ErrorCode, ...]] = {
    name: contract.possible_errors for name, contract in TOOL_CONTRACTS.items()
}

__all__ = [
    "TOOL_CONTRACTS",
    "TOOL_ERROR_CODES",
    "ToolContract",
]
