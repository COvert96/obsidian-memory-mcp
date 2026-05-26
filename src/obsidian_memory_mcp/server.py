"""MCP server - tool registration and request handling.

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

from obsidian_memory_mcp.config import (
    GuardrailEvaluator,
    ProjectConfig,
    load_project_config,
)
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.retrieval import (
    ReadNoteService,
    ReadSectionService,
    SearchService,
)
from obsidian_memory_mcp.server_registry import load_project_registry

mcp = FastMCP("obsidian-memory-mcp")


@mcp.tool()
def read_note(project: str, note_path: str) -> dict[str, Any]:
    """Read a full markdown note from a configured project vault.

    Args:
        project: Project name as defined in the server registry.
        note_path: Vault-relative path to the markdown file.
    """
    config = _project_config(project)
    result = ReadNoteService(config, GuardrailEvaluator(config)).read(note_path)
    return {"project": project, **result}


@mcp.tool()
def read_section(project: str, note_path: str, heading_name: str) -> dict[str, Any]:
    """Read one markdown section from a configured project vault.

    Args:
        project: Project name as defined in the server registry.
        note_path: Vault-relative path to the markdown file.
        heading_name: Case-insensitive markdown heading text to read.
    """
    config = _project_config(project)
    result = ReadSectionService(config, GuardrailEvaluator(config)).read(
        note_path,
        heading_name,
    )
    return {"project": project, **result}


@mcp.tool()
def search_notes(
    project: str,
    query: str,
    limit: int = 10,
    tags: list[str] | None = None,
    paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Search indexed markdown blocks from a configured project vault.

    Args:
        project: Project name as defined in the server registry.
        query: FTS5 query string, or a regex wrapped in forward slashes.
        limit: Maximum number of ranked results to return.
        tags: Optional tags that must all be present on each result.
        paths: Optional include glob patterns matched against vault paths.
        exclude_paths: Optional exclude glob patterns applied after includes.
    """
    config = _project_config(project)
    result = SearchService(config).search(
        query,
        limit=limit,
        tags=tags,
        paths=paths,
        exclude_paths=exclude_paths,
    )
    return {"project": project, **result}


@mcp.tool()
def get_context_pack(
    project: str,
    pack_name: str,
    strict_budget: bool = True,
) -> dict[str, Any]:
    """Load a configured context pack from a project vault.

    Args:
        project: Project name as defined in the server registry.
        pack_name: Context pack name from the project's memory-mcp.yaml.
        strict_budget: When true, reject packs over budget instead of truncating.
    """
    config = _project_config(project)
    result = _make_context_pack_loader(config).load(
        pack_name,
        strict_budget=strict_budget,
    )
    return {"project": project, **result.as_response()}


def _project_config(project: str) -> ProjectConfig:
    registry = load_project_registry()
    return load_project_config(registry.resolve(project))


def _make_context_pack_loader(config: ProjectConfig) -> ContextPackLoader:
    return ContextPackLoader(config)
