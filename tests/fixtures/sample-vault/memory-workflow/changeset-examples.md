---
tags: [memory-workflow, changesets, examples]
type: guide
---
# Changeset Examples

This guide provides concrete examples of changesets for common multi-file operations. It shows how to coordinate proposals into a changeset and apply them atomically.

## Single-File Changeset

A changeset with a single proposal is useful for coordinating with other pending changes: create a proposal for `Memory/config-v2.md`, group it into a changeset named `config-update`, and approve all proposals in the changeset together. Even with one proposal, this ensures the operation succeeds or fails as a unit.

## Multi-File Rename

Renaming multiple related files requires coordinating several delete/create operations. Example: renaming notes from `wiki/old-api/*` to `wiki/new-api/*` involves deleting the old files and creating the new ones. Create separate proposals for each file, then group them into a changeset named `rename-api-docs`. Approval applies all renames atomically.

### Step 1 - Create Proposals

Create individual proposals for each file: one delete proposal for each old file, one create proposal for each new file. This generates multiple proposal IDs.

### Step 2 - Group Into Changeset

Submit a changeset request with the changeset name and array of proposal IDs. The server validates compatibility (no file conflicts) and creates the changeset.

### Step 3 - Approve

Approve the changeset by passing the changeset name to the approval endpoint. All proposals transition to applied together or none apply (rollback on error).

## Archive and Replace Pattern

When archiving a note and creating a replacement, use a changeset with two proposals: archive the old note (delete with archive/ path), create the new note with updated content. This ensures consistency — the old note is removed and the new one is added in a single atomic operation.

## Supersession Via Changeset

[[memory-supersession]] can be implemented as a changeset that archives the original note, creates the superseding note, and updates cross-references in a single atomic operation. This prevents intermediate states where references are stale. See [[changeset-workflow]] and [[memory-supersession]] for more details.
