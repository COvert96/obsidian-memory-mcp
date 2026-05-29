# Example: session context after bootstrap

After `get_context_pack` for project `sample` and pack `default`, the agent merges abbreviated `content` into the system prompt.

## Resulting system context (illustrative)

You are assisting on project **sample**. The following background was loaded from the vault context pack at session start.

## Project background

### Architecture overview

The system uses direct-write MCP tools (v0.2.0). Memory notes live under `Memory/`; wiki content under `wiki/`.

### Write policy

- Create with `write_memory`; update with `read_note` + `update_memory` and `expected_hash`.
- Supersede outdated notes via `update_memory` with `supersedes` (see write-tools guide).

---

**Notes:** Real pack bodies can be much longer. Respect `token_count` and `warnings` from the tool response. If `strict_budget=false` was used, mention truncation to the operator when `warnings` are non-empty.
