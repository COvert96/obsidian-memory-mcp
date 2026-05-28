---
tags: [operations, proposals, workflow]
type: runbook
owner: platform-team
---
# Proposal Review

This runbook guides operators through reviewing, approving, and rejecting proposals. Proposals represent pending changes to the vault and must be reviewed before applying.

## Listing Pending Proposals

Execute `obsidian-memory list-proposals --status pending` to list all pending proposals. The output shows proposal ID, file path, operation (create/update/delete), and creation time. Use `--limit N` to control page size or `--file-path wiki/**` to filter by path.

## Reviewing Content

For a specific proposal, run `obsidian-memory show-proposal <proposal_id>` to display the full proposed content. For create or update operations, this shows the file content that will be applied. Compare against the current file (if updating) to ensure the changes are correct.

## Approving a Proposal

Execute `obsidian-memory approve-proposal <proposal_id>` to apply the changes to disk. The proposal transitions to `applied` status and the file is written. If the file has been modified since the proposal was created, the approval fails with a `CONFLICT` error — the reviewer must then create a new proposal with updated content.

## Rejecting a Proposal

Execute `obsidian-memory reject-proposal <proposal_id> --reason "reason text"` to discard the proposal. Optionally include `--notes "detailed notes"` for audit documentation. The proposal transitions to `rejected` status and cannot be reapplied.

## Bulk Review Workflow

For reviewing multiple related proposals (e.g., a changeset), list them with filter flags, review each one, then approve or reject them. Use `--changeset <name>` to operate on all proposals in a named changeset at once. See [[list-proposals]] and [[approve-reject-proposal]] for API details.
