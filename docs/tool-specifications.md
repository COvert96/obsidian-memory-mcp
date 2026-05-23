# Obsidian Memory MCP Tool Specifications

This document defines the Phase 0 contracts for the seven Obsidian Memory MCP tools. The canonical request and response schemas live in `src/obsidian_memory_mcp/schemas/*.json` and are validated at runtime before tool execution.

Machine-readable specification artifacts:

- `docs/tool-specifications.json`: top-level JSON contract specification for all tools.
- `docs/mcp-inspector-examples.json`: MCP inspector-ready JSON-RPC requests with expected success/error payloads.

## Validation Model

- All tool requests are validated against JSON Schema Draft 2020-12 before any tool logic runs.
- All tool responses can be validated against the matching response schema through `validate_tool_handler()`.
- Validation failures return the standard error shape:

```json
{
  "code": "ERR_INVALID_REQUEST",
  "message": "read_note request payload is invalid at 'note_path': 'note_path' is a required property",
  "details": {
    "field_path": "note_path",
    "validator": "required",
    "expected": "required property",
    "schema_path": "required",
    "suggestion": "Provide the missing required field 'note_path' and retry."
  }
}
```

## Token Estimation

`estimate_tokens(text: str) -> int` uses the `tiktoken` GPT-4 tokenizer directly:

- `tiktoken.encoding_for_model("gpt-4")` is used for counting.
- Line endings are normalized before counting so `CRLF` and `LF` produce identical counts.
- This removes heuristic drift and aligns the estimate with actual model tokenization behavior.

Developer utility:

```powershell
uv run obsidian-memory-tokens --file docs/prd/prd-phase-0-foundation.md
uv run obsidian-memory-tokens --text "# Heading`n- bullet"
```

## Error Catalog

| Code | HTTP | When it occurs | Recovery suggestion |
| --- | --- | --- | --- |
| `ERR_INVALID_REQUEST` | 400 | Request or response payload does not match schema | Fix the payload shape and retry |
| `ERR_INVALID_PROJECT` | 404 | Requested project or pack cannot be resolved from config | Use a configured project identifier |
| `ERR_MISSING_FILE` | 404 | Target note or proposal file does not exist | Verify the relative vault path |
| `ERR_SECTION_NOT_FOUND` | 404 | Requested heading does not exist in the target note | Retry with an existing heading |
| `ERR_GUARDRAIL_VIOLATION` | 403 | Read or write path violates configured vault boundaries | Use an allowed path within the vault |
| `ERR_STALE_PROPOSAL` | 409 | Proposal expired or file hash no longer matches | Recreate the proposal against current file contents |
| `ERR_CONTEXT_EXCEEDS_BUDGET` | 422 | Context pack exceeds the token budget with strict enforcement | Use a smaller pack or disable strict mode |
| `ERR_INTERNAL` | 500 | Unexpected runtime failure | Retry if transient, otherwise inspect logs |

## Tool Error Scenarios Table

The following table consolidates tool name, possible error codes, trigger conditions, and a concrete example response in one place.

| Tool | Possible error codes | When it occurs | Example response |
| --- | --- | --- | --- |
| `read_note` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` | Expected: missing file path. Unexpected: filesystem read failure. | `{"code":"ERR_MISSING_FILE","message":"File 'wiki/concepts/missing.md' does not exist in the project vault.","details":{"file_path":"wiki/concepts/missing.md"}}` |
| `read_section` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_SECTION_NOT_FOUND`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` | Expected: heading not found. Unexpected: parser failure while extracting section boundaries. | `{"code":"ERR_SECTION_NOT_FOUND","message":"Heading 'Controls' was not found in 'wiki/concepts/compliance-as-code.md'.","details":{"file_path":"wiki/concepts/compliance-as-code.md","heading_name":"Controls"}}` |
| `search_notes` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL` | Expected: query missing/invalid. Unexpected: SQLite index database connection failure. | `{"code":"ERR_INTERNAL","message":"The server encountered an unexpected internal error.","details":{"operation":"search_notes","cause":"database connection failed"}}` |
| `get_context_pack` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_CONTEXT_EXCEEDS_BUDGET`, `ERR_INTERNAL` | Expected: strict budget exceeded. Unexpected: context pack metadata lookup failure. | `{"code":"ERR_CONTEXT_EXCEEDS_BUDGET","message":"The requested context pack exceeds the configured token budget.","details":{"token_count":2049,"budget":1800,"overflow":249}}` |
| `propose_memory_update` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` | Expected: attempted write outside guardrails. Unexpected: proposal store insert failure. | `{"code":"ERR_GUARDRAIL_VIOLATION","message":"The requested file operation violates configured guardrails.","details":{"file_path":"../../outside.md"}}` |
| `list_proposals` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL` | Expected: invalid status filter. Unexpected: proposal database connection failure. | `{"code":"ERR_INTERNAL","message":"The server encountered an unexpected internal error.","details":{"operation":"list_proposals","cause":"database connection failed"}}` |
| `approve_proposal` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_STALE_PROPOSAL`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` | Expected: stale proposal hash mismatch. Unexpected: database update failure when applying proposal. | `{"code":"ERR_STALE_PROPOSAL","message":"File changed since proposal created; review new state before reapproving","details":{"proposal_id":"550e8400-e29b-41d4-a716-446655440000","file_path":"Memory/company-summary.md"}}` |

## Tool Matrix

| Tool | Request fields | Response fields | Possible errors |
| --- | --- | --- | --- |
| `read_note` | `project`, `note_path` | `project`, `file_path`, `content`, `frontmatter`, `file_size_bytes` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` |
| `read_section` | `project`, `note_path`, `heading_name` | `project`, `file_path`, `heading`, `heading_level`, `content`, `context_lines` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_SECTION_NOT_FOUND`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` |
| `search_notes` | `project`, `query`, `limit?`, `tags?`, `paths?` | `project`, `query`, `results`, `returned_count` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL` |
| `get_context_pack` | `project`, `pack_name`, `strict_budget?` | `project`, `pack_name`, `content`, `token_count`, `files_included`, `missing_files`, `warnings` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_CONTEXT_EXCEEDS_BUDGET`, `ERR_INTERNAL` |
| `propose_memory_update` | `project`, `file_path`, `operation`, `content?` | `project`, `proposal_id`, `file_path`, `operation`, `old_hash`, `new_hash`, `ttl_seconds` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` |
| `list_proposals` | `project`, `status?`, `file_path?`, `limit?` | `project`, `proposals`, `returned_count` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL` |
| `approve_proposal` | `project`, `proposal_id` | `project`, `proposal_id`, `file_path`, `operation`, `status`, `written_at`, `file_size_bytes` | `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_STALE_PROPOSAL`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL` |

## Tool Contracts

### `read_note`

Schema file: `src/obsidian_memory_mcp/schemas/read_note.json`

Example request:

```json
{
  "project": "occlave",
  "note_path": "wiki/concepts/compliance-as-code.md"
}
```

Example success response:

```json
{
  "project": "occlave",
  "file_path": "wiki/concepts/compliance-as-code.md",
  "content": "---\ntype: concept\n---\n# Compliance as Code\n...",
  "frontmatter": {
    "type": "concept"
  },
  "file_size_bytes": 412
}
```

Example error response:

```json
{
  "code": "ERR_MISSING_FILE",
  "message": "File 'wiki/concepts/missing.md' does not exist in the project vault.",
  "details": {
    "file_path": "wiki/concepts/missing.md"
  }
}
```

### `read_section`

Schema file: `src/obsidian_memory_mcp/schemas/read_section.json`

Example request:

```json
{
  "project": "occlave",
  "note_path": "wiki/concepts/compliance-as-code.md",
  "heading_name": "Definition"
}
```

Example success response:

```json
{
  "project": "occlave",
  "file_path": "wiki/concepts/compliance-as-code.md",
  "heading": "Definition",
  "heading_level": 2,
  "content": "## Definition\nCompliance controls encoded as executable rules.",
  "context_lines": 2
}
```

Example error response:

```json
{
  "code": "ERR_SECTION_NOT_FOUND",
  "message": "Heading 'Controls' was not found in 'wiki/concepts/compliance-as-code.md'.",
  "details": {
    "file_path": "wiki/concepts/compliance-as-code.md",
    "heading_name": "Controls"
  }
}
```

### `search_notes`

Schema file: `src/obsidian_memory_mcp/schemas/search_notes.json`

Example request:

```json
{
  "project": "occlave",
  "query": "continuous compliance",
  "limit": 5,
  "tags": ["compliance"],
  "paths": ["wiki/concepts/**"]
}
```

Example success response:

```json
{
  "project": "occlave",
  "query": "continuous compliance",
  "results": [
    {
      "file_path": "wiki/concepts/continuous-compliance.md",
      "heading": "Definition",
      "heading_level": 2,
      "preview": "...continuous compliance keeps evidence current...",
      "rank": 1.25,
      "tags": ["compliance"]
    }
  ],
  "returned_count": 1
}
```

Example error response:

```json
{
  "code": "ERR_INVALID_REQUEST",
  "message": "search_notes request payload is invalid at 'query': '' should be non-empty",
  "details": {
    "field_path": "query"
  }
}
```

### `get_context_pack`

Schema file: `src/obsidian_memory_mcp/schemas/get_context_pack.json`

Example request:

```json
{
  "project": "occlave",
  "pack_name": "prd",
  "strict_budget": true
}
```

Example success response:

```json
{
  "project": "occlave",
  "pack_name": "prd",
  "content": "<!-- From: docs/prd/master.md -->\n# Product Roadmap\n...",
  "token_count": 732,
  "files_included": ["docs/prd/master.md"],
  "missing_files": [],
  "warnings": []
}
```

Example error response:

```json
{
  "code": "ERR_CONTEXT_EXCEEDS_BUDGET",
  "message": "The requested context pack exceeds the configured token budget.",
  "details": {
    "token_count": 2049,
    "budget": 1800,
    "overflow": 249,
    "suggested_pack_names": ["prd-core", "engineering"]
  }
}
```

### `propose_memory_update`

Schema file: `src/obsidian_memory_mcp/schemas/propose_memory_update.json`

Example request:

```json
{
  "project": "occlave",
  "file_path": "Memory/company-summary.md",
  "operation": "update",
  "content": "# Company Summary\nUpdated content."
}
```

Example success response:

```json
{
  "project": "occlave",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_path": "Memory/company-summary.md",
  "operation": "update",
  "old_hash": "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887",
  "new_hash": "bef4b0b23bc6e4fcbf64cfd9d3405fceea27191c0b37db114d4e62ebccb8eaf7",
  "ttl_seconds": 3600
}
```

Example error response:

```json
{
  "code": "ERR_GUARDRAIL_VIOLATION",
  "message": "The requested file operation violates configured guardrails.",
  "details": {
    "file_path": "../../outside.md"
  }
}
```

### `list_proposals`

Schema file: `src/obsidian_memory_mcp/schemas/list_proposals.json`

Example request:

```json
{
  "project": "occlave",
  "status": "pending",
  "limit": 10
}
```

Example success response:

```json
{
  "project": "occlave",
  "proposals": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "file_path": "Memory/company-summary.md",
      "operation": "update",
      "status": "pending",
      "created_at": "2026-05-23T10:00:00Z",
      "expires_at": "2026-05-23T11:00:00Z",
      "preview": "# Company Summary\nUpdated content."
    }
  ],
  "returned_count": 1
}
```

Example error response:

```json
{
  "code": "ERR_INVALID_REQUEST",
  "message": "list_proposals request payload is invalid at 'status': 'queued' is not one of ['all', 'pending', 'approved', 'rejected', 'applied']",
  "details": {
    "field_path": "status"
  }
}
```

### `approve_proposal`

Schema file: `src/obsidian_memory_mcp/schemas/approve_proposal.json`

Example request:

```json
{
  "project": "occlave",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Example success response:

```json
{
  "project": "occlave",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_path": "Memory/company-summary.md",
  "operation": "update",
  "status": "applied",
  "written_at": "2026-05-23T10:15:00Z",
  "file_size_bytes": 128
}
```

Example error response:

```json
{
  "code": "ERR_STALE_PROPOSAL",
  "message": "File changed since proposal created; review new state before reapproving",
  "details": {
    "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_path": "Memory/company-summary.md"
  }
}
```

## MCP Inspector Execution

Executable MCP inspector-compatible JSON-RPC request examples are stored in `docs/mcp-inspector-examples.json`.

- Format: `{"jsonrpc":"2.0","id":"...","method":"tools/call","params":{"name":"<tool>","arguments":{...}}}`
- Validation: `tests/unit/test_contract_docs.py` validates every example request against the tool request schema and every success payload against the tool response schema.
- Coverage: includes expected failures and unexpected failures, including database connection error examples for retrieval and proposal tooling.