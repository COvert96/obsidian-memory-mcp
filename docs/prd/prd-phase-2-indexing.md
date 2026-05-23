# PRD: Phase 2 - Markdown Ingestion and Indexing

## Introduction

Build the indexing engine that parses markdown files from the vault, extracts structure (frontmatter, headings, sections, wikilinks), and stores indexed metadata in SQLite with FTS5 (Full Text Search) capabilities. Indexing is manual, triggered via CLI commands, not automatic/watched.

## Goals

- Parse markdown with YAML frontmatter, headings, and sections
- Build deterministic SQLite FTS5 index with metadata tracking
- Provide CLI commands to index, reindex, and check indexing status
- Track file hashes to enable incremental reindexing
- Support repeatable, deterministic index operations

## User Stories

### US-001: Implement markdown parser for vault files
**Description:** As a developer, I need a parser that extracts frontmatter, headings, and sections from markdown so I can index vault content.

**Acceptance Criteria:**
- [ ] Parser extracts: YAML frontmatter, H1/H2/H3 headings, section content between headings, wikilinks
- [ ] Handles edge cases: missing frontmatter, multiple H1s, empty sections, malformed YAML
- [ ] Returns structured output: `ParsedNote` object with frontmatter dict, sections list, metadata
- [ ] Section boundaries correct: content under H2 "## Foo" ends when next H2/H1 appears
- [ ] Wikilinks extracted as list: `[[Page Name]]`, `[[Page|display text]]`
- [ ] Performance: parse 1000 files in <5 seconds
- [ ] 20+ unit tests cover: valid notes, missing frontmatter, nested headings, special characters, trailing whitespace

### US-002: Design SQLite schema for index and metadata
**Description:** As a developer, I need a schema that stores notes, sections, and search metadata so indexing is queryable.

**Acceptance Criteria:**
- [ ] Schema includes tables: `files` (vault files), `sections` (indexed sections), `wikilinks` (note references)
- [ ] `files` table: `id`, `vault_path`, `file_hash` (SHA256 of content), `frontmatter_json`, `tags`, `indexed_at`
- [ ] `sections` table: `id`, `file_id`, `heading`, `heading_level`, `content`, `content_hash`, `char_count`
- [ ] FTS5 virtual table: `sections_fts` over `heading` + `content` for fulltext search
- [ ] Unique constraint on `(file_id, heading_level, heading)` to prevent duplicate sections
- [ ] Indexes on: `file_path` (unique), `file_hash`, `indexed_at`
- [ ] Schema supports 100k+ sections without performance degradation

### US-003: Implement markdown indexer service
**Description:** As a developer, I need an indexer that can parse files and write them to the database deterministically.

**Acceptance Criteria:**
- [ ] Indexer reads all markdown files from vault matching config path patterns
- [ ] Parses each file and stores in database using schema from US-002
- [ ] Hash-based deduplication: if file_hash unchanged, skip reparse (but update `indexed_at`)
- [ ] Supports full reindex (drop and rebuild) and incremental (new/changed files only)
- [ ] Returns summary: `{ files_processed: 42, sections_indexed: 312, errors: 0, duration_ms: 1250 }`
- [ ] Handles errors gracefully: logs bad files, continues indexing rest
- [ ] Transactions: all-or-nothing commits (no partial indexes)
- [ ] Performance: index 5000-file vault in <30 seconds

### US-004: Create CLI commands for indexing operations
**Description:** As an operator, I need CLI commands to trigger indexing and check status.

**Acceptance Criteria:**
- [ ] Command `mcp-memory index {vault_path}` — full reindex
- [ ] Command `mcp-memory index --incremental {vault_path}` — update changed files only
- [ ] Command `mcp-memory index status {vault_path}` — show indexed file count, last index time, errors
- [ ] Command output includes: files indexed, sections created, duration, any errors encountered
- [ ] Commands validate config (from Phase 1) before proceeding
- [ ] Respects write constraints: only reads from allowed vault paths
- [ ] Confirmation prompt before full reindex (to prevent accidental data loss)
- [ ] Exit code 0 on success, non-zero on failure
- [ ] Help text: `mcp-memory index --help`

### US-005: Add index status and error reporting
**Description:** As an operator, I need visibility into indexing health so I know if vault files are properly indexed.

**Acceptance Criteria:**
- [ ] Status report shows: total files in vault, indexed files, unindexed files, errors
- [ ] Errors reported with: file path, error type (parse error, permission denied, etc.), suggestion
- [ ] Database stores last_indexed timestamp for each file
- [ ] Status detects drift: files modified since last index
- [ ] Warning threshold: if >10% of vault files have errors, highlight in status output
- [ ] Status runs in <1 second even for large vaults (5000+ files)

### US-006: Document indexing workflow and troubleshooting
**Description:** As an operator, I need guidance on when and how to index so I can keep vault indexed and handle errors.

**Acceptance Criteria:**
- [ ] Indexing workflow doc covers:
  - Initial full index after vault setup
  - Incremental index during development
  - Full reindex workflow (when to use, what to expect)
  - Handling indexing errors (permission denied, malformed YAML, etc.)
- [ ] Troubleshooting guide for common issues:
  - "Index is stale" — solution is incremental reindex
  - "Files show as unindexed" — solution is full reindex
  - "Parse error on file X" — how to fix YAML frontmatter
- [ ] Performance expectations: how long indexing takes for different vault sizes

## Functional Requirements

- FR-1: Markdown parser extracts frontmatter, headings, sections, wikilinks
- FR-2: SQLite schema with `files`, `sections`, `wikilinks`, FTS5 virtual table
- FR-3: Indexer uses file hash to avoid reparsing unchanged files
- FR-4: Full reindex clears and rebuilds all index data
- FR-5: Incremental index updates only new/changed files
- FR-6: All indexing respects vault guardrails from Phase 1
- FR-7: Index status available via CLI and programmatically (for tools to check freshness)
- FR-8: Malformed files are logged as errors, indexing continues for rest of vault

## Non-Goals

- No automatic file watching (operator triggers reindex manually)
- No background indexing daemon (CLI-only for MVP)
- No support for non-markdown file types
- No incremental section diffing (if file changed, all sections are reindexed)
- No full-text search ranking or relevance scoring (Phase 3 handles retrieval)

## Technical Considerations

- **Parser:** Regex or simple state machine approach; use `yaml` library for frontmatter
- **SQLite:** In-process database, no remote/network DB for MVP
- **FTS5:** SQLite built-in full-text search, no external search engine
- **Hashing:** SHA256 of file content for change detection
- **Error Handling:** Log individual file errors, don't abort indexing
- **Transaction Scope:** One transaction per indexing operation (all-or-nothing)
- **Storage:** Index location specified in config (`index_db_location`)

## Success Metrics

- [ ] Parse 5000-file vault with mixed frontmatter/section styles in <30 seconds
- [ ] Incremental index on 1 changed file completes in <500ms
- [ ] Hash-based deduplication skips 100% of unchanged files
- [ ] Indexing errors are logged clearly and don't stop remaining files from being indexed
- [ ] Index status reports drift detection accurately (within 1 second)
- [ ] FTS5 search index supports queries from Phase 3 with <50ms response time

## Open Questions

- Should indexing support excluding certain paths (e.g., `.mcp/` directory)?
  A: Yes.
- Should section headers at level >3 be indexed separately or combined into parent section?
  A: Combined.
- Should wikilinks be extracted to separate table or stored as part of section content?
  A: Extracted to separate table.
- Should frontmatter tags be indexed separately from file content tags?
  A: No.

## Dependencies

- Phase 0 must be complete (error codes, schema validation approach)
- Phase 1 must be complete (config loading, path validation, guardrails)
- No dependency on Phase 3+ (indexing is self-contained)

## Deliverables

- `src/obsidian_memory_mcp/parser.py` with MarkdownParser and ParsedNote class
- `src/obsidian_memory_mcp/schema.py` with SQLite schema creation function
- `src/obsidian_memory_mcp/indexer.py` with MarkdownIndexer service
- `src/obsidian_memory_mcp/cli.py` with index CLI commands (add to existing)
- `docs/indexing-guide.md` with workflow and troubleshooting
- `tests/unit/test_parser.py` with 20+ parsing scenarios
- `tests/unit/test_indexer.py` with full/incremental index tests
- `tests/integration/test_indexing_workflow.py` with end-to-end fixture vault
