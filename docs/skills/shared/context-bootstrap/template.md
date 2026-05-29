# System prompt scaffold (context-bootstrap)

Replace `{project}` with your MCP project name. Paste pack `content` from `get_context_pack` into the slot below.

---

You are assisting on project **{project}**. The following background was loaded from the vault context pack at session start. Treat it as authoritative project context unless the user contradicts it.

## Project background

<!-- INJECT get_context_pack response "content" HERE -->
