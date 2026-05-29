# Structured note template — conventions

Requires **obsidian-memory-mcp >= v0.2.0**. **MCP tools:** none — this skill is a template and convention reference for agents calling `write_memory` or `update_memory`.

> **Living document:** Update [template.md](template.md) when new frontmatter fields are added by `SupersessionService` or other write tools.

## Overview

Consistent `Memory/` note shape improves `search_notes` precision, human readability, and maintenance workflows. Use [template.md](template.md) as a copy-paste-ready example when creating or revising memory files.

## When to Use

- Before **`write_memory`** on a new `Memory/` path.
- When revising notes during [memory-capture](../memory-capture/workflow.md) or [memory-maintenance](../memory-maintenance/workflow.md).
- When the operator asks for vault note structure or frontmatter standards.

## Frontmatter fields

### User-managed (set at creation or edit)

| Field | Format | Purpose |
|-------|--------|---------|
| `date` | ISO 8601 date (`YYYY-MM-DD`) | When the fact or decision was recorded; aids chronological browsing. |
| `tags` | Comma-separated list (e.g. `memory, api, #review`) | **`search_notes(tags=[...])`** filters on these values; include `#stale` or `#review` for [memory-maintenance](../memory-maintenance/workflow.md). |
| `status` | `active` \| `stale` \| `superseded` | Signals lifecycle; `stale` and `#review` / `#stale` tags drive maintenance triage. |
| `last_reviewed` | ISO 8601 date (optional) | Freshness signal for maintenance; set at creation and refresh after review. |
| `superseded_by` | Vault-relative path (optional) | Manual pointer when you know a successor path before server archival (prefer `update_memory` + `supersedes` for automated archival). |
| `supersedes` | List of vault-relative paths (optional) | Manual back-references; normally written by the server on the canonical note after supersession. |

### System-written (do not hand-edit unless correcting an error)

`SupersessionService` stamps these when **`update_memory`** is called with `supersedes`:

| Field | Set on | Purpose |
|-------|--------|---------|
| `superseded` | Archived note | `true` when the note was moved to the archive. |
| `superseded_by` | Archived note | Path of the replacement note. |
| `superseded_at` | Archived note | ISO 8601 timestamp of archival. |
| `supersedes` | Canonical (new) note | List of archive paths for notes this write replaced. |

## Body conventions

- One top-level `#` heading matching the note subject (aligned with filename topic).
- Standard sections (all optional but recommended for consistency):
  - `## Summary` — one or two sentences.
  - `## Details` — decisions, context, links.
  - `## Open Questions` — unresolved items.
  - `## References` — wiki paths, tickets, external links.

## Naming conventions

| Pattern | Example | When to use |
|---------|---------|-------------|
| Topic-based | `Memory/api-auth-decisions.md` | Long-lived facts you may update in place. |
| Date-prefixed | `Memory/2026-05-28-sprint-retro.md` | Time-bounded entries, retros, incidents. |
| Avoid | `Memory/notes.md`, `Memory/misc.md` | Generic names merge unrelated content and degrade search precision. |

Use kebab-case filenames and the `Memory/` prefix. Paths must satisfy server guardrails.

## Archive convention (`memory_archive_path`)

Superseded notes are moved automatically to the configured archive directory (default **`Memory/archive/`**) when you call **`update_memory`** with `supersedes`. **Do not manually move notes into `Memory/archive/`** — the server relocates files, stamps supersession frontmatter, and links the canonical note. Archived notes remain searchable but are marked historical via `superseded: true`.

## Supporting files

- **[template.md](template.md)** — complete example note (valid YAML frontmatter + standard sections).

## See also

- [memory-capture](../memory-capture/workflow.md) — when to persist insights.
- [memory-maintenance](../memory-maintenance/workflow.md) — `#stale`, `#review`, `last_reviewed`.
- [Write tools guide](../../../write-tools-guide.md) — supersession and `write_memory`.
