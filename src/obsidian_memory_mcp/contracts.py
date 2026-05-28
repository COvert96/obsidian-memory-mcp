"""Tool contracts: canonical definitions of each MCP tool's interface.

Each `ToolContract` records the tool's name, description, possible error codes,
and representative example payloads.  `TOOL_ERROR_CODES` is derived from
`TOOL_CONTRACTS` and provides a convenient mapping from tool name to its error
tuple without maintaining a separate, drift-prone list.
"""

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


TOOL_CONTRACTS: dict[str, ToolContract] = {
    "read_note": ToolContract(
        name="read_note",
        description="Read a full markdown note from a configured project vault.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_MISSING_FILE,
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "note_path": "wiki/concepts/compliance-as-code.md",
        },
        example_response={
            "project": "occlave",
            "file_path": "wiki/concepts/compliance-as-code.md",
            "content": "---\ntype: concept\n---\n# Compliance as Code\n...",
            "frontmatter": {"type": "concept"},
            "file_size_bytes": 412,
        },
    ),
    "read_section": ToolContract(
        name="read_section",
        description="Read a single heading section with nearby context lines.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_MISSING_FILE,
            ErrorCode.ERR_SECTION_NOT_FOUND,
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "note_path": "wiki/concepts/compliance-as-code.md",
            "heading_name": "Definition",
        },
        example_response={
            "project": "occlave",
            "file_path": "wiki/concepts/compliance-as-code.md",
            "heading": "Definition",
            "heading_level": 2,
            "content": "## Definition\nCompliance controls encoded as executable rules.",
            "context_prefix": "Compliance overview.",
        },
    ),
    "search_notes": ToolContract(
        name="search_notes",
        description="Run deterministic full-text search over indexed notes.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "query": "continuous compliance",
            "limit": 5,
            "tags": ["compliance"],
            "paths": ["wiki/concepts/**"],
            "exclude_paths": ["wiki/private/**"],
        },
        example_response={
            "project": "occlave",
            "query": "continuous compliance",
            "results": [
                {
                    "file_path": "wiki/concepts/continuous-compliance.md",
                    "heading": "Definition",
                    "heading_level": 2,
                    "preview": "...continuous compliance keeps evidence current...",
                    "rank": 1.25,
                    "tags": ["compliance"],
                }
            ],
            "returned_count": 1,
        },
    ),
    "get_context_pack": ToolContract(
        name="get_context_pack",
        description=(
            "Load a deterministic, budget-bound pack of curated project context. "
            "Call list_context_packs first when pack_name is unknown."
        ),
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "pack_name": "prd",
            "strict_budget": True,
        },
        example_response={
            "project": "occlave",
            "pack_name": "prd",
            "content": "<!-- From: docs/prd/master.md -->\n# Product Roadmap\n...",
            "token_count": 732,
            "files_included": ["docs/prd/master.md"],
            "missing_files": [],
            "warnings": [],
        },
    ),
    "list_context_packs": ToolContract(
        name="list_context_packs",
        description=(
            "List configured context packs and metadata so clients can select "
            "a valid pack_name."
        ),
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
        },
        example_response={
            "project": "occlave",
            "context_packs": [
                {
                    "pack_name": "overview",
                    "description": "High-level project documentation.",
                    "token_budget": 8000,
                    "path_patterns": ["docs/overview/*.md"],
                    "sections": [],
                    "tags_filter": [],
                    "include_context_packs": [],
                }
            ],
            "returned_count": 1,
        },
    ),
    "propose_memory_update": ToolContract(
        name="propose_memory_update",
        description=(
            "Create a guarded write proposal for files under Memory/ without "
            "mutating the target file."
        ),
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_MISSING_FILE,
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "file_path": "Memory/company-summary.md",
            "operation": "update",
            "content": "# Company Summary\nUpdated content.",
        },
        example_response={
            "project": "occlave",
            "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
            "file_path": "Memory/company-summary.md",
            "operation": "update",
            "old_hash": "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887",
            "new_hash": "bef4b0b23bc6e4fcbf64cfd9d3405fceea27191c0b37db114d4e62ebccb8eaf7",
            "ttl_seconds": 3600,
        },
    ),
    "list_proposals": ToolContract(
        name="list_proposals",
        description="List proposal metadata with status and preview filters.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "status": "pending",
            "limit": 10,
        },
        example_response={
            "project": "occlave",
            "proposals": [
                {
                    "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
                    "file_path": "Memory/company-summary.md",
                    "operation": "update",
                    "status": "pending",
                    "created_at": "2026-05-23T10:00:00Z",
                    "expires_at": "2026-05-23T11:00:00Z",
                    "preview": "# Company Summary\\nUpdated content.",
                }
            ],
            "returned_count": 1,
        },
    ),
    "approve_proposal": ToolContract(
        name="approve_proposal",
        description="Apply a validated proposal to disk and mark it as applied.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_STALE_PROPOSAL,
            ErrorCode.ERR_GUARDRAIL_VIOLATION,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
        },
        example_response={
            "project": "occlave",
            "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
            "file_path": "Memory/company-summary.md",
            "operation": "update",
            "status": "applied",
            "written_at": "2026-05-23T10:15:00Z",
            "file_size_bytes": 128,
        },
    ),
    "reject_proposal": ToolContract(
        name="reject_proposal",
        description="Reject a pending proposal without applying file changes.",
        possible_errors=(
            ErrorCode.ERR_INVALID_REQUEST,
            ErrorCode.ERR_INVALID_PROJECT,
            ErrorCode.ERR_STALE_PROPOSAL,
            ErrorCode.ERR_INTERNAL,
        ),
        example_request={
            "project": "occlave",
            "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
            "reason": "duplicate",
            "notes": "Superseded by a grouped memory changeset.",
        },
        example_response={
            "project": "occlave",
            "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
            "file_path": "Memory/company-summary.md",
            "operation": "update",
            "status": "rejected",
            "rejected_at": "2026-05-23T10:15:00Z",
            "reason": "duplicate",
        },
    ),
}

# Derived from TOOL_CONTRACTS - no separate list to maintain.
# Use this when you need only the error codes without the full contract.
TOOL_ERROR_CODES: dict[str, tuple[ErrorCode, ...]] = {
    name: contract.possible_errors for name, contract in TOOL_CONTRACTS.items()
}
