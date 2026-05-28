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
mcp-memory proposals show {proposal_or_changeset_id} --diff
mcp-memory proposals approve {proposal_id}
mcp-memory proposals reject {proposal_id} --reason duplicate --notes "Superseded by another proposal"
mcp-memory proposals audit --proposal-id {proposal_id}
mcp-memory proposals cleanup --retention-days 7 --yes
```

Approval prints a preview for create/update proposals and requires typing
`YES` before any disk write occurs. When the identifier is a grouped changeset,
approval prints every affected file and applies the group as one logical workflow.

`show --diff` prints a unified diff for a single proposal or for every proposal
inside a grouped changeset. `audit` queries lifecycle records separately from the
primary proposal list. `cleanup` expires pending records and removes terminal
records older than the configured retention window.

## Configuration

Proposal TTL defaults to 3600 seconds. Configure a project-specific TTL in
`memory-mcp.yaml`:

```yaml
proposal_ttl_seconds: 3600
max_proposal_ttl_hours: 24
max_proposal_content_bytes: 1048576
proposal_retention_days: 7
```

`max_proposal_ttl_hours` remains an upper bound; the effective TTL is the lower
of `proposal_ttl_seconds` and that maximum. `max_proposal_content_bytes` limits
the UTF-8 byte size stored in SQLite for create/update proposals.
`proposal_retention_days` controls how long applied, rejected, and expired
proposal records remain available for audit before cleanup can remove them.
