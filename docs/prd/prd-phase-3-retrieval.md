# PRD: Phase 3 - Retrieval Tools (Read and Search)

## Introduction

Implement the core retrieval capabilities: `read_note` (get entire file), `read_section` (get specific section), and `search_notes` (full-text search with filtering). These are MCP tools that return vault content with proper metadata and rankings.

## Architecture Alignment Update (2026-05-23)

- Tool entrypoints must be implemented as **FastMCP handlers** (thin adapters) in `server.py` or mounted handler modules.
- Runtime request validation is derived from FastMCP/Pydantic type hints, not JSON-schema decorators.
- All retrieval tools must resolve `project` via the shared server registry (`project -> vault_root`) introduced in Phase 2A.

## Goals

- Implement `read_note` tool to return complete markdown files
- Implement `read_section` tool to return specific sections by heading name
- Implement `search_notes` tool with FTS, optional filtering by tags/paths
- Return results with metadata (headings, source paths, snippet previews)
- Ensure search results are ranked and relevant

## User Stories

### US-001: Implement read_note MCP tool
**Description:** As a tool user, I want to read an entire markdown file from the vault so I can see full context.

**Acceptance Criteria:**
- [x] Tool parameter: `note_path` (path relative to vault root)
- [x] Validates path against guardrails (Phase 1) before reading
- [x] Returns: `{ content: str, frontmatter: dict, file_path: str, file_size_bytes: int }`
- [x] Content is exact markdown from disk (no parsing or modification)
- [x] Returns error `ERR_MISSING_FILE` if file doesn't exist
- [x] Returns error `ERR_GUARDRAIL_VIOLATION` if path outside vault or not readable
- [x] Performance: return file in <50ms (even for 100KB files)
- [x] Handles special characters in filenames correctly

### US-002: Implement read_section MCP tool
**Description:** As a tool user, I want to read just one section of a markdown file so I don't need the entire file.

**Acceptance Criteria:**
- [x] Tool parameters: `note_path`, `heading_name` (e.g., "Installation", "API Reference")
- [x] Returns section content between heading and next heading of same/higher level
- [x] Returns error `ERR_MISSING_FILE` if note doesn't exist
- [x] Returns error `ERR_SECTION_NOT_FOUND` if heading not found in file
- [x] Response shape: `{ heading: str, heading_level: int, content: str, context_prefix: str, file_path: str }`
  - `content`: the heading line (e.g. `## Installation`) as the first line, followed by the section body up to the next same-or-higher-level heading
  - `context_prefix`: up to 3 non-heading lines immediately above the heading line in the source file; empty string if the heading is at the start of the file or is preceded only by frontmatter
- [x] Heading line is always the first line of `content`; `context_prefix` is never included in `content`
- [x] Case-insensitive heading matching (accept "installation" for "## Installation")
- [x] Performance: <50ms for any file/section combination

### US-003: Implement search_notes MCP tool with FTS
**Description:** As a tool user, I want to search the vault for notes matching keywords so I can find relevant content.

**Acceptance Criteria:**
- [x] Tool parameters: `query` (required), `limit` (optional, default 10), `tags` (optional list), `paths` (optional list of include globs), `exclude_paths` (optional list of exclude globs)
- [x] Uses SQLite FTS5 index from Phase 2 for fulltext search
- [x] Returns top-k results ranked by relevance
- [x] Each result includes: `{ file_path: str, heading: str, heading_level: int, preview: str, rank: float, tags: [str] }`
- [x] Preview shows search term in context (snippet 100-200 characters with "..." around match)
- [x] Optional tag filter: `tags` is a list of tag strings; only return blocks whose tag set contains **all** listed tags (AND semantics); comparison is case-insensitive with any leading `#` stripped from inputs
- [x] Optional path filter: `paths` is a list of include globs (e.g., `["wiki/**", "api/**"]`); only return blocks from files matching at least one glob
- [x] Optional path exclusion: `exclude_paths` is a list of exclude globs; blocks from files matching any exclude glob are removed after include filtering
- [x] Empty query returns error with message "query is required"
- [x] Handles multi-word queries: "complex query" searches all terms
- [x] Regex query: if `query` contains a regex pattern (detected by caller wrapping in `/…/`), FTS5 first retrieves candidates using the raw terms, then Python filters the result set using `re.search`; only the filtered subset is returned
- [x] Performance: <100ms for typical queries on 5000-file vault

### US-004: Handle search ranking and relevance
**Description:** As a tool user, I want results ranked by relevance so I find the most important matches first.

**Acceptance Criteria:**
- [x] Relevance ranking uses FTS5 column-weighted BM25: `bm25(blocks_fts, 0, 0, 1.0, 10.0, 1.0, 1.0)` — column order is `block_key` (UNINDEXED, 0), `vault_path` (UNINDEXED, 0), `section_path` (1.0), `heading` (10.0), `content` (1.0), `tags` (1.0)
- [x] The 10× heading weight is applied at the SQL level; no post-processing score adjustment is performed in Phase 3
- [x] Heading-level distinction (H1 vs H2) is **not** in scope for Phase 3; `heading_level` is returned in results via a JOIN to `sections` (for client-side use) but does not influence the BM25 score
- [x] FTS5 native ranking implemented and documented in `docs/retrieval-guide.md`
- [x] Benchmark: on query "compliance", top 3 results contain relevant compliance content (verified by unit test with fixture vault)
- [x] No irrelevant results in top 5 for common queries
- [x] Ranking is deterministic (same query always produces same order); `block_key ASC` is used as the tiebreaker

### US-005: Implement search filters and result formatting
**Description:** As a tool user, I want to filter search by tags and paths so I can scope results.

**Acceptance Criteria:**
- [x] Tag filter: `tags: ["urgent", "api"]` returns only blocks whose tag set contains **both** `urgent` and `api` (AND semantics); matching is case-insensitive and leading `#` is stripped from each input tag before comparison
- [x] Path include filter: `paths: ["wiki/api/**"]` returns only files whose `vault_path` matches at least one of the provided globs
- [x] Path exclude filter: `exclude_paths: ["wiki/private/**"]` removes files matching any exclude glob after include filtering; applied independently of `paths`
- [x] Multiple filter types (tags, paths, exclude_paths) are AND'ed: a result must pass all active filters
- [x] Results include `heading_level` (obtained by joining `sections` on `section_key`) so the client can sort/format appropriately
- [x] Search result snippets show match context with surrounding words (not just isolated term)
- [x] Handles filters on blocks with no tags gracefully: an active `tags` filter returns no results for tag-free blocks (not an error)

### US-006: Create integration tests for retrieval tools
**Description:** As a developer, I need end-to-end tests so I can verify tools work on realistic vault content.

**Acceptance Criteria:**
- [x] Fixture vault created with diverse content: multiple files, heading levels, tags, special characters
- [x] Test `read_note` on each fixture file
- [x] Test `read_section` on each heading in fixture vault
- [x] Test `search_notes` with 15+ queries covering: single term, multi-term, common phrases, edge cases
- [x] Tests verify result accuracy and latency (<100ms per search)
- [x] Tests verify error handling (missing files, bad paths, etc.)

## Functional Requirements

- FR-1: `read_note` MCP tool returns complete file with frontmatter and content
- FR-2: `read_section` MCP tool returns specific heading/section with context
- FR-3: `search_notes` MCP tool performs FTS queries with optional filtering
- FR-4: All tools validate paths against vault guardrails before access
- FR-5: Search ranking uses FTS5 column-weighted BM25 with `heading` column at 10× weight; `block_key ASC` is the deterministic tiebreaker; heading-level (H1 vs H2) distinction is deferred to a future phase
- FR-6: Results include metadata: file path, heading level, tags, preview
- FR-7: All tools return appropriate error codes from Phase 0 on failure
- FR-8: Performance: read tools <50ms, search <100ms on typical vaults

## Non-Goals

- No semantic/embedding-based search (FTS only for MVP)
- No caching of search results (each request re-queries index)
- No support for searching file content outside indexed sections
- No autocomplete or query suggestions
- No result pagination (client uses limit parameter)

## Technical Considerations

- **Path Validation:** Use Phase 1 guardrail evaluator to check all file access
- **FTS5 Ranking:** Use `bm25(blocks_fts, 0, 0, 1.0, 10.0, 1.0, 1.0)` — zero weights for UNINDEXED columns (`block_key`, `vault_path`), then `section_path` 1.0, `heading` 10.0, `content` 1.0, `tags` 1.0. Lower BM25 value = higher relevance (SQLite convention). Document in `docs/retrieval-guide.md`.
- **Search Query Parsing:** Support phrase queries (`"exact phrase"`) and FTS5 boolean operators (AND/OR/NOT); pass the query string directly to FTS5 MATCH
- **Regex Queries:** Detected when the query string is wrapped in `/…/`. FTS5 is first called with the bare terms extracted from the pattern to retrieve candidates; Python `re.search` is then applied to each candidate's `content` field. Only matching candidates are returned. This is a post-FTS filter, not a native FTS feature. Document the detection convention in `docs/retrieval-guide.md`.
- **Tag Filtering:** Tags are stored as a JSON array in `blocks.tags`. Each tag in the `tags` filter parameter is normalised (lowercased, leading `#` stripped) before comparison. For AND semantics, a `LIKE` clause is added per tag. Implemented in the query builder; not in FTS5 itself.
- **Path Filtering:** `paths` is a list of include globs. Each glob is converted to a `LIKE` pattern against `blocks.vault_path` (using the existing `_glob_to_regex`-style helper). Multiple include globs are OR'ed in SQL. `exclude_paths` is applied as `NOT (vault_path LIKE ?)` clauses AND'ed after the include filter.
- **`heading_level` in Results:** The `blocks_fts`/`blocks` tables do not store heading level. `heading_level` is obtained by joining `sections` on `blocks.section_key = sections.section_key`. This JOIN is required for all search and read_section responses.
- **`read_section` Response Fields:** `content` = heading line + section body (up to next same/higher-level heading). `context_prefix` = up to 3 non-heading source lines immediately above the heading; empty string when the heading is at file start or follows frontmatter only.
- **Result Formatting:** Snippet extraction done in Python, not SQL, for easier context handling
- **Caching:** No caching in MVP (but note where it could be added in Phase 6)

## Success Metrics

- [x] Read tools return results in <50ms consistently
- [x] Search completes in <100ms even on 5000-file vaults
- [x] Search top-3 relevance: >=80% of benchmark queries return relevant results in top 3
- [x] Tag/path filtering works on 100% of test cases
- [x] All tool contracts match Phase 0 specifications
- [x] Error messages are clear and actionable
- [x] Integration test suite passes on fixture vault in <5 seconds

## Open Questions

- Should search support regex queries or only simple/phrase matching?
  **Decision:** Regex is supported as a post-FTS Python filter. Query strings wrapped in `/…/` are detected by the handler; FTS5 runs on the extracted terms first, then `re.search` narrows the candidate set. Native FTS5 regex is not used.
- Should tag filter be OR'ed (any tag) or AND'ed (all tags)?
  **Decision:** AND semantics — all listed tags must be present on the block. Tag comparison is case-insensitive with leading `#` stripped.
- Should path filter support exclusion patterns (e.g., `not(wiki/private/*)`)?
  **Decision:** Yes, via a separate `exclude_paths` parameter (list of globs). The inline `not()` syntax is not supported; use `exclude_paths: ["wiki/private/**"]` instead.
- For read_section, should we return the heading line itself or just content?
  **Decision:** `content` always begins with the heading line. A separate `context_prefix` field returns up to 3 non-heading lines above the heading; it is never part of `content`.

## Dependencies

- Phase 0 must be complete (tool contracts, error codes)
- Phase 1 must be complete (config loading, guardrails)
- Phase 2A must be complete (FastMCP server bootstrap, project registry mapping, serve command)
- Phase 2 must be complete (indexing, parser, FTS schema)
- No dependency on Phase 4-5 (retrieval is independent)

## Deliverables

- `src/obsidian_memory_mcp/retrieval/` with `readers.py` (ReadNoteService + ReadSectionService) and `search.py` (SearchService)
- `src/obsidian_memory_mcp/server.py` (or mounted FastMCP handler module) with tool entry points for all three tools
- `src/obsidian_memory_mcp/contracts.py` updated: `read_section` contract must reflect `context_prefix` field and updated `content` definition; `search_notes` contract must reflect `heading_level`, `paths` as list, and `exclude_paths` parameter
- `tests/unit/test_read_note.py` with file reading and guardrail tests
- `tests/unit/test_read_section.py` with section extraction tests, including `context_prefix` assertions
- `tests/unit/test_search_notes.py` with FTS and filtering tests, including AND tag semantics, path include/exclude globs, and regex post-filter
- `tests/unit/test_contracts.py` updated to cover the revised `read_section` and `search_notes` contracts
- `tests/integration/test_retrieval_tools.py` with fixture vault end-to-end tests
- `docs/retrieval-guide.md` with tool examples, BM25 column weight rationale, regex convention, and expected results
- Fixture vault in `tests/fixtures/sample-vault/` with diverse content for testing
