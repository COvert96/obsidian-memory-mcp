# PRD: Phase 5A - Core Proposal Workflow

## Introduction

Phase 5A implements the minimum guarded write workflow needed to move the product from read-only retrieval to safe, operator-approved writes. It focuses on straightforward single-file proposals and leaves richer workflow semantics, grouped changesets, and advanced operator tooling to Phase 5B.

## Why 5A Exists

The current codebase already documents proposal tools in contracts and architecture, but runtime behavior is still effectively read-only. Phase 5A closes that gap with the smallest safe implementation that can support real write workflows without granting direct autonomous file mutation.

Phase 5A should be built only if a real write workflow exists that is not served well enough by manual copy-paste.

## Scope

Phase 5A includes:

- `propose_memory_update`
- `list_proposals`
- `approve_proposal`
- proposal persistence
- hash-based file-state conflict detection
- expiry handling
- minimal lifecycle logging
- support for straightforward single-file create, update, and delete proposals

Phase 5A does not attempt to solve higher-level semantic workflows such as contradiction-resolving `Memory/` supersession when that requires multiple coordinated file mutations.

## Goals

- Enable safe, explicit approval before any vault mutation
- Persist proposals without writing to disk during proposal creation
- Reject stale proposals when file state changed since proposal creation
- Keep the first writable release operationally small and maintainable

## User Stories

### US-5A-001: Create a proposal without mutating disk
**Description:** As a tool user, I want to propose a file change without modifying the vault so an operator can review it first.

**Acceptance Criteria:**
- [ ] Tool parameters: `project` (required), `file_path` (required), `operation` (required: "create"|"update"|"delete"), `content` (required for create/update, omitted for delete)
- [ ] Returns: `{ proposal_id: str, file_path: str, operation: str, old_hash: str | null, new_hash: str | null, ttl_seconds: int }`
- [ ] Proposal TTL default is 3600 seconds (1 hour); configurable per project
- [ ] Proposal is validated against write guardrails before storage
- [ ] No disk write occurs during proposal creation
- [ ] Old content hash is captured for update/delete proposals
- [ ] New content hash is captured for create/update proposals
- [ ] Performance: proposal creation completes in under 100ms for typical markdown files (<=256KB) on local disk

### US-5A-002: Store and query proposal metadata
**Description:** As a developer, I need proposal metadata stored durably so proposals can be listed, validated, and approved later.

**Acceptance Criteria:**
- [ ] Proposals are stored in SQLite with fields sufficient for file path, operation, old/new hash, content, created time, expiry time, and status
- [ ] Proposals can be queried by ID, target file, status, and created time
- [ ] Status transitions support at least: pending, applied, rejected, expired

### US-5A-003: Review pending proposals
**Description:** As an operator, I want to list pending proposals with enough preview information to decide what to approve.

**Acceptance Criteria:**
- [ ] `list_proposals` supports filtering by status and file path
- [ ] Results are sorted newest first
- [ ] Results include a content preview for create/update proposals
- [ ] Expired proposals are marked or filtered correctly before results are returned

### US-5A-004: Approve a proposal safely
**Description:** As an operator, I want to approve a pending proposal so it gets applied only if the target file state is still valid.

**Acceptance Criteria:**
- [ ] `approve_proposal` accepts `proposal_id`
- [ ] Approval fails with `ERR_INVALID_REQUEST` when the proposal does not exist
- [ ] Approval fails with `ERR_STALE_PROPOSAL` when the proposal has expired
- [ ] Approval fails with `ERR_STALE_PROPOSAL` when the current file hash no longer matches `old_hash`
- [ ] Approval writes atomically to disk and marks the proposal as applied on success
- [ ] Create operations create parent directories when needed
- [ ] Delete operations fail clearly if the target file no longer exists

### US-5A-005: Provide minimum operator CLI support
**Description:** As an operator, I need the smallest CLI surface that lets me review, approve, and reject proposals safely.

**Acceptance Criteria:**
- [ ] `mcp-memory proposals list` shows at minimum: proposal ID, target file path, operation, status, and age
- [ ] `mcp-memory proposals list` is available in Phase 5A
- [ ] `mcp-memory proposals approve {proposal_id}` is available in Phase 5A
- [ ] `mcp-memory proposals reject {proposal_id}` is available in Phase 5A (marks proposal rejected without applying it)
- [ ] CLI approval requires explicit confirmation before applying the write
- [ ] CLI approval shows a content preview for create/update proposals before requesting confirmation
- [ ] Performance: approval completes in under 200ms including disk write for typical markdown files (<=256KB) on local disk

### US-5A-006: Record proposal lifecycle events
**Description:** As an operator, I need enough lifecycle records to understand what happened to a proposal.

**Acceptance Criteria:**
- [ ] Lifecycle records capture proposal creation, approval attempt, apply success, apply rejection, and expiry
- [ ] Records are sufficient to explain why a proposal changed state or why a file write occurred

## Precondition

Phase 5A should not be built unless a concrete write workflow exists that is not served well enough by manual copy-paste. This is a go/no-go decision before implementation starts, not a runtime check.

## Functional Requirements

- FR-5A-1: `propose_memory_update` creates a non-mutating proposal with a unique ID
- FR-5A-2: Proposal persistence stores enough metadata to validate and apply safely later
- FR-5A-3: `list_proposals` returns pending or filtered proposals with preview metadata
- FR-5A-4: `approve_proposal` verifies file-state safety before applying
- FR-5A-5: Proposal expiry is enforced consistently
- FR-5A-6: Lifecycle records capture enough information for support and debugging
- FR-5A-7: Phase 5A supports only straightforward single-file mutations
- FR-5A-8: Phase 5A CLI supports list, approve, and reject for operator-driven proposal handling

## Non-Goals

- No grouped multi-file logical approvals
- No semantic contradiction resolution in `Memory/`
- No automatic contradiction detection
- No batch approval or batch rejection
- No rejection reason or operator notes (notes are a 5B enrichment)
- No rich audit reporting UI/CLI beyond minimum lifecycle visibility
- No generic merge conflict resolution

## Technical Considerations

- Proposal persistence should remain generic and workflow-agnostic
- File-state conflict detection uses `old_hash` comparison against current disk state
- Disk writes must be atomic
- Lifecycle logging should stay minimal in Phase 5A
- The public contract may remain proposal-oriented while richer grouped-change abstractions are deferred to Phase 5B

## Success Metrics

- [ ] 100% of Phase 5A writes require explicit approval
- [ ] Zero stale proposals are applied after `old_hash` mismatch
- [ ] Proposal creation completes in under 100ms for typical markdown files (<=256KB) on local disk
- [ ] Proposal approval completes in under 200ms including disk write for typical markdown files (<=256KB) on local disk
- [ ] Operators can review and approve a proposal in under 10 seconds
- [ ] Phase 5A replaces at least one real manual write workflow

## Open Questions

- Which write workflow is the first Phase 5A target?
  A: Agent/MCP wants to propose memory update about a project/vault.
- Should delete proposals be part of the first release or added after create/update prove out?
  A: Added after.
- Does the first operator workflow need CLI approval only, or MCP approval as well?
  A: MCP approval. LLM will make a proposal, then ask user if they approve of the it, and finally approve or reject proposal via MCP. Feel free to think about this workflow yourself and decide.

## Dependencies

- Phase 0 complete
- Phase 1 complete
- Phase 2A complete
- Phases 3-4 may already be complete, but are not hard blockers if a write workflow is prioritized independently

## Deliverables

- `src/obsidian_memory_mcp/proposals/` — new sub-package (mirrors the `indexing/` and `retrieval/` pattern):
  - `__init__.py` — public API surface: `ProposalManager` and result types only; internals are not re-exported
  - `_models.py` — `Proposal`, `ProposalStatus`, `ProposalOperation` dataclasses; no IO imports
  - `repository.py` — SQLite CRUD detail: insert, query, update status, expire (mirrors `indexing/repository.py`)
  - `manager.py` — `ProposalManager` orchestration service: create, list, approve, reject, expire (mirrors `indexing/service.py`)
- `src/obsidian_memory_mcp/server.py` — thin tool handlers for `propose_memory_update`, `list_proposals`, `approve_proposal`; import only from `proposals/__init__.py`
- `src/obsidian_memory_mcp/cli.py` — `proposals list`, `proposals approve`, `proposals reject`
- `tests/unit/test_proposals.py` — proposal creation, validation, and expiry
- `tests/integration/test_approval_workflow.py` — hash conflict, atomic write, and rejection tests
- operator documentation for the core proposal workflow