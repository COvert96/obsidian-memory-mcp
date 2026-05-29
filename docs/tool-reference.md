# MCP Tool Reference

`src/obsidian_memory_mcp/contracts/__init__.py` is the authoritative metadata source for tool descriptions, example payloads, and possible error codes. `src/obsidian_memory_mcp/server.py` is the authoritative live registration surface. Both define the same 9 tools for the MVP release.

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

## write_memory

Request fields: `project`, `file_path` (must begin with `Memory/`), `content`.

Response fields: `project`, `file_path`, `operation`, `content_hash`, `file_size_bytes`, `written_at`.

Creates a new file under `Memory/` directly — there is no staging step. The file must not already exist; otherwise the call is rejected with `ERR_FILE_EXISTS`. Use `update_memory` to modify an existing file.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_GUARDRAIL_VIOLATION`, `ERR_FILE_EXISTS`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "file_path": "Memory/release-note.md",
  "content": "# Release Note\nInitial memory.\n"
}
```

## write_note

Request fields: `project`, `file_path` (any config-allowed path outside `Memory/`), `content`. Use `write_memory` for `Memory/` files.

Response fields and error codes are identical to `write_memory`.

```json
{
  "project": "sample",
  "file_path": "wiki/concepts/new-concept.md",
  "content": "# New Concept\nInitial content.\n"
}
```

## update_memory

Request fields: `project`, `file_path` (must begin with `Memory/`), `content`, optional `expected_hash`, optional `supersedes`.

Response fields: `project`, `file_path`, `operation`, `content_hash`, `file_size_bytes`, `written_at`. When `supersedes` is supplied, the response also includes `supersedes` — the vault-relative archive paths of the notes that were superseded.

The target file must already exist. When `expected_hash` is supplied and no longer matches the on-disk content, the call is rejected with `ERR_HASH_MISMATCH` and nothing is written.

`supersedes` is an optional list of vault-relative `Memory/` paths that this write replaces. Each superseded note is moved into the configured `memory_archive_path` (default `Memory/archive`), stamped with `superseded: true`, `superseded_by`, and `superseded_at` frontmatter, and back-referenced from this note via a `supersedes` frontmatter list. A single append-only `write_audit` row records the archive paths. Self-supersession is rejected with `ERR_INVALID_REQUEST`; a missing superseded note raises `ERR_MISSING_FILE`; all validation happens before any file is written.

Possible errors: `ERR_INVALID_REQUEST`, `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_GUARDRAIL_VIOLATION`, `ERR_HASH_MISMATCH`, `ERR_INTERNAL`.

```json
{
  "project": "sample",
  "file_path": "Memory/release-note.md",
  "content": "# Release Note\nRevised memory.\n",
  "expected_hash": "3c7b5f1d2a7e4cb68f4b33d20c342f87df8af3f8f0dcbcb3552f7c8f35ea1887",
  "supersedes": ["Memory/release-note-draft.md"]
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

Write or update memory:

1. Call `write_memory` to create a new `Memory/**` note, or `read_note` + `update_memory` to revise an existing one (passing `expected_hash` for optimistic-lock safety).
2. To replace older notes, call `update_memory` with `supersedes` listing their paths; they are archived and back-referenced automatically.
3. Inspect the append-only log with `mcp-memory audit writes`.
