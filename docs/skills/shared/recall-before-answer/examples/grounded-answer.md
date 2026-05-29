# Example: grounded answer after search

**User question:** What is our context pack token budget default?

**Agent steps (fictional):**

1. Key terms: `context`, `pack`, `token`, `budget`
2. `search_notes(project="sample", query="context pack token budget", limit=5)`
3. Top hit: `file_path` = `wiki/operations/context-pack-budget.md`, `heading` = `Default budget`
4. `read_section(project="sample", note_path="wiki/operations/context-pack-budget.md", heading_name="Default budget")`

---

## Agent answer (sample)

The default context pack token budget is **8000 tokens** unless a pack overrides it with `token_budget` in `memory-mcp.yaml`. With `strict_budget=true`, `get_context_pack` fails with `ERR_CONTEXT_EXCEEDS_BUDGET` when the pack exceeds the cap; with `strict_budget=false`, content is truncated at section boundaries.

Source: `wiki/operations/context-pack-budget.md` (section “Default budget”).

No matching project notes were **not** applicable here — if `returned_count` had been 0, the agent would answer from general MCP documentation and state that no vault note matched.

---

### Footnotes: query and filters

- Phrase query example: `"token budget"` instead of loose `token budget`.
- Narrow to wiki: `search_notes(..., paths=["wiki/**"])`.
- Require tag: `search_notes(..., tags=["operations"])`.
- Exclude drafts: `search_notes(..., exclude_paths=["wiki/drafts/**"])`.
- Heading-biased FTS5: `query="heading : budget"` (column filter syntax).

See [retrieval-guide.md](../../../../retrieval-guide.md) for full filter semantics.
