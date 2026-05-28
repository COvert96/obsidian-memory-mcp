---
tags: [concepts, changesets, proposals]
type: concept
---
# Changeset Workflow

A changeset is a named collection of related proposals that are approved or rejected together as a single unit. Changesets enable atomic multi-file operations, ensuring consistency across interdependent changes. If any proposal in a changeset fails to apply, the entire changeset is marked as failed.

## Overview

Clients create multiple proposals independently, then group them into a named changeset. The changeset server stores the association and enforces that all proposals in the changeset are applied together. This is useful for complex operations like bulk renaming or coordinated schema migrations.

## Creating a Changeset

A changeset is created by submitting a request with a changeset name, optional description, and an array of proposal IDs. The server validates that all proposals exist, are in pending state, and have compatible file paths (no conflicts). If validation passes, the changeset is created and each proposal is marked as belonging to the changeset.

## Atomic Approval

When a changeset approval request is received, all proposals in the changeset are approved in a single transaction. If any proposal approval fails (e.g., due to a conflict), the entire transaction is rolled back. All proposals either apply together or none apply. This ensures the vault remains in a consistent state.

## Rollback Behavior

If a changeset approval fails partway through, the system rolls back all successful approvals in that batch. This is accomplished using SQLite transactions. Rolled-back proposals remain in pending state and can be reapproved or modified.

## Use Cases

Common use cases include: renaming multiple related files, bulk updating metadata across several notes, performing coordinated schema migrations, and archiving multiple notes while creating replacements. See [[memory-supersession]] and [[proposal-lifecycle]] for examples.
