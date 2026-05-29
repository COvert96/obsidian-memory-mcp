# Write Tools Guide

v0.2.0 writes are direct and atomic. There is no staging or approval step: the
four CRUD tools write to the vault immediately, behind the configured write
guardrails, and append one row to the append-only `write_audit` log on success.

| Tool | Scope | Precondition |
|---|---|---|
| `write_memory` | Creates a file under `Memory/**` | File must not exist (`ERR_FILE_EXISTS` otherwise) |
| `write_note` | Creates a file at any allowed path outside `Memory/` | File must not exist |
| `update_memory` | Overwrites an existing `Memory/**` file | File must exist (`ERR_MISSING_FILE` otherwise) |
| `update_note` | Overwrites an existing file outside `Memory/` | File must exist |

Every path is checked against `write_constraints.write`; a violation raises
`ERR_GUARDRAIL_VIOLATION`. Content over `max_write_content_bytes` is rejected
with `ERR_INVALID_REQUEST`.

## Optimistic-lock conflict detection

`update_memory` and `update_note` accept an optional `expected_hash`. Pass the
`content_hash` returned by the most recent `read_note`; if the file changed on
disk since then, the write is rejected with `ERR_HASH_MISMATCH` and nothing is
written. Call `read_note` again to get the current hash, then retry.

## Supersession

When a new note replaces older ones, pass their vault-relative paths to
`update_memory` as `supersedes`. In a single call the server:

1. Validates every superseded path up front (scope, existence, no
   self-supersession; duplicates are de-duplicated). No file is touched until
   validation passes.
2. Writes the new/updated note.
3. Moves each superseded note into `memory_archive_path` (default
   `Memory/archive`), stamping it with `superseded: true`, `superseded_by`, and
   `superseded_at` frontmatter.
4. Adds a `supersedes` frontmatter list to the new note pointing at the archive
   paths.
5. Appends exactly one `write_audit` row carrying the archive paths.

Same-named notes archived from different folders are disambiguated with a short
UUID suffix, so the archive never overwrites an existing file. The archive is an
ordinary vault directory: search it with `search_notes`, and move a note back
with `write_note` to un-archive it manually.

```json
{
  "project": "sample",
  "file_path": "Memory/company-summary.md",
  "content": "# Company Summary\nCurrent source of truth.\n",
  "supersedes": ["Memory/company-summary-draft.md"]
}
```

## Audit log

Inspect the append-only write log from the vault root:

```powershell
mcp-memory audit writes [vault_path] [--project NAME] [--file-path PATH] [--limit 50]
```

Each row records `occurred_at`, `tool`, `project`, `file_path`, `operation`, and
the content hash. Supersession writes additionally record the archived paths.

## Configuration

```yaml
max_write_content_bytes: 1048576
memory_archive_path: "Memory/archive"
```

`max_write_content_bytes` caps the UTF-8 byte size of written content.
`memory_archive_path` is a relative path under `Memory/` and defaults to
`Memory/archive` when omitted.
