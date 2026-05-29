---
name: context-bootstrap
description: Load a configured obsidian-memory-mcp context pack at session start so the agent has project background before the first user message. Requires MCP server >= v0.2.0 (list_context_packs, get_context_pack, search_notes).
when_to_use: At the start of a new conversation; when the user asks to bootstrap or load context; when topic-specific vault background is needed before the first message.
---

# Context bootstrap

Follow the MCP workflow in **[workflow.md](../../shared/context-bootstrap/workflow.md)**.

Supporting files live under `docs/skills/shared/context-bootstrap/` (template, examples). Copy or symlink this skill directory to `.claude/skills/context-bootstrap/` and keep `shared/` reachable via relative paths, or copy `shared/context-bootstrap/` alongside the skill.

**MCP tools:** `list_context_packs`, `get_context_pack`, `search_notes` (topic variant only).
