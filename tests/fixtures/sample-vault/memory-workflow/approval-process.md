---
tags: [memory-workflow, writes, operations]
type: guide
---
# Post-Write Review

After automated agents call `write_memory` or `update_memory`, operators review outcomes using the write audit log and spot checks on affected files.

## Who Can Write

Write access is enforced by `write_constraints.write` guardrails in `memory-mcp.yaml`. Only paths matching allow patterns (and not deny patterns) can be created or updated.

## Pre-Write Checks

Clients should call `read_note` before `update_memory` when concurrent edits are possible. Pass the returned `content_hash` as `expected_hash` so the server can reject stale updates with `ERR_HASH_MISMATCH`.

## Hash Conflict Handling

When `expected_hash` does not match the file on disk, nothing is written. Refresh content with another `read_note`, merge changes, and retry the update.

## Post-Write Actions

Run `mcp-memory audit writes` to list recent operations, re-index if needed, and verify cross-references. See [[write-lifecycle]] and [[write-review]] for operational checklists.
