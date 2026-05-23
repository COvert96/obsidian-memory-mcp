# PRD: Phase 3 - Retrieval Tools (Read and Search)

## Introduction

Implement the core retrieval capabilities: `read_note` (get entire file), `read_section` (get specific section), and `search_notes` (full-text search with filtering). These are MCP tools that return vault content with proper metadata and rankings.

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
- [ ] Tool parameter: `note_path` (path relative to vault root)
- [ ] Validates path against guardrails (Phase 1) before reading
- [ ] Returns: `{ content: str, frontmatter: dict, file_path: str, file_size_bytes: int }`
- [ ] Content is exact markdown from disk (no parsing or modification)
- [ ] Returns error `ERR_MISSING_FILE` if file doesn't exist
- [ ] Returns error `ERR_GUARDRAIL_VIOLATION` if path outside vault or not readable
- [ ] Performance: return file in <50ms (even for 100KB files)
- [ ] Handles special characters in filenames correctly

### US-002: Implement read_section MCP tool
**Description:** As a tool user, I want to read just one section of a markdown file so I don't need the entire file.

**Acceptance Criteria:**
- [ ] Tool parameters: `note_path`, `heading_name` (e.g., "Installation", "API Reference")
- [ ] Returns section content between heading and next heading of same/higher level
- [ ] Returns error `ERR_MISSING_FILE` if note doesn't exist
- [ ] Returns error `ERR_SECTION_NOT_FOUND` if heading not found in file
- [ ] Result includes: `{ heading: str, heading_level: int, content: str, file_path: str, context_lines: int }`
- [ ] Includes 2-3 lines of context above section heading
- [ ] Case-insensitive heading matching (accept "installation" for "## Installation")
- [ ] Performance: <50ms for any file/section combination

### US-003: Implement search_notes MCP tool with FTS
**Description:** As a tool user, I want to search the vault for notes matching keywords so I can find relevant content.

**Acceptance Criteria:**
- [ ] Tool parameters: `query` (required), `limit` (optional, default 10), `tags` (optional filter), `paths` (optional filter)
- [ ] Uses SQLite FTS5 index from Phase 2 for fulltext search
- [ ] Returns top-k results ranked by relevance
- [ ] Each result includes: `{ file_path: str, heading: str, preview: str, rank: float, tags: [str] }`
- [ ] Preview shows search term in context (snippet 100-200 characters with "..." around match)
- [ ] Optional tag filter: only return sections with matching tags
- [ ] Optional path filter: only return sections from files matching path glob (e.g., `wiki/**`)
- [ ] Empty query returns error with message "query is required"
- [ ] Handles multi-word queries: "complex query" searches all terms
- [ ] Performance: <100ms for typical queries on 5000-file vault

### US-004: Handle search ranking and relevance
**Description:** As a tool user, I want results ranked by relevance so I find the most important matches first.

**Acceptance Criteria:**
- [ ] Relevance ranking considers: term frequency, section heading level (H1 > H2 > content)
- [ ] Boost score for matches in heading vs content (2x weight)
- [ ] FTS5 native ranking or custom scoring implemented and documented
- [ ] Benchmark: on query "compliance", top 3 results contain relevant compliance content (measure via unit test with fixture vault)
- [ ] No irrelevant results in top 5 for common queries
- [ ] Ranking is deterministic (same query always produces same order)

### US-005: Implement search filters and result formatting
**Description:** As a tool user, I want to filter search by tags and paths so I can scope results.

**Acceptance Criteria:**
- [ ] Tag filter: `tags: ["urgent", "api"]` returns only sections with both tags
- [ ] Path filter: `paths: "wiki/api/**"` returns only files under wiki/api/
- [ ] Multiple filters are AND'ed (must match all)
- [ ] Results include section heading level so client can sort/format appropriately
- [ ] Search result snippets show match context with surrounding words (not just isolated term)
- [ ] Handles filters on non-indexed content gracefully (section content without tags returns empty filter)

### US-006: Create integration tests for retrieval tools
**Description:** As a developer, I need end-to-end tests so I can verify tools work on realistic vault content.

**Acceptance Criteria:**
- [ ] Fixture vault created with diverse content: multiple files, heading levels, tags, special characters
- [ ] Test `read_note` on each fixture file
- [ ] Test `read_section` on each heading in fixture vault
- [ ] Test `search_notes` with 15+ queries covering: single term, multi-term, common phrases, edge cases
- [ ] Tests verify result accuracy and latency (<100ms per search)
- [ ] Tests verify error handling (missing files, bad paths, etc.)

## Functional Requirements

- FR-1: `read_note` MCP tool returns complete file with frontmatter and content
- FR-2: `read_section` MCP tool returns specific heading/section with context
- FR-3: `search_notes` MCP tool performs FTS queries with optional filtering
- FR-4: All tools validate paths against vault guardrails before access
- FR-5: Search ranking prioritizes headings > content, with deterministic ordering
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
- **FTS5 Ranking:** Use SQLite FTS5 native BM25 ranking; document any custom scoring
- **Search Query Parsing:** Support phrase queries ("exact phrase") and boolean operators (AND/OR/NOT)
- **Result Formatting:** Snippet extraction done in Python, not SQL, for easier context handling
- **Caching:** No caching in MVP (but note where it could be added in Phase 6)

## Success Metrics

- [ ] Read tools return results in <50ms consistently
- [ ] Search completes in <100ms even on 5000-file vaults
- [ ] Search top-3 relevance: >=80% of benchmark queries return relevant results in top 3
- [ ] Tag/path filtering works on 100% of test cases
- [ ] All tool contracts match Phase 0 specifications
- [ ] Error messages are clear and actionable
- [ ] Integration test suite passes on fixture vault in <5 seconds

## Open Questions

- Should search support regex queries or only simple/phrase matching?
  A: Yes support regex queries.
- Should tag filter be OR'ed (any tag) or AND'ed (all tags)?
  A: Analysis required for retrieval quality.
- Should path filter support exclusion patterns (e.g., `not(wiki/private/*)`)?
  A: Yes.
- For read_section, should we return the heading line itself or just content?
  A: Yes return heading line.

## Dependencies

- Phase 0 must be complete (tool contracts, error codes)
- Phase 1 must be complete (config loading, guardrails)
- Phase 2 must be complete (indexing, parser, FTS schema)
- No dependency on Phase 4-5 (retrieval is independent)

## Deliverables

- `src/obsidian_memory_mcp/retrieval.py` with ReadNoteService, ReadSectionService, SearchService
- `src/obsidian_memory_mcp/tools.py` with MCP tool entry points for all three tools
- `tests/unit/test_read_note.py` with file reading and guardrail tests
- `tests/unit/test_read_section.py` with section extraction tests
- `tests/unit/test_search_notes.py` with FTS and filtering tests
- `tests/integration/test_retrieval_tools.py` with fixture vault end-to-end tests
- `docs/retrieval-guide.md` with tool examples and expected results
- Fixture vault in `tests/fixtures/sample-vault/` with diverse content for testing
