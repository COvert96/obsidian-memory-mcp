---
tags: [api, writes, memory]
---
# write_memory Tool

## Request Parameters

- `project` — registry project name
- `file_path` — vault-relative path under `Memory/`
- `content` — full file body to create

The target file must not exist. Use `update_memory` to overwrite an existing note.

## Response Fields

Returns `project`, `file_path`, `content_hash`, `written_at`, and `operation` (`create`).
