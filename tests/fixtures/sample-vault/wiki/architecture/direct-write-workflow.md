---
tags: [architecture, writes, audit]
type: concept
---
# Direct Write Workflow Architecture

v0.2.0 applies vault writes immediately through the four CRUD MCP tools. Each successful write appends one row to the append-only `write_audit` log. Guardrails, optimistic-lock hashes, and supersession archiving provide safety without a staging step.

## Design Rationale

Direct writes keep operator workflows simple: agents call `write_memory` or `update_memory`, and the vault reflects the change atomically. Auditability comes from the `write_audit` table and optional `expected_hash` conflict detection rather than a separate approval queue.

## Write Lifecycle

1. Validate the vault-relative path against write guardrails.
2. Enforce create-vs-update preconditions (`ERR_FILE_EXISTS` / `ERR_MISSING_FILE`).
3. Optionally compare `expected_hash` from the latest `read_note` (`ERR_HASH_MISMATCH` on drift).
4. Write via temp-file rename and record the audit row.

## Supersession

`update_memory` may archive older `Memory/**` notes under `memory_archive_path`, stamp supersession frontmatter, and back-reference archive paths from the new note in a single audited operation.
