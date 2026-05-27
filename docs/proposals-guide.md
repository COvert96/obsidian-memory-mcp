# Proposal Workflow Guide

Phase 5A writes use a guarded proposal workflow. Proposal creation stores the
requested change in SQLite and never mutates the vault file. Approval re-checks
the write guardrail and the target file hash before applying the change.

## MCP Workflow

1. Call `propose_memory_update` with `project`, `file_path`, `operation`, and
   `content` for create/update operations.
2. Review pending work with `list_proposals`.
3. Apply with `approve_proposal` only after operator approval.
4. Reject through `reject_proposal` when the proposed change should not apply.

`approve_proposal` fails with `ERR_STALE_PROPOSAL` if the proposal expired or if
the current file hash no longer matches the hash captured at proposal creation.

## CLI Workflow

Run these commands from the vault root, or pass the vault path as the final
argument:

```powershell
mcp-memory proposals list
mcp-memory proposals approve {proposal_id}
mcp-memory proposals reject {proposal_id}
```

Approval prints a preview for create/update proposals and requires typing
`YES` before any disk write occurs.

## Configuration

Proposal TTL defaults to 3600 seconds. Configure a project-specific TTL in
`memory-mcp.yaml`:

```yaml
proposal_ttl_seconds: 3600
max_proposal_ttl_hours: 24
max_proposal_content_bytes: 1048576
```

`max_proposal_ttl_hours` remains an upper bound; the effective TTL is the lower
of `proposal_ttl_seconds` and that maximum. `max_proposal_content_bytes` limits
the UTF-8 byte size stored in SQLite for create/update proposals.
