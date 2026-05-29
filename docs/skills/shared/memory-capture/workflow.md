# Memory capture — workflow

Requires **obsidian-memory-mcp >= v0.2.0**. MCP tools: `search_notes`, `read_note`, `write_memory`, `update_memory`.

## Overview

Project memory grows when agents persist durable insights from conversations. This workflow identifies a
small set of worth-keeping facts, checks for existing related notes, then creates or updates
`Memory/` files using direct-write tools. Contradictions are resolved by superseding outdated notes
into the archive.

## When to Use

- The conversation is ending and the operator wants vault memory updated without manual note-taking.
- The user explicitly asks to save what was learned (see trigger phrase below).
- After a design or debugging session where decisions should survive the chat.

**Example trigger phrase:** “Before ending this conversation, capture any new insights.”

## Tool Call Sequence

Substitute `{project}` with the configured MCP project name.

1. **Agent behavior (not an MCP call):** At conversation end (or on explicit trigger), identify **1–3 insights** worth persisting. Draft each using [template.md](template.md).

2. For each insight, **`search_notes`** — `project="{project}"`, `query=<key terms from the insight>`, `limit=5`.
   - Review `results[].file_path` and previews for an existing related `Memory/` or wiki note.

3. **No related note found** → **`write_memory`** — `project="{project}"`, `file_path=<Memory/... path>`, `content=<filled template>`.
   - `file_path` must start with `Memory/` and must not already exist (`ERR_FILE_EXISTS` otherwise).

4. **Related note found** → **`read_note`** — `project="{project}", note_path=<file_path from search>`.
   - Decide: skip (already covered), or update in place.
   - To update: **`update_memory`** — `project="{project}"`, `file_path=<same Memory/ path>`, `content=<revised body>`, `expected_hash=<content_hash from read_note>`.
   - On **`ERR_HASH_MISMATCH`**: call `read_note` again, refresh `expected_hash`, and retry `update_memory`.

5. **Contradiction** (new insight replaces older notes) → use **`update_memory`** on the **canonical** `Memory/` path with `supersedes` listing vault-relative paths of outdated notes (see [write-tools-guide.md](../../../write-tools-guide.md)).
   - `supersedes` is only accepted on `update_memory`, and the target `file_path` must already exist.
   - **Two-step pattern when the canonical note is new:** (a) `write_memory` to create the canonical file; (b) `update_memory` on the **same** `file_path` with revised content and `supersedes: [<outdated paths>]`.

### Read-before-write (`expected_hash`)

Always capture optimistic-lock safety when updating:

1. `read_note` → save `content_hash`.
2. `update_memory` with `expected_hash` set to that hash.
3. On `ERR_HASH_MISMATCH`, re-read and retry.

### Choosing `Memory/` paths

| Convention | Example | When to use |
|------------|---------|-------------|
| Date-based | `Memory/2026-05-29-api-timeout-fix.md` | Time-stamped decisions, incident notes |
| Topic-based | `Memory/auth-token-refresh-policy.md` | Long-lived facts you may update in place |
| Hybrid | `Memory/2026-05/onboarding-checklist.md` | Monthly roll-ups |

Use kebab-case filenames, `.md` extension, and stay under `Memory/`. Prefer topic-based paths when you expect `update_memory`; use date-based paths for append-only event logs.

## Supporting files

- **[template.md](template.md)** — `Memory/` note scaffold (YAML frontmatter + `## Summary` / `## Details`).
- **[examples/captured-note.md](examples/captured-note.md)** — Complete example after a fictional capture.
- **[scripts/validate-note.py](scripts/validate-note.py)** — Local frontmatter check (no MCP). Run from the **repository root**:

  ```powershell
  uv run python docs/skills/shared/memory-capture/scripts/validate-note.py <path-to-note.md>
  ```

  | Exit code | Meaning |
  |-----------|---------|
  | 0 | File exists and YAML frontmatter parses |
  | 1 | File missing, unreadable, or frontmatter parse error |
  | 2 | Usage error (wrong argument count) |

## See also

- [Write tools guide](../../../write-tools-guide.md) — supersession, `expected_hash`, audit log.
- [Tool reference](../../../tool-reference.md) — `write_memory`, `update_memory`, `read_note`.
- Phase **9b** will add `structured-note-template` for full frontmatter field reference (not yet in this library).
