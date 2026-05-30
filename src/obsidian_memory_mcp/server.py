"""MCP server - tool registration and request handling.

Follows the FastMCP pattern: a module-level ``mcp`` instance with
``@mcp.tool()``-decorated functions.  FastMCP handles transport, JSON-RPC
framing, schema generation, and error serialisation.

Domain exceptions (``ToolExecutionError``) raised inside tool functions
propagate naturally to FastMCP, which converts them to
``CallToolResult(isError=True)`` responses.  No manual error-wrapping needed.

Index schema is migrated lazily on first tool access per project via
``ensure_index_migrated()`` in ``_project_config`` (memoized per DB path).
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
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.migrations import MigrationError, ensure_index_migrated
from obsidian_memory_mcp.retrieval import (
    ReadNoteService,
    ReadSectionService,
    SearchService,
)
from obsidian_memory_mcp.server_registry import load_project_registry
from obsidian_memory_mcp.writes import (
    SupersessionService,
    WriteAuditRepository,
    WriteService,
    is_memory_path,
    require_memory_path,
)

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
def write_memory(project: str, file_path: str, content: str) -> dict[str, Any]:
    """Create a new file under Memory/ directly without a staging step.

    Use `list_context_packs` first to discover the correct `project` name.
    The file must not already exist — use the appropriate update tool to
    modify an existing memory file.

    Args:
        project: Project name from the server registry.
        file_path: Vault-relative path that must begin with `Memory/`
            (for example, `Memory/company-summary.md`).
        content: Full file content to write.
    """
    require_memory_path(file_path, "write_memory")
    config = _project_config(project)
    result = _write_service(config, tool="write_memory", project=project).create(
        file_path,
        content,
    )
    return {"project": project, **result.as_response()}


@mcp.tool()
def write_note(project: str, file_path: str, content: str) -> dict[str, Any]:
    """Create a new vault note at any config-allowed path outside Memory/.

    Use this tool for non-memory notes. Paths under `Memory/` are rejected —
    use `write_memory` instead. The file must not already exist.

    Args:
        project: Project name from the server registry.
        file_path: Vault-relative path outside `Memory/`
            (for example, `wiki/concepts/new-note.md`).
        content: Full file content to write.
    """
    _require_non_memory_path(file_path, "write_note")
    config = _project_config(project)
    result = _write_service(config, tool="write_note", project=project).create(
        file_path,
        content,
    )
    return {"project": project, **result.as_response()}


@mcp.tool()
def update_memory(
    project: str,
    file_path: str,
    content: str,
    expected_hash: str | None = None,
    supersedes: list[str] | None = None,
) -> dict[str, Any]:
    """Overwrite an existing file under Memory/ directly.

    The file must already exist — use `write_memory` to create one. To guard
    against a concurrent change, pass the `content_hash` returned by the most
    recent `read_note` as `expected_hash`; the write is rejected with
    `ERR_HASH_MISMATCH` if the file changed since.

    Pass `supersedes` with the vault-relative paths of older Memory notes this
    write replaces. Each is moved to the configured archive directory, stamped
    with supersession frontmatter, and back-referenced from this note.

    Args:
        project: Project name from the server registry.
        file_path: Vault-relative path that must begin with `Memory/`.
        content: Full replacement file content.
        expected_hash: Optional content_hash from read_note for conflict detection.
        supersedes: Optional vault-relative Memory paths to archive and link.
    """
    require_memory_path(file_path, "update_memory")
    config = _project_config(project)
    service = _write_service(config, tool="update_memory", project=project)

    if not supersedes:
        result = service.update(file_path, content, expected_hash)
        return {"project": project, **result.as_response()}

    supersession = SupersessionService(config, GuardrailEvaluator(config))
    plan = supersession.plan(supersedes, new_path=file_path)
    result = service.update(file_path, content, expected_hash, defer_audit=True)
    archived_paths = supersession.commit(
        plan, new_path=file_path, written_at=result.written_at
    )
    service.record_supersession_audit(result, archived_paths)
    return {"project": project, **result.as_response(), "supersedes": archived_paths}


@mcp.tool()
def update_note(
    project: str,
    file_path: str,
    content: str,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    """Overwrite an existing vault note at any config-allowed path outside Memory/.

    Paths under `Memory/` are rejected — use `update_memory` instead. The file
    must already exist. Pass the `content_hash` from the most recent `read_note`
    as `expected_hash` to reject concurrent changes with `ERR_HASH_MISMATCH`.

    Args:
        project: Project name from the server registry.
        file_path: Vault-relative path outside `Memory/`.
        content: Full replacement file content.
        expected_hash: Optional content_hash from read_note for conflict detection.
    """
    _require_non_memory_path(file_path, "update_note")
    config = _project_config(project)
    result = _write_service(config, tool="update_note", project=project).update(
        file_path,
        content,
        expected_hash,
    )
    return {"project": project, **result.as_response()}


def _project_config(project: str) -> ProjectConfig:
    registry = load_project_registry()
    config = load_project_config(registry.resolve(project))
    try:
        ensure_index_migrated(config.index_db_location)
    except MigrationError as exc:
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INTERNAL,
                message=(
                    f"Failed to migrate index database for project '{project}': {exc}"
                ),
                details={
                    "project": project,
                    "index_db_path": str(config.index_db_location),
                },
            )
        ) from exc
    return config


def _write_service(config: ProjectConfig, *, tool: str, project: str) -> WriteService:
    return WriteService(
        config,
        audit=WriteAuditRepository(config),
        tool=tool,
        project=project,
    )


def _require_non_memory_path(file_path: str, tool_name: str) -> None:
    if not is_memory_path(file_path):
        return
    raise ToolExecutionError(
        build_error(
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            message=(
                f"{tool_name} does not support files under 'Memory/'. "
                f"Received '{file_path}'. Use the matching memory tool instead."
            ),
            details={"file_path": file_path, "forbidden_prefix": "Memory/"},
        )
    )


def _make_context_pack_loader(config: ProjectConfig) -> ContextPackLoader:
    return ContextPackLoader(config)
