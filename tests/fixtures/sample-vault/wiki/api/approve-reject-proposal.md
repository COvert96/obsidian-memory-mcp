---
tags: [api, proposals, write]
type: reference
---
# Approve and Reject Proposal

The approval and rejection endpoints complete the proposal lifecycle. These endpoints are used to make final decisions on pending proposals, either applying changes to disk or discarding them with optional notes.

## Approval Endpoint

The approve endpoint accepts a proposal ID and applies the proposed changes to disk. Before approval, the system verifies the proposal has not expired and that the file hash matches the original proposal. Upon successful approval, the file is written to disk and the proposal status is set to `applied`. The endpoint is idempotent — approving the same proposal twice returns success without modifying the file again.

## Rejection Endpoint

The reject endpoint discards a proposal without applying any changes. It accepts optional `reason` and `notes` fields for audit trail documentation. Rejection is useful when a proposal contains errors or is no longer needed. Rejected proposals cannot be reapproved, but the client can submit a new proposal with corrected content.

## Conflict Detection

Before approval, the system checks whether the file has been modified since the proposal was created. If the on-disk hash differs from the proposal hash, a `CONFLICT` error is returned and the approval is aborted. This prevents silent data loss from concurrent writes. See [[proposal-lifecycle]] for details on conflict resolution strategies.

## Response Fields

Both endpoints return updated proposal state including `proposal_id`, `status`, `modified_at`, `applied_by` (approval only), and `rejected_by` with reason (rejection only). For complex multi-file operations, see [[approve-reject-proposal]] workflow documentation and [[propose-memory-update]].
