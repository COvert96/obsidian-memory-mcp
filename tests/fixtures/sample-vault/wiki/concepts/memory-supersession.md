---
tags: [concepts, memory-workflow, proposals]
type: concept
---
# Memory Supersession

Memory supersession is a pattern for replacing an existing note with a new, updated version while archiving the old version. It is useful when notes become outdated or need significant restructuring. Supersession is implemented as a multi-step changeset that atomically archives the old note and creates the new one.

## What is Supersession

Supersession involves creating a new note with updated content, archiving the original note (moving it to an archive directory with a timestamp suffix), and transferring metadata (tags, ownership) from the original to the new note. Unlike a simple update, supersession preserves the old note for historical reference.

## When to Use It

Use supersession when a note has become a historical record or when its structure is fundamentally changing. Examples include: replacing an old API documentation with a new version, consolidating multiple notes into a single authoritative source, or archiving deprecated configurations. For small updates or corrections, prefer direct file updates instead.

## How It Works

Supersession is coordinated as a changeset with three steps: archive (rename original to archive/ with timestamp), create (create the new note with supersession metadata), and finalize (update cross-references if needed).

### Archive Step

The old note is moved to `archive/` with a modified name: `archive/{original_name}~{timestamp}.md`. This preserves the original for audit purposes while removing it from active directories.

### Create Step

The new note is created in its intended location with fresh content. The frontmatter includes a `supersedes` field pointing to the original note, enabling traceability.

### Metadata Propagation

Tags and ownership information from the original note are merged into the new note's frontmatter. This preserves important metadata across supersession. Wikilinks in the new note should reference the appropriate version (old for historical context, new for active links).

## Limitations

Supersession does not automatically update references in other notes — clients must manually update wikilinks. Bulk supersession of many related notes is complex and should be coordinated carefully to avoid orphaned references. See [[changeset-workflow]] and [[direct-write-workflow]] for related patterns.
