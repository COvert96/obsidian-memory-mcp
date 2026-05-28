"""MCP server - tool registration and request handling.

Follows the FastMCP pattern: a module-level ``mcp`` instance with
``@mcp.tool()``-decorated functions.  FastMCP handles transport, JSON-RPC
framing, schema generation, and error serialisation.

Domain exceptions (``ToolExecutionError``) raised inside tool functions
propagate naturally to FastMCP, which converts them to
``CallToolResult(isError=True)`` responses.  No manual error-wrapping needed.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from mcp.server.fastmcp import FastMCP

from obsidian_memory_mcp.config import (
    GuardrailEvaluator,
    ProjectConfig,
    load_project_config,
)
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.proposals import ProposalManager
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
            Call list_context_packs first when the pack name is unknown.
        strict_budget: When true, reject packs over budget instead of truncating.
    """
    config = _project_config(project)
    result = _make_context_pack_loader(config).load(
        pack_name,
        strict_budget=strict_budget,
    )
    return {"project": project, **result.as_response()}


@mcp.tool()
def list_context_packs(project: str) -> dict[str, Any]:
    """List configured context packs for a project.

    Args:
        project: Project name as defined in the server registry.
    """
    config = _project_config(project)
    packs = _make_context_pack_loader(config).list_packs()
    return {
        "project": project,
        "context_packs": [pack.as_response() for pack in packs],
        "returned_count": len(packs),
    }


@mcp.tool()
def propose_memory_update(
    project: str,
    file_path: str,
    operation: str,
    content: str | None = None,
) -> dict[str, Any]:
    """Propose a write to a file in the `Memory/` directory.

    This is step 1 of a two-step workflow: call this tool to create a
    proposal, then call `approve_proposal` with the returned `proposal_id`
    to apply the change to disk.  The file is not modified until approval.

    Use `list_context_packs` first to discover the correct `project` name.
    Only files under `Memory/` are accepted — paths starting with anything
    else (e.g. `wiki/`) are rejected with a guardrail error.

    Args:
        project: Project name from the server registry — use the same value
            returned by `list_context_packs` (e.g. "occlave").
        file_path: Vault-relative path that must begin with `Memory/`
            (for example, `Memory/company-summary.md`).
        operation: One of "create" (target must not exist), "update"
            (target must already exist), or "delete".
        content: Full file content for create/update; omit for delete.
            Prefer focused, concise notes — very large content (> 8 KB)
            should be split into multiple smaller Memory files.
    """
    _require_memory_path(file_path)
    config = _project_config(project)
    result = ProposalManager(config).create(
        file_path=file_path,
        operation=operation,
        content=content,
    )
    return {"project": project, **result.as_response()}


@mcp.tool()
def list_proposals(
    project: str,
    status: str | None = "pending",
    file_path: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List proposal metadata with status and optional file-path filters.

    Args:
        project: Project name as defined in the server registry.
        status: Optional proposal status filter. Defaults to pending.
        file_path: Optional vault-relative proposal target path.
        limit: Maximum number of proposals to return.
    """
    config = _project_config(project)
    proposals = ProposalManager(config).list(
        status=status,
        file_path=file_path,
        limit=limit,
    )
    return {
        "project": project,
        "proposals": [proposal.as_response() for proposal in proposals],
        "returned_count": len(proposals),
    }


@mcp.tool()
def approve_proposal(project: str, proposal_id: str) -> dict[str, Any]:
    """Apply a pending proposal to disk (step 2 of the write workflow).

    Call this immediately after `propose_memory_update` succeeds to
    commit the change.  The file is only written when this call returns
    status "applied".

    Args:
        project: Project name — same value used in `propose_memory_update`.
        proposal_id: The `proposal_id` returned by `propose_memory_update`.
    """
    config = _project_config(project)
    result = ProposalManager(config).approve(proposal_id, actor="mcp")
    return {"project": project, **result.as_response()}


@mcp.tool()
def reject_proposal(
    project: str,
    proposal_id: str,
    reason: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Discard a pending proposal without writing any file.

    Args:
        project: Project name — same value used in `propose_memory_update`.
        proposal_id: The `proposal_id` returned by `propose_memory_update`.
    """
    config = _project_config(project)
    result = ProposalManager(config).reject(
        proposal_id,
        reason=reason,
        notes=notes,
        actor="mcp",
    )
    return {"project": project, **result.as_response()}


def _project_config(project: str) -> ProjectConfig:
    registry = load_project_registry()
    return load_project_config(registry.resolve(project))


def _make_context_pack_loader(config: ProjectConfig) -> ContextPackLoader:
    return ContextPackLoader(config)


def _require_memory_path(file_path: str) -> None:
    normalized_path = file_path.replace("\\", "/").strip()
    path = PurePosixPath(normalized_path)
    if len(path.parts) >= 2 and path.parts[0] == "Memory":
        return
    raise ToolExecutionError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=(
                "propose_memory_update only supports files under 'Memory/'. "
                f"Received '{file_path}'."
            ),
            details={"file_path": file_path, "required_prefix": "Memory/"},
        )
    )
