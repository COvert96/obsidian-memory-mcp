---
name: context-bootstrap
description: Load a configured obsidian-memory-mcp context pack at session start (>= v0.2.0). Use when starting a new Codex session, bootstrapping project context, or loading topic-specific background before the first message. MCP tools list_context_packs, get_context_pack, search_notes.
---

# Context bootstrap

Follow the MCP workflow in **[workflow.md](../../shared/context-bootstrap/workflow.md)**.

Supporting files live under `docs/skills/shared/context-bootstrap/` (template, examples). Install this skill under `.agents/skills/context-bootstrap/` per [Codex skills](https://developers.openai.com/codex/skills) and preserve relative paths to `shared/`, or vendor `shared/context-bootstrap/` next to the skill.

**MCP tools:** `list_context_packs`, `get_context_pack`, `search_notes` (topic variant only).
