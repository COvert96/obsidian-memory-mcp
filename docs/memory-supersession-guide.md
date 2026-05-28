# Memory Supersession Guide

Memory supersession is for semantic contradictions, not file-state conflicts.
Use it when a new `Memory/` note should become the active source of truth while
the prior note remains traceable.

## Workflow

1. Identify the existing `Memory/` note that is being superseded.
2. Create a supersession changeset with the old path, new path, and new content.
3. Review the grouped changeset with `mcp-memory proposals show {changeset_id} --diff`.
4. Approve the changeset with `mcp-memory proposals approve {changeset_id}`.

Approval updates the prior note and creates the new active note together. If any
file hash changed since proposal creation, approval fails with a file-state stale
proposal error and no file in the changeset is left partially applied.

## Frontmatter Conventions

Active memory:

```yaml
status: active
supersedes:
  - Memory/old-note.md
```

Superseded memory:

```yaml
status: superseded
superseded_by: Memory/new-note.md
archived_at: '2026-05-28T09:30:00+00:00'
```

`status` defines whether a note is the current source of truth. `supersedes`
points from the active note to the prior note. `superseded_by` and `archived_at`
preserve the prior note's history and review timeline.

## Boundary

Automatic contradiction detection is not part of this workflow. The caller must
explicitly identify the superseded note. File-state conflicts remain separate:
they are detected through the underlying proposal hashes and reported as stale
proposal errors, not as semantic contradiction errors.
