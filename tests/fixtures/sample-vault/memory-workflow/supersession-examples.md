---
tags: [memory-workflow, memory-supersession, examples]
type: guide
---
# Supersession Examples

This guide provides examples of [[memory-supersession]] in practice, showing how to archive old notes and replace them with new versions.

## Basic Supersession

To supersede `Memory/old-note.md` with `Memory/new-note.md`: Create a proposal to delete `Memory/old-note.md` with operation set to archive (target path becomes `Memory/archive/old-note~2026-05-28.md`). Create a proposal to create `Memory/new-note.md` with content that includes `supersedes: old-note.md` in the frontmatter. Group these into a changeset and approve together.

## Supersession with Tag Merge

If the old note has tags that should be preserved in the new note, extract them from the old frontmatter and include them in the new note's frontmatter. Example: old note has `tags: [api, v1, deprecated]`; the new note should have `tags: [api, v2, active]`. The changeset ensures both notes are updated consistently.

## Bulk Supersession

Superseding multiple related notes (e.g., all API v1 documentation) requires creating multiple archive + create proposal pairs and grouping them into a single changeset. This ensures all old notes are removed and new ones are created together. If any proposal fails, the entire bulk operation rolls back.

## Pitfalls

### Common Mistakes

Forgetting to update wikilinks after supersession leaves dangling references to archived notes. After supersession, scan the vault for references to the old note name and update them manually. Another mistake is archiving without creating a replacement, leaving references orphaned. Always create a replacement or update references before archiving. See [[memory-supersession]] and [[changeset-examples]] for correct patterns.

#### Orphaned Archive Notes

If an archive note is created without updating references, it becomes orphaned — referenced only by history, not by active notes. To prevent this, verify all cross-references have been updated before approving a supersession changeset. Tools can help detect orphaned notes by finding notes with no incoming references.
