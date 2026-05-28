---
tags: [memory-workflow, proposals]
type: concept
---
# Proposal Lifecycle

The proposal lifecycle describes the states a proposal transitions through from creation to finalization. Understanding the lifecycle is essential for building reliable workflows that depend on proposal state.

## States Overview

A proposal progresses through states: `pending` (awaiting review), `applied` (successfully written to disk), `rejected` (discarded), and `expired` (automatically removed). Each state transition is triggered by a user action or automatic timer. The diagram would show: pending → (approved) → applied, pending → (rejected) → rejected, and pending → (timeout) → expired.

### State Transition Diagram

Proposals start in pending. From pending, they can transition to applied (approval endpoint), rejected (rejection endpoint), or expired (24-hour timeout). Applied and rejected are terminal states — no further transitions are possible. Expired proposals remain in the database but cannot be acted upon.

### Terminal States

Applied, rejected, and expired are terminal states. Proposals in these states cannot be approved, rejected, or modified. If you need to apply an expired proposal, create a new proposal with the same content.

## Creating a Proposal

A proposal is created via the [[propose-memory-update]] endpoint. The client provides operation, file path, and content. The server validates the request, checks vault boundaries, and returns a proposal ID. The proposal enters the pending state with an expiry time (typically 24 hours from creation).

## Pending Review

While pending, proposals are visible to reviewers via [[list-proposals]]. The content cannot be changed — if changes are needed, the proposal must be rejected and a new one created. Reviewers can examine the proposed content to decide whether to approve or reject.

## Approval and Application

[[approve-reject-proposal]] applies the approved proposal to disk. Before applying, the system checks whether the file has been modified since the proposal was created (conflict detection). If the file hash matches, the proposal transitions to applied. If not, a CONFLICT error is returned and no changes are made.

## Rejection

Rejection discards a proposal without applying any changes. The proposal transitions to rejected with optional reason and notes for audit documentation. Rejected proposals serve as records of what was considered and why it was not applied.

## Expiry

Proposals automatically expire after a configurable retention period (default 24 hours). Expired proposals cannot be approved or rejected. They remain in the database for compliance purposes. See [[approve-reject-proposal]] and [[proposal-workflow]] for implementation details.
