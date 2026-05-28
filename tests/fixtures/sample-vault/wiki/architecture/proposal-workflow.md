---
tags: [architecture, proposals, writes]
type: concept
---
# Proposal Workflow Architecture

The proposal workflow is a two-step, conflict-detecting mechanism for applying changes to the vault. Proposals are created with proposed content, stored with metadata, and later approved or rejected. This design enables audit trails, concurrent request handling, and recovery from conflicts.

## Design Rationale

A two-step workflow prevents accidental overwrites and enables offline review of proposed changes. Proposals are immutable — once created, the proposed content cannot be changed. The approval step is a separate transaction that can be performed later or by a different user. This separation of concerns makes the system more reliable and auditable.

## State Machine

Proposals transition through several states: `pending` (awaiting decision), `applied` (successfully written), `rejected` (discarded), and `expired` (automatically removed after retention period). Proposals can only transition from pending to applied or rejected. Applied and rejected proposals are terminal states.

### Pending State

A new proposal enters the pending state when created. It remains pending until explicitly approved, rejected, or automatically expired. Pending proposals do not affect the vault.

### Applied State

A proposal transitions to applied when the approval endpoint is called and the file hash matches the proposal. Once applied, the proposal is immutable and serves as an audit record.

### Rejected State

A proposal transitions to rejected when the rejection endpoint is called. Optionally, a reason and notes are recorded. Rejected proposals remain in the database for audit purposes but cannot be reapplied.

### Expired State

Proposals automatically expire after a configurable retention period (default 24 hours). Expired proposals are not automatically deleted but are marked as expired and not actionable.

## Storage Model

Proposals are stored in a SQLite table with columns for `proposal_id`, `project`, `file_path`, `operation`, `content`, `content_hash`, `created_at`, `expires_at`, `status`, `created_by`, and metadata fields. The content hash enables conflict detection during approval.

## Conflict Detection

Before approving a proposal, the system computes the hash of the on-disk file and compares it with the proposal's content hash. If the hashes differ, the file has been modified since the proposal was created. A CONFLICT error is returned. Clients can then reload the file, create a new proposal with updated content, and retry.

## Audit Trail

Every proposal creation, approval, and rejection is logged with timestamp, user, and optional notes. The audit log enables compliance reviews and investigation of data changes. See [[system-overview]] and [[proposal-lifecycle]] for implementation details.
