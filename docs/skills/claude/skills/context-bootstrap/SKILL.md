---
name: context-bootstrap
description: Load a configured obsidian-memory-mcp context pack at session start so the agent has project background before the first user message. Requires MCP server >= v0.2.0 (list_context_packs, get_context_pack, search_notes).
when_to_use: At the start of a new conversation; when the user asks to bootstrap or load context; when topic-specific vault background is needed before the first message.
---

# Context bootstrap

Follow the MCP workflow in **[workflow.md](./workflow.md)**.

Supporting files: `template.md`, `examples/`.

**MCP tools:** `list_context_packs`, `get_context_pack`, `search_notes` (topic variant only).
