---
name: recall-before-answer
description: Search obsidian-memory-mcp project notes and cite vault paths before answering domain questions. Requires MCP server >= v0.2.0 (search_notes, read_note, read_section).
when_to_use: Before answering questions about project architecture, policies, prior decisions, or vault-specific facts; when a definitive answer should be grounded in Memory/ or wiki notes.
---

# Recall before answer

Follow the MCP workflow in **[workflow.md](../../shared/recall-before-answer/workflow.md)**.

Supporting files: `docs/skills/shared/recall-before-answer/examples/`.

Copy or symlink this directory to `.claude/skills/recall-before-answer/`.

**MCP tools:** `search_notes`, `read_note`, `read_section`.
