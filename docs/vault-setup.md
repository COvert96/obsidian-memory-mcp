# Vault Setup

This guide sets up one Obsidian vault as one isolated Memory MCP project.

## 1. Create The Vault Structure

Create the vault directory and the folders you want tools to read or write:

```powershell
mkdir path\to\example-vault
mkdir path\to\example-vault\wiki
mkdir path\to\example-vault\wiki\proposals
mkdir path\to\example-vault\docs\prd
```

## 2. Add `memory-mcp.yaml`

Copy `docs/config-example.yaml` to the vault root as `memory-mcp.yaml`, then set:

- `vault_path`: absolute path to the vault root.
- `index_db_location`: SQLite index path. Relative paths stay inside the vault.
- `context_packs`: named groups of files used for curated context.
- `write_constraints`: read/write allow and deny rules.
- `max_write_content_bytes`: maximum UTF-8 size for content written by the write tools.
- `memory_archive_path`: relative path under `Memory/` where `update_memory`
  archives superseded notes. Defaults to `Memory/archive` when omitted.

Minimum shape:

```yaml
vault_path: "path/to/example-vault"
index_db_location: "memory-index.sqlite3"
context_packs:
  - name: "default"
    paths:
      - "wiki/**/*.md"
write_constraints:
  read:
    allow:
      - "wiki/**"
  write:
    allow:
      - "Memory/**"
max_write_content_bytes: 1048576
memory_archive_path: "Memory/archive"
```

### Archive directory convention

When `update_memory` is called with a `supersedes` list, each superseded note is
moved (flattened to its filename) into `memory_archive_path` and stamped with
`superseded: true`, `superseded_by`, and `superseded_at` frontmatter. The new note
gains a `supersedes` frontmatter list pointing at the archived paths. Same-named
notes from different folders are disambiguated with a short UUID suffix, so the
archive never overwrites an existing file. The archive is an ordinary vault
directory — search it with `search_notes`, and move a note back with `write_note`
if you need to un-archive it.

## 3. Validate The Config

Run the CLI from this repository:

```powershell
uv run mcp-memory config validate path\to\example-vault
```

Expected success:

```text
Config is valid: path\to\example-vault
```

If validation fails, the CLI prints every invalid field and a suggested fix.

## 4. Choose Guardrails

Guardrails are default-deny. A path must match an `allow` rule for the operation, and `deny`
rules override `allow` rules.

Supported patterns:

- Explicit file: `wiki/index.md`
- Directory: `wiki/proposals/`
- Glob: `wiki/**/*.md`

Read-heavy wiki:

```yaml
write_constraints:
  read:
    allow:
      - "wiki/**"
      - "docs/**/*.md"
  write:
    allow:
      - "wiki/proposals/"
    deny:
      - "wiki/log.md"
```

Writable memory vault:

```yaml
write_constraints:
  read:
    allow:
      - "**/*.md"
  write:
    allow:
      - "Memory/"
      - "wiki/proposals/"
    deny:
      - "Memory/private/**"
```

## Common Errors

- `Config file not found`: create `{vault_root}/memory-mcp.yaml`.
- `vault_path must be an absolute path`: use the full filesystem path.
- `vault_path must be an existing directory`: create the vault or fix the path.
- `index_db_location must be a path inside vault_path`: use a relative path such as `memory-index.sqlite3`.
- `ERR_GUARDRAIL_VIOLATION`: the requested path escaped the vault or did not match the configured allow rules.
