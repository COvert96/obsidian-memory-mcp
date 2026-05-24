"""MCP server — tool registration and request handling.

Follows the FastMCP pattern: a module-level ``mcp`` instance with
``@mcp.tool()``-decorated functions.  FastMCP handles transport, JSON-RPC
framing, schema generation, and error serialisation.

Domain exceptions (``ToolExecutionError``) raised inside tool functions
propagate naturally to FastMCP, which converts them to
``CallToolResult(isError=True)`` responses.  No manual error-wrapping needed.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from obsidian_memory_mcp.config import ConfigLoader, GuardrailEvaluator
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.server_registry import load_project_registry
from obsidian_memory_mcp.vault import parse_frontmatter

mcp = FastMCP("obsidian-memory-mcp")


@mcp.tool()
def read_note(project: str, note_path: str) -> dict[str, Any]:
    """Read a full markdown note from a configured project vault.

    Args:
        project: Project name as defined in the server registry.
        note_path: Vault-relative path to the markdown file.
    """
    registry = load_project_registry()
    vault_root = registry.resolve(project)
    config = ConfigLoader(vault_root).load()
    resolved_path = GuardrailEvaluator(config).check_read(note_path)

    if not resolved_path.exists():
        relative = resolved_path.relative_to(config.vault_path).as_posix()
        raise ToolExecutionError(
            build_error(ErrorCode.ERR_MISSING_FILE, details={"file_path": relative})
        )

    raw = resolved_path.read_text(encoding="utf-8")
    return {
        "project": project,
        "file_path": resolved_path.relative_to(config.vault_path).as_posix(),
        "content": raw,
        "frontmatter": parse_frontmatter(raw),
        "file_size_bytes": len(raw.encode("utf-8")),
    }
