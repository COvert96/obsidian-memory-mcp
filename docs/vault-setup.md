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
      - "wiki/proposals/"
```

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
