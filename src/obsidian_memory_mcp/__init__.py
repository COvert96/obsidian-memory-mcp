"""Obsidian Memory MCP - an MCP server for structured, safe access to Obsidian vaults.

This module re-exports a convenience surface for tests and tooling. It is **not** a
semver-stable library API until PyPI publication is announced. Prefer explicit imports
from subpackages (``obsidian_memory_mcp.config``, ``obsidian_memory_mcp.contracts``,
and so on) in new code.
"""

from obsidian_memory_mcp.config import (
    AccessConstraints,
    AccessPolicy,
    ConfigLoader,
    ConfigValidationException,
    ConfigValidator,
    GuardrailEvaluator,
    ProjectConfig,
    WriteConstraints,
    WritePolicy,
    load_project_config,
)
from obsidian_memory_mcp.contracts import TOOL_CONTRACTS, TOOL_ERROR_CODES, ToolContract
from obsidian_memory_mcp.errors import (
    ERROR_CATALOG,
    ErrorCode,
    ErrorResponse,
    ToolExecutionError,
)
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import (
    DEFAULT_SERVER_REGISTRY_FILE,
    SERVER_REGISTRY_ENV_VAR,
    ProjectRegistry,
    load_project_registry,
)
from obsidian_memory_mcp.tokens import estimate_tokens

__all__ = [
    # Server
    "mcp",
    # Config
    "AccessConstraints",
    "AccessPolicy",
    "ConfigLoader",
    "ConfigValidationException",
    "ConfigValidator",
    "GuardrailEvaluator",
    "ProjectConfig",
    "WriteConstraints",
    "WritePolicy",
    "load_project_config",
    # Contracts
    "TOOL_CONTRACTS",
    "TOOL_ERROR_CODES",
    "ToolContract",
    # Errors
    "ERROR_CATALOG",
    "ErrorCode",
    "ErrorResponse",
    "ToolExecutionError",
    # Registry
    "DEFAULT_SERVER_REGISTRY_FILE",
    "SERVER_REGISTRY_ENV_VAR",
    "ProjectRegistry",
    "load_project_registry",
    # Tokens
    "estimate_tokens",
]
