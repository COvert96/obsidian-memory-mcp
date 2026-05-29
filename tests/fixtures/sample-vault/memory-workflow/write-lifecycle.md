---
tags: [memory, writes, audit]
---
# Write Lifecycle

## States Overview

A memory file is either absent (create with `write_memory`), present (update with `update_memory`), or archived after supersession. There is no pending or rejected staging state in v0.2.0.

## Audit Record

Every successful MCP write stores `tool`, `project`, `file_path`, `operation`, `content_hash`, and `occurred_at` in `write_audit`. Operators review history with `mcp-memory audit writes`.

## Conflict Handling

When `expected_hash` does not match the on-disk file, the server returns `ERR_HASH_MISMATCH` and leaves the vault unchanged. Call `read_note` again before retrying.
