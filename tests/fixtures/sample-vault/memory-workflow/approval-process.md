---
tags: [memory-workflow, proposals, operations]
type: guide
---
# Approval Process

The approval process is the formal step where a proposal transitions from pending to applied. This guide covers authorization, pre-approval checks, and handling special cases like conflicts.

## Who Can Approve

By default, any client with write access to the proposal's target directory can approve proposals. More restrictive configurations can require approval by members of a specific group (e.g., platform-team) using role-based access control. Check your vault's authorization policy before approving proposals.

## Pre-Approval Checks

Before approving, the [[proposal-review]] runbook recommends: verifying the proposal content matches intended changes, checking that the target file has not been modified since proposal creation (to detect conflicts), and ensuring the proposal has not expired. Run `obsidian-memory show-proposal` to view content.

## Applying to Disk

The approval endpoint performs the following steps: fetch the proposal metadata, read the current file from disk, compute its hash, compare with the proposal hash, write the proposed content to disk (if hashes match), and update the proposal status to applied. All steps occur in a single transaction to ensure consistency.

## Hash Conflict Handling

If the on-disk file hash differs from the proposal hash, a CONFLICT error is returned and nothing is written. The approver must create a new proposal with updated content that reflects the current state of the file. Conflicts are expected in concurrent environments and are not errors — they are a normal part of the conflict detection mechanism.

## Post-Approval Actions

After approval, the proposal becomes read-only and serves as an audit record. The indexing service is notified of the change and updates the search index. If the change affects cross-references, dependent notes should be updated. See [[proposal-lifecycle]], [[proposal-review]], and [[approval-process]] for more information.
