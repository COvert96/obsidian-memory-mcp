---
tags: [memory-workflow, compliance, audit]
type: concept
owner: security-team
---
# Audit Trail

The audit trail is a permanent record of all changes to the vault, including proposal creation, approval, rejection, and content modifications. It is essential for compliance, investigation, and understanding the history of vault state.

## What is Logged

Every proposal operation generates an audit event: creation (who, when, file, operation), approval (who, when, approval timestamp), rejection (who, when, reason), and expiry (automatic). Content modifications are logged at the proposal level, enabling reconstruction of previous states. For compliance, user authentication is required for all audit-logged operations.

## Audit Event Schema

Each event includes: `event_id` (unique identifier), `timestamp`, `event_type` (create/approve/reject), `user_id`, `proposal_id`, `file_path`, and `details` (operation-specific metadata). Events are immutable — once created, they cannot be modified or deleted.

## Querying the Audit Log

Run `obsidian-memory audit-log --start 2026-01-01 --end 2026-12-31 --user chris` to query events by date and user. Results can be filtered by `event_type` (create, approve, reject), `file_path` (glob patterns supported), and `status` (pending, applied, rejected). Results are paginated and can be exported to CSV or JSON.

## Retention Policy

Audit events are retained indefinitely unless a retention policy is configured in the vault config. Default retention is permanent. To enable automatic pruning, set `audit_retention_days` in the config. Events older than the specified period are deleted automatically.

## Compliance Use Cases

The audit trail enables: demonstrating compliance with change control policies, investigating unauthorized modifications, reconstructing the history of a note's evolution, and proving who approved what changes. Organizations can export audit logs to their compliance system for external audits. See [[compliance-as-code]] and [[proposal-lifecycle]] for more details.
