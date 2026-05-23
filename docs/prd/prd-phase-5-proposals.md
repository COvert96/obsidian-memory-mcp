# PRD: Phase 5 - Guarded Propose-Only Update Workflow

## Introduction

Implement a safety-first write workflow: `propose_memory_update` creates a proposal without writing to disk, `list_proposals` shows pending proposals, and `approve_proposal` applies approved proposals. This guards against accidental/malicious overwrites and ensures all memory updates are explicit and traceable.

## Goals

- Implement propose-only memory updates (no disk writes during proposal creation)
- Store proposals with metadata: id, target file, old hash, TTL, validation status
- Enable explicit approval workflow before any file modification
- Prevent stale/invalid proposals from being applied
- Maintain audit trail of who proposed what and when

## User Stories

### US-001: Implement propose_memory_update MCP tool
**Description:** As a tool user, I want to propose a memory update without writing to disk so I can review it first.

**Acceptance Criteria:**
- [ ] Tool parameters: `file_path` (required), `operation` (required: "create"|"update"|"delete"), `content` (required for create/update, optional for delete)
- [ ] Returns: `{ proposal_id: str, file_path: str, operation: str, old_hash: str, new_hash: str, ttl_seconds: int }`
- [ ] Proposal validated against guardrails before storage (file path is writable)
- [ ] Returns error `ERR_GUARDRAIL_VIOLATION` if file path is not writable
- [ ] Proposal stored with unique ID (UUID or sequential)
- [ ] TTL default: 3600 seconds (1 hour), configurable
- [ ] No disk write occurs during proposal creation
- [ ] Old content hash computed for update/delete operations
- [ ] New content hash computed for create/update operations
- [ ] Performance: proposal creation <100ms even for large files

### US-002: Design proposal storage and metadata
**Description:** As a developer, I need a schema for proposals so they can be stored, queried, and validated.

**Acceptance Criteria:**
- [ ] Proposals stored in SQLite table: `id`, `file_path`, `operation`, `old_hash`, `new_hash`, `content` (text), `created_at`, `expires_at`, `status` (pending|approved|rejected|applied)
- [ ] Unique index on `id` (proposal ID)
- [ ] Proposals indexed by `file_path` (query by target file)
- [ ] Proposals indexed by `created_at` (clean up expired)
- [ ] Each proposal stores full new content (for review before approval)
- [ ] Hash comparison enables conflict detection (if old_hash doesn't match current, reject)
- [ ] Status transitions: pending → approved → applied, or pending → rejected

### US-003: Implement list_proposals MCP tool
**Description:** As a tool user, I want to see pending proposals so I can review them before approval.

**Acceptance Criteria:**
- [ ] Tool parameters: `status` (optional: all|pending|approved|rejected), `file_path` (optional filter), `limit` (optional, default 10)
- [ ] Returns: array of proposals with `{ id, file_path, operation, status, created_at, expires_at, preview }`
- [ ] Preview shows first 200 chars of content for create/update operations
- [ ] Results sorted by creation time (newest first)
- [ ] Handles expired proposals: automatically expire old proposals before returning
- [ ] Performance: <200ms even with 1000s of historical proposals
- [ ] Supports filtering by: status, file path, age

### US-004: Implement approve_proposal MCP tool
**Description:** As a tool user, I want to approve a proposal so it gets written to disk.

**Acceptance Criteria:**
- [ ] Tool parameters: `proposal_id` (required)
- [ ] Returns error if proposal doesn't exist: `ERR_INVALID_REQUEST`
- [ ] Returns error if proposal expired: `ERR_STALE_PROPOSAL`
- [ ] Before applying, verify current file state matches old_hash
  - If mismatch, return error `ERR_STALE_PROPOSAL` with message: "File changed since proposal created; review new state before reapproving"
- [ ] On success: write content to disk, mark proposal as `applied`, return result
- [ ] Disk write is atomic: use temp file + rename pattern
- [ ] Record write timestamp and success in proposal metadata
- [ ] Returns: `{ proposal_id, file_path, operation, status: "applied", written_at, file_size_bytes }`
- [ ] For create operation: create parent directories if needed
- [ ] For delete operation: confirm file still exists, return error if not
- [ ] Performance: approval <200ms including disk write

### US-005: Implement proposal validation and conflict detection
**Description:** As a tool user, I need to know if a proposal is valid and safe to apply.

**Acceptance Criteria:**
- [ ] Validation checks:
  - File path is writable per guardrails
  - Proposal not expired
  - For update/delete: current file hash matches old_hash (no concurrent edits)
  - New content is valid UTF-8 markdown (basic syntax check)
- [ ] Validation error messages are clear: "File was modified at 2026-05-23 10:15 by external edit; old_hash mismatch"
- [ ] Validation runs when proposal is created (flag as valid/invalid in storage)
- [ ] Stale proposal detection: if proposal not approved within 1 hour, automatically rejected
- [ ] Proposal can't be re-approved after expiry (returns error)

### US-006: Create CLI commands for proposal management
**Description:** As an operator, I need CLI tools to manage proposals safely.

**Acceptance Criteria:**
- [ ] Command: `mcp-memory proposals list [--status pending|approved|all]` — show all proposals
- [ ] Command: `mcp-memory proposals show {proposal_id}` — show full proposal with diff preview
- [ ] Command: `mcp-memory proposals approve {proposal_id}` — apply a proposal
- [ ] Command: `mcp-memory proposals reject {proposal_id}` — mark as rejected (don't apply)
- [ ] Command: `mcp-memory proposals cleanup` — remove expired proposals
- [ ] Output shows: file path, operation, content preview, age, expiry countdown
- [ ] Approval requires explicit confirmation: "Apply proposal to {file_path}? yes/no"
- [ ] Diff view (unified diff format) for update operations

### US-007: Implement audit trail and history
**Description:** As an operator, I need an audit log so I can track what was proposed, approved, and applied.

**Acceptance Criteria:**
- [ ] Audit log table: `timestamp`, `proposal_id`, `action` (proposed|approved|rejected|applied), `user` (optional), `notes`
- [ ] Log entries created for: proposal creation, approval, rejection, application, expiry
- [ ] Command: `mcp-memory proposals audit [--since 24h|7d]` — show recent activity
- [ ] Audit log shows: who did what to which proposal when
- [ ] Audit log output in JSON for machine parsing
- [ ] Audit log retained indefinitely (not deleted with proposals)

## Functional Requirements

- FR-1: `propose_memory_update` creates non-mutating proposal with unique ID
- FR-2: Proposal stored with: file path, operation, old/new hash, content, TTL, status
- FR-3: `list_proposals` returns pending/approved proposals with filtering
- FR-4: `approve_proposal` checks hash, writes to disk atomically, updates status
- FR-5: Validation prevents stale proposals (hash mismatch detection)
- FR-6: Automatic expiry of proposals after configurable TTL
- FR-7: Audit log tracks all proposal lifecycle events
- FR-8: CLI tools for proposal review, approval, rejection, cleanup

## Non-Goals

- No diff computation or merge conflict resolution (simple overwrite only)
- No collaborative approval workflow (single approval per proposal)
- No proposal revert (once applied, permanent unless new proposal created)
- No scheduling or automation of approval
- No encryption of proposal content (assume vault filesystem is protected)

## Technical Considerations

- **Proposal Storage:** SQLite table in same database as index
- **ID Generation:** UUID v4 or sequential (both deterministic, UUID preferred for uniqueness)
- **Hash Computation:** SHA256 of file content for comparison
- **Atomic Writes:** Write to temp file with `.tmp` suffix, then `os.rename()` (atomic on POSIX/Windows)
- **TTL Enforcement:** Check expiry on list/approve operations, clean up expired on `proposals cleanup` or periodic task
- **Conflict Detection:** Compare old_hash against current file before applying
- **Audit Logging:** Append-only log, timestamp in UTC, JSON format for queries

## Success Metrics

- [ ] Zero accidental overwrites: 100% of modifications go through approval workflow
- [ ] No data loss: hash mismatch detection prevents concurrent-edit conflicts
- [ ] Audit trail complete: every proposal lifecycle event logged
- [ ] Approval latency <200ms on typical files
- [ ] Proposal expiry enforcement: zero stale proposals applied (>1 hour old)
- [ ] Operator can review, approve, or reject any proposal in <10 seconds

## Open Questions

- Should proposal approval be reversible (undo recent approvals)?
  A: Not for MVP.
- Should proposals support dry-run preview before approval?
  A: Yes.
- Should multiple proposals be approvable in batch, or one-at-a-time?
  A: Yes approvable in batch.
- Should approval require additional authentication/signing for sensitive paths?
  A: No.
- Should proposal content be compressed if very large (e.g., >1MB)?
  A: No.

## Dependencies

- Phase 0 must be complete (error codes, validation approach)
- Phase 1 must be complete (config loading, guardrails, write constraints)
- Phase 2 helpful for indexing proposals alongside notes (optional)
- Phase 3-4 independent (can implement in parallel)

## Deliverables

- `src/obsidian_memory_mcp/proposals.py` with ProposalManager, ProposalValidator, AuditLog
- `src/obsidian_memory_mcp/tools.py` — add MCP tools: `propose_memory_update`, `list_proposals`, `approve_proposal`
- `src/obsidian_memory_mcp/cli.py` — add proposal CLI commands (list, show, approve, reject, cleanup, audit)
- `tests/unit/test_proposals.py` with proposal creation, validation, expiry tests
- `tests/unit/test_approval_workflow.py` with hash conflict, concurrent edit tests
- `tests/integration/test_proposal_tools.py` with end-to-end workflow tests
- `docs/proposal-workflow.md` with explanation and examples
- `docs/audit-log-guide.md` with operator guide to reviewing and understanding audit logs
