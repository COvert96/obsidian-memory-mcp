---
name: memory-capture
description: Capture 1–3 conversation insights into Memory/ notes at session end with deduplication, optimistic locking, and supersession via obsidian-memory-mcp >= v0.2.0.
when_to_use: At conversation end; when the user says "Before ending this conversation, capture any new insights"; after sessions with decisions worth persisting.
---

# Memory capture

Follow the MCP workflow in **[workflow.md](../../shared/memory-capture/workflow.md)**.

Supporting files: `docs/skills/shared/memory-capture/` (`template.md`, `examples/`, `scripts/validate-note.py`).

Copy or symlink this directory to `.claude/skills/memory-capture/`.

**MCP tools:** `search_notes`, `read_note`, `write_memory`, `update_memory`.
