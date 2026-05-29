# Recall before answer — workflow

Requires **obsidian-memory-mcp >= v0.2.0**. MCP tools: `search_notes`, `read_note`, `read_section`.

## Overview

Training data alone cannot know your vault. This workflow extracts query terms, searches the indexed
notes, reads the best matches, and grounds answers in retrieved content with vault-relative
citations. When nothing matches, the agent answers from general knowledge and states that no project
notes were found.

## When to Use

- The user asks about architecture, policies, past decisions, or anything that should live in the vault.
- You are about to give a definitive project-specific answer without having searched memory yet.
- A question references names, features, or paths that likely appear in indexed markdown.

## Tool Call Sequence

Substitute `{project}` with the configured MCP project name.

1. **Agent behavior (not an MCP call):** Extract **2–4 key terms** from the user's question (nouns, product names, error codes, feature names). Avoid stop words.

2. **`search_notes`** — `project="{project}"`, `query=<key terms>`, `limit=5`.
   - Optionally narrow with request parameters (not embedded in the query string):
     - `tags` — AND semantics; every tag must be present (see [retrieval-guide.md](../../../retrieval-guide.md)).
     - `paths` — include globs (e.g. `["wiki/**"]`, `["Memory/**"]`).
     - `exclude_paths` — exclude globs applied after includes.

3. If **`returned_count` > 0**:
   - For the top **1–2** results, call **`read_note`** — `project="{project}", note_path=<file_path>` when you need the full file.
   - Or call **`read_section`** — `project="{project}", note_path=<file_path>, heading_name=<heading>` when only one section is relevant (use `heading` from the search hit when helpful).

4. **Agent behavior (not an MCP call):** Incorporate retrieved content into the answer. **Cite** the vault-relative `file_path` from the search or read response (e.g. “According to `wiki/concepts/compliance-as-code.md` …”). See [examples/grounded-answer.md](examples/grounded-answer.md).

5. If **`returned_count` is 0**: answer from training data and **explicitly state** that no matching project notes were found.

### FTS5 query syntax (cheat sheet)

The `query` string is passed to SQLite FTS5 `MATCH`:

| Pattern | Example |
|---------|---------|
| Phrase | `"exact phrase"` |
| Boolean AND / OR / NOT | `compliance AND evidence`, `api OR gateway`, `legacy NOT deprecated` |
| Column-biased (heading) | `heading : budget` — prefer matches in the indexed heading column |
| Regex (post-FTS filter) | `/compliance\s+evidence/` — wrap in forward slashes per [retrieval-guide.md](../../../retrieval-guide.md) |

Use `tags`, `paths`, and `exclude_paths` on the **`search_notes` request** for path/tag filtering — do not embed path globs in the query string.

## Supporting files

- **[examples/grounded-answer.md](examples/grounded-answer.md)** — Sample answer citing `file_path` after a fictional `search_notes` hit.

## See also

- [Retrieval guide](../../../retrieval-guide.md) — ranking, filters, regex queries.
- [Tool reference](../../../tool-reference.md) — `search_notes`, `read_note`, `read_section`.
- [Context bootstrap](../context-bootstrap/workflow.md) — load standing context at session start.
