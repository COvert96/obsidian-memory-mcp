---
tags: [api, audit, writes]
---
# Write Audit Log

## CLI Inspection

`mcp-memory audit writes {vault_path}` lists recent `write_audit` rows with tool name, project, path, operation, and a short content hash prefix.

## Fields

Each row records when the write occurred, which MCP tool performed it, and the vault-relative path that changed.
