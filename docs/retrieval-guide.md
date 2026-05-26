# Retrieval Guide

Phase 3 exposes three FastMCP tools for reading and searching configured
Obsidian vaults. Every tool resolves `project` through the server registry,
loads that project's vault config, and applies read guardrails before returning
vault content.

## read_note

Use `read_note` when the client needs the complete markdown file exactly as it
exists on disk.

Example request:

```json
{
  "project": "sample",
  "note_path": "wiki/concepts/compliance-as-code.md"
}
```

Example response:

```json
{
  "project": "sample",
  "file_path": "wiki/concepts/compliance-as-code.md",
  "content": "---\ntype: concept\n---\n# Compliance as Code\n...",
  "frontmatter": {"type": "concept"},
  "file_size_bytes": 412
}
```

`ERR_MISSING_FILE` is returned when the guarded vault-relative path does not
exist. `ERR_GUARDRAIL_VIOLATION` is returned when the path escapes the vault or
does not satisfy the configured read policy.

## read_section

Use `read_section` when the client needs one heading and its nested content.
Heading matching is case-insensitive.

Example request:

```json
{
  "project": "sample",
  "note_path": "wiki/concepts/compliance-as-code.md",
  "heading_name": "definition"
}
```

Example response:

```json
{
  "project": "sample",
  "file_path": "wiki/concepts/compliance-as-code.md",
  "heading": "Definition",
  "heading_level": 2,
  "content": "## Definition\nCompliance controls encoded as executable rules.",
  "context_prefix": "Compliance overview."
}
```

`content` always starts with the matched heading line and continues until the
next heading at the same or higher level. Lower-level headings remain part of
the returned section. `context_prefix` contains up to three non-heading source
lines immediately above the matched heading and is never included in `content`.

## search_notes

Use `search_notes` when the client needs ranked full-text retrieval from the
SQLite FTS5 index created by Phase 2.

Example request:

```json
{
  "project": "sample",
  "query": "continuous compliance",
  "limit": 5,
  "tags": ["compliance"],
  "paths": ["wiki/concepts/**"],
  "exclude_paths": ["wiki/private/**"]
}
```

Example response:

```json
{
  "project": "sample",
  "query": "continuous compliance",
  "results": [
    {
      "file_path": "wiki/concepts/continuous-compliance.md",
      "heading": "Definition",
      "heading_level": 2,
      "preview": "...continuous compliance keeps evidence current...",
      "rank": -1.25,
      "tags": ["compliance"]
    }
  ],
  "returned_count": 1
}
```

The query string is passed to FTS5 `MATCH`, so phrase queries such as
`"exact phrase"` and FTS5 boolean operators such as `AND`, `OR`, and `NOT` are
available. Empty queries return `ERR_INVALID_REQUEST` with message
`query is required`. `limit` defaults to 10 and is capped at 100 results per
call.

## Ranking

Search uses SQLite FTS5 BM25 at the SQL level:

```sql
bm25(blocks_fts, 0, 0, 1.0, 10.0, 1.0, 1.0)
```

The FTS column order is:

1. `block_key` (UNINDEXED, weight `0`)
2. `vault_path` (UNINDEXED, weight `0`)
3. `section_path` (weight `1.0`)
4. `heading` (weight `10.0`)
5. `content` (weight `1.0`)
6. `tags` (weight `1.0`)

The heading column receives a 10x weight so title-level matches rank above
ordinary body matches. Phase 3 does not perform any post-query score adjustment.
SQLite FTS5 returns lower BM25 values for more relevant rows, and ties are
ordered by `block_key ASC` for deterministic results.

## Filters

`tags` uses AND semantics: every requested tag must be present on a result
block. Matching is case-insensitive, and leading `#` is stripped from inputs.
Blocks with no tags are omitted when a tag filter is active.

`paths` is a list of include globs matched against indexed vault paths. A result
must match at least one include glob when the list is provided.

`exclude_paths` is a list of exclude globs. Exclusions are applied after include
filtering and remove any matching vault path. Tags, includes, and excludes are
combined with AND semantics.

Glob matching is path-aware: `*` and `?` stay within one path segment, `**`
matches across directory boundaries, and `**/` matches zero or more directories.
For example, `wiki/**/test.md` matches both `wiki/test.md` and
`wiki/sub/test.md`, but not `wiki/badtest.md`.

## Section Context

`read_section` returns `context_prefix` as source context, not parsed markdown
structure. If a fenced code block appears immediately above a heading, those
fence lines may be returned as context lines because they are part of the source
near the matched heading.

## Regex Queries

Regex search is enabled by wrapping the query in forward slashes:

```json
{
  "project": "sample",
  "query": "/compliance\\s+evidence/",
  "limit": 10
}
```

The service extracts literal terms from the regex and uses them to retrieve FTS5
candidates first. It then applies Python `re.search` to each candidate block's
content and returns only matching rows. Regex is a post-FTS filter, not a native
SQLite regex feature.
