# Memory maintenance — workflow

Requires **obsidian-memory-mcp >= v0.2.0**. MCP tools: `search_notes`, `read_note`, `update_memory`.

## Overview

Memory notes drift as products and decisions change. This workflow periodically surfaces notes tagged for review, reads each candidate in full, and applies a consistent decision tree: refresh metadata, revise in place, supersede into the archive, or defer removal until a future server release. The server does not auto-detect staleness — the agent judges content and drives updates.

## When to Use

Run periodically, for example:

- At the start of a new project phase.
- After a significant product or architecture change.
- On a weekly cadence when the vault is actively written.

Also run when the operator asks to review stale memory, clear `#review` queues, or refresh `last_reviewed` hygiene.

## Tool Call Sequence

Substitute `{project}` with the configured MCP project name.

1. **`search_notes`** — `project="{project}"`, `tags=["#stale"]`, `limit=20`.
   - Collect `results[].file_path` for explicitly tagged stale notes.

2. **`search_notes`** — `project="{project}"`, `tags=["#review"]`, `limit=20`.
   - Collect paths for notes marked for human or agent review.
   - De-duplicate paths that appear in both result sets before step 3.

3. For each unique `file_path` from steps 1–2:
   - **`read_note`** — `project="{project}"`, `note_path=<file_path>`.
   - Inspect body and YAML frontmatter (`status`, `last_reviewed`, `tags`).
   - Apply the decision tree below using **`update_memory`** (always pass `expected_hash` from `read_note` when overwriting content).

### Decision tree (per note)

| Outcome | Action |
|---------|--------|
| **Still accurate** | **`update_memory`** — remove `#stale` and `#review` from `tags` (or set `status: active`), set `last_reviewed` to today (ISO 8601 date), keep body unchanged unless minor typo fixes are needed. Use `expected_hash` from the latest `read_note`. |
| **Outdated but salvageable** | **`update_memory`** — rewrite body with corrected facts; update `last_reviewed`; clear `#stale` / `#review`; set `status: active`. Use `expected_hash`. |
| **Contradicted by newer information** | Ensure the canonical replacement note exists (create with `write_memory` if needed), then **`update_memory`** on that canonical `Memory/` path with `supersedes: [<stale note path>]` so `SupersessionService` archives the old note under `memory_archive_path` (default `Memory/archive/`). See [write-tools-guide.md](../../../write-tools-guide.md). |
| **No longer relevant** | Record the `file_path` in your session summary for the operator. **Deletion is deferred to v0.3.0** — there is no delete tool in v0.2.0. Interim workaround: set `status: stale` in frontmatter, add `#stale`, and optionally supersede if a replacement note exists; otherwise leave the note in place until deletion ships. |

On **`ERR_HASH_MISMATCH`**: `read_note` again, refresh `expected_hash`, retry `update_memory`.

### Deletion limitation (v0.2.0)

The MCP server cannot delete memory files in this release. Do not attempt to remove notes manually from the vault filesystem. When content is obsolete and no replacement is warranted, mark `status: stale`, add `#stale`, and document the path for a future delete pass (v0.3.0). When a replacement note exists, prefer **`update_memory`** with `supersedes` so the stale note moves to `Memory/archive/` with system supersession frontmatter.

## Proactive hygiene at note creation

When capturing new memory (see [memory-capture](../memory-capture/workflow.md)):

- Set **`last_reviewed`** to the creation date (ISO 8601) so maintenance can judge freshness later.
- Add **`#review`** when the note needs a future pass (e.g. time-bounded decisions).
- Add **`#stale`** only when you already know content is suspect; otherwise use `status: active` and let maintenance add tags during review.

Follow [structured-note-template](../structured-note-template/workflow.md) for full frontmatter and heading conventions.

## Supporting files

- Provider entrypoints: [claude/memory-maintenance/](../../claude/memory-maintenance/), [openai/memory-maintenance/](../../openai/memory-maintenance/).
- [structured-note-template](../structured-note-template/) — field reference for `status`, `tags`, and `last_reviewed`.

## See also

- [Write tools guide](../../../write-tools-guide.md) — `update_memory`, `supersedes`, archive behavior.
- [Tool reference](../../../tool-reference.md) — `search_notes`, `read_note`, `update_memory`.
- [structured-note-template](../structured-note-template/) — well-formed `Memory/` notes.
