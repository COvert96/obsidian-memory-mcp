"""Tool contracts: canonical definitions of each MCP tool's interface."""

from __future__ import annotations

from dataclasses import dataclass

from obsidian_memory_mcp.contracts._examples import (
    SAMPLE_CONTENT_HASH,
    SAMPLE_PROJECT,
    project_request,
    read_tool_errors,
    write_create_errors,
    write_result,
    write_update_errors,
)
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
        possible_errors=read_tool_errors(),
        example_request=project_request(
            note_path="wiki/concepts/compliance-as-code.md",
        ),
        example_response={
            "project": SAMPLE_PROJECT,
            "file_path": "wiki/concepts/compliance-as-code.md",
            "content": "---\ntype: concept\n---\n# Compliance as Code\n...",
            "frontmatter": {"type": "concept"},
            "file_size_bytes": 412,
            "content_hash": SAMPLE_CONTENT_HASH,
        },
    ),
    "read_section": ToolContract(
        name="read_section",
        description="Read a single heading section with nearby context lines.",
        possible_errors=(
            *read_tool_errors(),
            ErrorCode.ERR_SECTION_NOT_FOUND,
        ),
        example_request=project_request(
            note_path="wiki/concepts/compliance-as-code.md",
            heading_name="Definition",
        ),
        example_response={
            "project": SAMPLE_PROJECT,
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
        example_request=project_request(
            query="continuous compliance",
            limit=5,
            tags=["compliance"],
            paths=["wiki/concepts/**"],
            exclude_paths=["wiki/private/**"],
        ),
        example_response={
            "project": SAMPLE_PROJECT,
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
        example_request=project_request(pack_name="prd", strict_budget=True),
        example_response={
            "project": SAMPLE_PROJECT,
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
        example_request=project_request(),
        example_response={
            "project": SAMPLE_PROJECT,
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
    "write_memory": ToolContract(
        name="write_memory",
        description=(
            "Create a new file under Memory/ directly without a staging step. "
            "Fails if the file already exists."
        ),
        possible_errors=write_create_errors(),
        example_request=project_request(
            file_path="Memory/company-summary.md",
            content="# Company Summary\nInitial content.",
        ),
        example_response=write_result(
            file_path="Memory/company-summary.md",
            operation="create",
            content_hash=SAMPLE_CONTENT_HASH,
            file_size_bytes=128,
        ),
    ),
    "write_note": ToolContract(
        name="write_note",
        description=(
            "Create a new vault note at any config-allowed path outside Memory/. "
            "Fails if the file already exists. Use write_memory for Memory/ files."
        ),
        possible_errors=write_create_errors(),
        example_request=project_request(
            file_path="wiki/concepts/new-concept.md",
            content="# New Concept\nContent here.",
        ),
        example_response=write_result(
            file_path="wiki/concepts/new-concept.md",
            operation="create",
            file_size_bytes=96,
        ),
    ),
    "update_memory": ToolContract(
        name="update_memory",
        description=(
            "Overwrite an existing file under Memory/ directly. Fails if the file "
            "does not exist. Pass the content_hash from read_note as expected_hash "
            "to reject concurrent changes."
        ),
        possible_errors=write_update_errors(),
        example_request=project_request(
            file_path="Memory/company-summary.md",
            content="# Company Summary\nUpdated content.",
            expected_hash=SAMPLE_CONTENT_HASH,
        ),
        example_response=write_result(
            file_path="Memory/company-summary.md",
            operation="update",
            file_size_bytes=128,
        ),
    ),
    "update_note": ToolContract(
        name="update_note",
        description=(
            "Overwrite an existing vault note at any config-allowed path outside "
            "Memory/. Fails if the file does not exist. Use update_memory for "
            "Memory/ files. Pass the content_hash from read_note as expected_hash "
            "to reject concurrent changes."
        ),
        possible_errors=write_update_errors(),
        example_request=project_request(
            file_path="wiki/concepts/compliance-as-code.md",
            content="# Compliance as Code\nRevised content.",
            expected_hash=SAMPLE_CONTENT_HASH,
        ),
        example_response=write_result(
            file_path="wiki/concepts/compliance-as-code.md",
            operation="update",
            file_size_bytes=102,
        ),
    ),
}

TOOL_ERROR_CODES: dict[str, tuple[ErrorCode, ...]] = {
    name: contract.possible_errors for name, contract in TOOL_CONTRACTS.items()
}

__all__ = [
    "TOOL_CONTRACTS",
    "TOOL_ERROR_CODES",
    "ToolContract",
]
