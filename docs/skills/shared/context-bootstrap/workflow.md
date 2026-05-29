# Context bootstrap — workflow

Requires **obsidian-memory-mcp >= v0.2.0**. MCP tools: `list_context_packs`, `get_context_pack`, `search_notes` (topic variant only).

## Overview

Context packs bundle vault markdown into a single payload for agent background. This workflow lists
configured packs, loads the chosen pack within its token budget, and injects the result into the
session system prompt so answers start from project knowledge instead of an empty slate.

## When to Use

- A new chat or agent session begins and the operator wants standing project context loaded automatically.
- The user asks to “bootstrap” or “load context” before work begins.
- You need topic-specific background: use the **Load by topic** variant below when the session focus is already known.

## Tool Call Sequence

Substitute `{project}` with the configured MCP project name (from `memory-mcp.yaml` / server registry).

### Default: load configured pack

1. **`list_context_packs`** — `project="{project}"`.
   - If `returned_count` is **0**: stop and tell the operator no context packs are configured in `memory-mcp.yaml`.
   - If **1**: use that entry's `pack_name`.
   - If **more than one**: present each `pack_name` (and `description` when returned) to the operator; use the chosen `pack_name`.

2. **`get_context_pack`** — `project="{project}"`, `pack_name=<chosen>`, `strict_budget=true`.
   - On success, note `content`, `token_count`, `files_included`, and any `warnings`.

3. **Agent behavior (not an MCP call):** Treat the response `content` as session background. Merge it into [template.md](template.md) (system-prompt slot) before the user's first message. See [examples/session-bootstrap.md](examples/session-bootstrap.md) for the expected shape.

4. If the call fails with **`ERR_CONTEXT_EXCEEDS_BUDGET`**, retry the same `pack_name` with `strict_budget=false`. The server truncates at section boundaries (see [context-packs-guide.md](../../../context-packs-guide.md)).

### Variant: load by topic

Use when the session topic is known before pack selection (e.g. “work on the API docs today”).

1. **`search_notes`** — `project="{project}"`, `query=<topic key terms>`, `limit=5`.
2. From `results`, identify tags (`tags`) and `file_path` values that best match the topic.
3. Call **`list_context_packs`** — `project="{project}"`. For each pack in `context_packs`, compare `path_patterns` (and `tags_filter` when present) to the search hits. Pick the pack whose sources overlap the strongest matches.
4. Continue with **`get_context_pack`** steps 2–4 from the default flow using the selected `pack_name`.

## Supporting files

- **[template.md](template.md)** — System-prompt scaffold with `{project}` and a slot for injected pack `content`.
- **[examples/session-bootstrap.md](examples/session-bootstrap.md)** — Sample showing how pack content appears in session context.

## See also

- [Context packs guide](../../../context-packs-guide.md) — pack YAML, budgets, truncation.
- [Tool reference](../../../tool-reference.md) — `list_context_packs`, `get_context_pack`.
- [Recall before answer](../recall-before-answer/workflow.md) — search memory before answering.
