# MCP Tool Reference

`src/obsidian_memory_mcp/contracts.py` is the authoritative metadata source for tool descriptions, example payloads, and possible error codes. `src/obsidian_memory_mcp/server.py` is the authoritative live registration surface. Both define the same 9 tools for the MVP release.

Examples below use the fixture project name `sample` and paths from `tests/fixtures/sample-vault/`.

## Common Response Shape

Successful tools return JSON content through MCP. Error responses are surfaced by FastMCP as tool errors whose text contains one of the documented error codes. See [error-codes.md](error-codes.md).

## read_note

Request fields: `project` string, `note_path` vault-relative markdown path.

Response fields: `project`, `file_path`, `content`, `frontmatter`, `file_size_bytes`, `content_hash`. `content_hash` is the SHA-256 of the raw file bytes; pass it as `expected_hash` to `update_memory` or `update_note` for optimistic-lock conflict detection.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL`.

```json
{"project": "sample", "note_path": "wiki/concepts/compliance-as-code.md"}
```

## read_section

Request fields: `project`, `note_path`, `heading_name`.

Response fields: `project`, `file_path`, `heading`, `heading_level`, `content`, `context_prefix`, `context_suffix`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_SECTION_NOT_FOUND`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL`.

```json
{"project": "sample", "note_path": "wiki/concepts/compliance-as-code.md", "heading_name": "Evidence Pipeline"}
```

## search_notes

Request fields: `project`, `query`, optional `limit`, optional `tags`, optional `paths`, optional `exclude_paths`.

Response fields: `project`, `query`, `results`, `returned_count`. Each result includes `file_path`, `heading`, `heading_level`, `preview`, `rank`, and `tags`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "query": "strict budget",
  "limit": 3,
  "paths": ["wiki/**"],
  "exclude_paths": ["wiki/private/**"]
}
```

## get_context_pack

Request fields: `project`, `pack_name`, optional `strict_budget`.

Response fields: `project`, `pack_name`, `content`, `token_count`, `files_included`, `missing_files`, `warnings`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_CONTEXT_EXCEEDS_BUDGET`, `ERR_INTERNAL`.

```json
{"project": "sample", "pack_name": "default", "strict_budget": true}
```

## list_context_packs

Request fields: `project`.

Response fields: `project`, `context_packs`, `returned_count`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL`.

```json
{"project": "sample"}
```

## propose_memory_update

Request fields: `project`, `file_path`, `operation`, optional `content`. `operation` is `create`, `update`, or `delete`. The path must be under `Memory/`.

Response fields: `project`, `proposal_id`, `file_path`, `operation`, `old_hash`, `new_hash`, `ttl_seconds`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "file_path": "Memory/release-note.md",
  "operation": "create",
  "content": "# Release Note\nReviewed memory update.\n"
}
```

## list_proposals

Request fields: `project`, optional `status`, optional `file_path`, optional `limit`.

Response fields: `project`, `proposals`, `returned_count`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_INTERNAL`.

```json
{"project": "sample", "status": "pending", "limit": 10}
```

## approve_proposal

Request fields: `project`, `proposal_id`.

Response fields: `project`, `proposal_id`, `file_path`, `operation`, `status`, `written_at`, `file_size_bytes`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_STALE_PROPOSAL`, `ERR_GUARDRAIL_VIOLATION`, `ERR_INTERNAL`.

```json
{"project": "sample", "proposal_id": "550e8400-e29b-41d4-a716-446655440000"}
```

## reject_proposal

Request fields: `project`, `proposal_id`, optional `reason`, optional `notes`.

Response fields: `project`, `proposal_id`, `file_path`, `operation`, `status`, `rejected_at`, `reason`.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_STALE_PROPOSAL`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "reason": "duplicate",
  "notes": "Covered by a grouped changeset."
}
```

## update_memory

Request fields: `project`, `file_path` (must begin with `Memory/`), `content`, optional `expected_hash`.

Response fields: `project`, `file_path`, `operation`, `content_hash`, `file_size_bytes`, `written_at`.

The target file must already exist. When `expected_hash` is supplied and no longer matches the on-disk content, the call is rejected with `ERR_HASH_MISMATCH` and nothing is written.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_HASH_MISMATCH`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "file_path": "Memory/release-note.md",
  "content": "# Release Note\nRevised memory.\n",
  "expected_hash": "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887"
}
```

## update_note

Request fields: `project`, `file_path` (any config-allowed path outside `Memory/`), `content`, optional `expected_hash`. Use `update_memory` for `Memory/` files.

Response fields and error codes are identical to `update_memory`.

```json
{
  "project": "sample",
  "file_path": "wiki/concepts/compliance-as-code.md",
  "content": "# Compliance as Code\nRevised.\n",
  "expected_hash": "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887"
}
```

## audit writes (CLI)

`mcp-memory audit writes [vault_path] [--project NAME] [--file-path PATH] [--limit 50]` prints the append-only write log as a table: `occurred_at | tool | project | file_path | operation | content_hash[:12]`. Every successful `write_memory`, `write_note`, `update_memory`, and `update_note` call appends one row.

## Workflows

Search and retrieve:

1. Call `search_notes` with a topic query and `limit`.
2. Use a returned `file_path` with `read_note` for full context or `read_section` for a specific heading.

Load context pack:

1. Call `list_context_packs`.
2. Call `get_context_pack` with the chosen `pack_name`.
3. If `ERR_CONTEXT_EXCEEDS_BUDGET` occurs, retry with a smaller pack or `strict_budget: false`.

Propose and review memory update:

1. Call `propose_memory_update` for a `Memory/**` path.
2. Call `list_proposals` to confirm pending state.
3. Review the proposal with the CLI if needed.
4. Call `approve_proposal` to write, or `reject_proposal` to discard.
