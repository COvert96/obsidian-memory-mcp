# PRD: Phase 2 - Markdown Ingestion and Indexing (Revised)

## Document Control

- Phase: 2
- Status: Approved for implementation
- Revised: 2026-05-24
- Related docs:
  - docs/system-architecture.md
  - docs/prd/prd-phase-1-config-safety.md
  - docs/prd/prd-phase-3-retrieval.md

## 1. Overview

Phase 2 builds a deterministic indexing pipeline for Obsidian markdown vaults. The vault remains the source of truth. SQLite is a derived index that can be rebuilt at any time.

This revision tightens architecture boundaries so policy logic remains testable and independent of database and CLI details:

- Domain policy: parsing rules, index freshness logic, and drift/status logic
- Infrastructure detail: SQLite schema, FTS5, file IO, and command-line rendering

Indexing is operator-triggered only. No file watching and no background daemon in this phase.

## 2. Problem Statement

Without a deterministic index, read and search tools cannot reliably retrieve relevant context from large vaults. A robust indexing layer is required before Phase 3 retrieval APIs can be trusted.

The system must:

1. Parse markdown structure consistently, including frontmatter and links.
2. Track freshness and drift so operators can trust index state.
3. Expose operational diagnostics (status, errors, debug search).
4. Stay resilient: individual file failures must not corrupt or abort whole runs.

## 3. Goals

1. Parse markdown files into stable structural units (files, sections, blocks, wikilinks, tags).
2. Persist deterministic index data in SQLite with FTS5 over retrieval blocks.
3. Support incremental and full reindex workflows.
4. Provide clear status, drift, and error visibility.
5. Keep implementation aligned with Clean Architecture dependency direction.

## 4. Non-Goals

1. No automatic filesystem watching.
2. No embeddings or semantic/vector search.
3. No non-markdown indexing.
4. No direct writes to vault content.
5. No cross-vault federated index.
6. No background indexing service.

## 5. Actors And Responsibilities

1. Operator:
   - Runs index commands.
   - Interprets status/errors.
2. Developer:
   - Maintains parser/indexer/status code.
   - Uses debug search to diagnose ranking behavior.
3. MCP tool layer (future phase consumer):
   - Reads indexed data; does not own indexing workflow.

## 6. Architecture Constraints (Blocking)

These constraints are required and override local implementation convenience.

1. Dependency rule:
   - Core policy modules must not depend on CLI formatting concerns.
   - Parser policy must not depend on SQLite APIs.
2. Single-writer policy:
   - Parsing may be parallelized.
   - DB writes are serialized through one writer path.
3. Determinism:
   - Same vault content + same parser version + same config => equivalent index content (excluding run IDs and timestamps).
4. Guardrails first:
   - Vault path and access checks from Phase 1 must execute before file reads.
5. Derived-data principle:
   - Index DB is rebuildable and must never be treated as source-of-truth content.

## 7. Scope

### In Scope

1. Markdown parser and parse model.
2. SQLite schema and versioning.
3. Indexer service for full and incremental modes.
4. Status and drift reporting.
5. Debug FTS search inspection.
6. CLI commands for index workflows.
7. Unit and integration tests.
8. Operator documentation.

### Out Of Scope

1. Retrieval ranking improvements beyond FTS5/BM25.
2. Proposal/write workflows (Phase 5).
3. Context pack generation (Phase 4).

## 8. User Stories And Acceptance Criteria

### US-001: Parse markdown into deterministic structures

Description: As a developer, I need deterministic parsed note structures so indexing and retrieval are stable across runs.

Acceptance Criteria:

- [x] Parser extracts frontmatter, headings, sections, blocks, wikilinks, markdown tags, and frontmatter tags.
- [x] Headings inside fenced code blocks are ignored as structural headings.
- [x] Malformed YAML does not fail file parsing; parser returns `frontmatter_parse_error`.
- [x] Repeated headings are disambiguated deterministically with ordinal suffixes.
- [x] Section keys are deterministic: `<vault_path>#<heading_slug>#<ordinal>`.
- [x] Block keys are deterministic: `<section_key>::block-<ordinal>`.
- [x] Section keys and block keys are deterministic index identifiers, not durable long-term knowledge IDs.
- [x] Parser output object includes:
  - `vault_path`
  - `frontmatter`
  - `frontmatter_parse_error`
  - `headings`
  - `sections`
  - `blocks`
  - `wikilinks`
  - `tags`
  - `raw_content_hash`
  - `normalized_content_hash`
  - `parser_version`
- [x] Unit tests cover at least 30 parser scenarios.
- [x] Parse performance target: 1,000 files (avg 5KB) in under 5 seconds on modern SSD-backed dev machine.

### US-001A: Deterministic block segmentation rules

Description: As a developer, I need a precise blocking algorithm so retrieval behavior is consistent across implementations.

Acceptance Criteria:

- [x] Blocks are deterministic retrieval units generated from section content.
- [x] Target block size is 300-700 estimated tokens.
- [x] Hard max block size is 1,000 estimated tokens.
- [x] Fenced code blocks remain atomic unless they exceed hard max.
- [x] Markdown tables remain atomic unless they exceed hard max.
- [x] Prose splits on paragraph boundaries first.
- [x] No overlap between adjacent blocks in Phase 2.
- [x] Each block inherits `vault_path`, `section_path`, heading, and tags.
- [x] Empty or whitespace-only blocks are not indexed.
- [x] Tiny sections may collapse into a single block when under minimum size.
- [x] Oversized sections split deterministically according to the above boundaries.

### US-002: Persist index schema with FTS5

Description: As a developer, I need a queryable schema with run metadata and diagnostics.

Acceptance Criteria:

- [x] Schema includes: `index_runs`, `files`, `sections`, `blocks`, `wikilinks`, `index_errors`, `blocks_fts`.
- [x] Unique constraints exist on:
  - `files.vault_path`
  - `sections.section_key`
  - `blocks.block_key`
- [x] Required secondary indexes exist for file freshness, section/block joins, wikilink target lookups, and run error lookup.
- [x] `PRAGMA user_version` is set and validated by schema bootstrap.
- [x] FTS5 table indexes retrieval blocks (not files/sections as retrieval unit):
  - `block_key`, `vault_path`, `section_path`, `heading`, `content`, `tags`
- [x] Phase 2 uses explicit FTS synchronization in indexer transactions (no SQLite triggers).
- [x] FTS row delete/insert behavior occurs in the same transaction as `blocks` changes.
- [x] Tests verify no orphaned FTS rows after block update/delete and deleted-file tombstoning.
- [x] Schema creation is idempotent.

### US-003: Run full and incremental indexing

Description: As an operator, I need fast incremental indexing and safe full rebuilds.

Acceptance Criteria:

- [x] Eligible `.md` files are discovered within allowed vault roots and include/exclude policies.
- [x] Default exclusions include: `.git/`, `.obsidian/`, `.trash/`, `.mcp/`, and index DB path.
- [x] Incremental freshness uses stat-first logic:
  - compare `vault_path`, `size_bytes`, `mtime_ns`, `parser_version`
  - if unchanged, skip without reading file body
  - if changed/unknown, read file and compute `file_hash`
  - if `file_hash` is unchanged after metadata drift, update metadata and skip parse
- [x] Parser version change marks old rows stale and triggers reindex behavior.
- [x] Changed file reindex deletes and recreates dependent rows (`sections`, `blocks`, `wikilinks`, `blocks_fts`) atomically for that file.
- [x] Deleted files are detected each run.
- [x] Deleted-file default behavior is tombstone (`deleted_at`), not hard delete.
- [x] Tombstoned files keep a `files` row but remove searchable/derived rows (`sections`, `blocks`, `wikilinks`, `blocks_fts`).
- [x] If a tombstoned path reappears, indexer treats it as changed/new: clears `deleted_at`, clears `last_error_id` on success, and rebuilds dependent rows.
- [x] Full reindex rebuilds derived tables while preserving schema version metadata.
- [x] Index run summary returns:
  - `index_run_id`
  - `mode`
  - `files_seen`
  - `files_processed`
  - `files_skipped`
  - `files_deleted`
  - `files_failed`
  - `sections_indexed`
  - `blocks_indexed`
  - `errors`
  - `duration_ms`
- [x] Run status is one of: `success`, `success_with_errors`, `failed`.
- [x] Non-fatal file errors do not abort whole run.
- [x] A malformed-YAML file with indexed body content counts as:
  - `files_processed += 1`
  - `errors += 1`
  - `files_failed` unchanged
  - run status `success_with_errors`
- [x] Fatal DB/schema errors abort run and mark run `failed`.
- [x] Performance targets:
  - full index 5,000 files (avg 5KB) in under 30 seconds
  - incremental with 1 changed file in under 500ms (excluding process startup)

### US-004: Operate indexing via CLI

Description: As an operator, I need reliable commands and exit codes for local and CI use.

Acceptance Criteria:

- [x] Commands exist:
  - `mcp-memory index {vault_path}`
  - `mcp-memory index --full {vault_path}`
  - `mcp-memory index status {vault_path}`
  - `mcp-memory index errors {vault_path}`
  - `mcp-memory debug search {vault_path} "{query}"`
- [x] Repair path is explicit: `mcp-memory index --full --yes {vault_path}` is the supported index repair operation in Phase 2.
- [x] Full reindex requires confirmation unless `--yes` is passed.
- [x] Commands validate config and guardrails before indexing.
- [x] Exit codes:
  - `0`: success
  - `1`: fatal failure
  - `2`: success with indexing errors
  - `3`: invalid config/guardrail violation
- [x] Help text exists for all index and debug search commands.

### US-005: Report index health and drift

Description: As an operator, I need to know if index data is fresh and trustworthy.

Acceptance Criteria:

- [x] Status output includes:
  - vault path
  - index DB path
  - schema version
  - parser version
  - last run time and status
  - total markdown files
  - indexed files
  - unindexed files
  - changed files
  - deleted indexed files
  - files with errors
  - total sections
  - total blocks
  - total wikilinks
- [x] Drift detection includes:
  - modified files since last index
  - deleted files since last index
  - files present in vault but not indexed
  - files indexed with old parser version
- [x] Warn when >10% eligible files currently have indexing errors.
- [x] Warn when parser version drift exists.
- [x] Status call completes in under 1 second for 5,000-file vault without reparsing file bodies.

### US-006: Inspect FTS behavior for diagnostics

Description: As a developer, I need transparent search diagnostics to tune retrieval quality.

Acceptance Criteria:

- [x] Debug search reads from `blocks_fts` joined to canonical metadata tables.
- [x] Output includes:
  - query
  - matched `block_key`
  - `vault_path`
  - `section_path`
  - heading
  - BM25 score
  - snippet
  - token count estimate
  - tags
- [x] Optional filters:
  - `--limit`
  - `--path`
  - `--tag`
- [x] Debug search supports structured JSON output via `--json`.
- [x] Typical query returns in under 50ms on 250,000 indexed blocks on modern dev hardware.

### US-007: Document workflow and troubleshooting

Description: As an operator, I need clear docs to run and troubleshoot indexing safely.

Acceptance Criteria:

- [x] `docs/indexing-guide.md` covers:
  - first-time index
  - incremental cycle
  - full reindex and when to use it
  - parser version invalidation
  - deleted-file behavior
  - status interpretation
  - debug search interpretation
- [x] Troubleshooting covers:
  - stale index
  - unindexed files
  - malformed YAML
  - permission denied
  - database locked
  - FTS inconsistency
  - parser drift
  - unexpected query matches
- [x] Docs explicitly state DB is derived data and direct DB edits are unsupported.

## 9. Functional Requirements

- FR-1: Parse markdown into structured note models with stable identifiers.
- FR-2: Ignore heading markers inside fenced code blocks.
- FR-3: Store files/sections/blocks/wikilinks/index-run/errors in SQLite.
- FR-4: Index retrieval units as blocks in FTS5.
- FR-5: Use SHA256 for raw and normalized content hashes.
- FR-6: Use parser version as freshness input.
- FR-7: Use stat-first incremental freshness checks before content hashing.
- FR-8: Support incremental and full indexing modes.
- FR-9: Detect and process deleted files explicitly with tombstone semantics.
- FR-10: Tombstoned files must be removed from searchable derived tables.
- FR-11: Record non-fatal file errors without aborting whole run.
- FR-12: Abort run on fatal schema/database failures.
- FR-13: Provide programmatic status data for future MCP tools.
- FR-14: Provide debug search diagnostics for ranking transparency, including JSON mode.
- FR-15: Apply deterministic block segmentation rules for retrieval units.
- FR-16: Normalize paths and newline handling consistently for cross-platform hashing/indexing.

## 10. Non-Functional Requirements

- NFR-1: Deterministic output for deterministic input.
- NFR-2: Single writer for SQLite mutations.
- NFR-3: WAL mode and foreign keys enabled.
- NFR-4: Schema bootstrap idempotent.
- NFR-5: Status endpoint performance under 1 second for 5,000-file vault.
- NFR-6: Incremental one-file update under 500ms (excluding startup).
- NFR-7: Clear operator-visible diagnostics for lock and permission failures.

## 10.1 Normalization And Path Safety Rules

1. Store `vault_path` with POSIX separator `/` in index tables.
2. Normalize `.` and `..` path segments before indexing decisions.
3. Resolve symlinks before guardrail validation.
4. Reject files whose resolved real path escapes allowed vault roots.
5. `raw_content_hash` is byte-exact SHA256 of file bytes.
6. `normalized_content_hash` is SHA256 after newline normalization to LF.
7. Section/block content hashes use normalized LF content.

## 11. Data Contracts

### 11.1 Parser Models

Required dataclasses (or equivalent typed models):

- `ParsedNote`
- `ParsedSection`
- `ParsedBlock`
- `ParsedWikilink`

Model fields must match US-001 acceptance criteria and be immutable or treated immutably once produced.

### 11.2 Index Run Result Contract

Indexer return payload:

- `index_run_id: int`
- `mode: "incremental" | "full"`
- `status: "success" | "success_with_errors" | "failed"`
- `files_seen: int`
- `files_processed: int`
- `files_skipped: int`
- `files_deleted: int`
- `files_failed: int`
- `sections_indexed: int`
- `blocks_indexed: int`
- `errors: int`
- `duration_ms: int`

### 11.3 File Outcome Semantics

1. `files_processed`: file produced indexable body content and metadata update for current run.
2. `files_skipped`: file determined fresh without reparsing.
3. `files_failed`: file produced no usable indexable body due to read/parse/system failure.
4. Malformed YAML with successful body indexing counts as processed-with-error, not failed.

## 12. Implementation Plan (Thin Slices)

1. Slice 1: schema bootstrap and migration/version checks.
2. Slice 2: parser with deterministic section/block IDs.
3. Slice 3: file discovery and incremental freshness decision engine.
4. Slice 4: transactional write path (file upsert + dependent row rebuild + FTS sync).
5. Slice 5: status and drift reporting service.
6. Slice 6: debug search service.
7. Slice 7: CLI wiring and exit codes.
8. Slice 8: docs and integration test hardening.

## 13. Testing Strategy

### Unit Tests

- `tests/unit/test_parser.py` (30+ scenarios)
- `tests/unit/test_schema.py`
- `tests/unit/test_indexer.py`
- `tests/unit/test_status.py`
- `tests/unit/test_search_debug.py`

### Integration Tests

- `tests/integration/test_indexing_workflow.py`

Required integration scenarios:

1. Initial full index on fixture vault.
2. Incremental run with no changes (all skipped).
3. One-file change incremental reindex.
4. Deleted file tombstone behavior.
5. Parser version bump causes stale detection and reindex.
6. Malformed YAML logs error while body still indexed.
7. FTS consistency after updates/deletes.
8. Tombstoned file reappears and dependent rows are rebuilt.
9. Metadata drift with unchanged file hash updates metadata without reparsing.

## 14. CLI Contract

### Index

- `mcp-memory index {vault_path}`
- `mcp-memory index --full {vault_path}`
- `mcp-memory index --full --yes {vault_path}`

### Status And Errors

- `mcp-memory index status {vault_path}`
- `mcp-memory index errors {vault_path}`

### Debug Search

- `mcp-memory debug search {vault_path} "{query}" --limit 10 --path wiki/ --tag compliance`
- `mcp-memory debug search {vault_path} "{query}" --json`

### Repair

- `mcp-memory index --full --yes {vault_path}` is the supported repair workflow for stale/corrupt derived index state in Phase 2.

### Exit Codes

- `0`: success
- `1`: fatal error
- `2`: success with indexing errors
- `3`: config or guardrail violation

## 15. Dependencies

1. Phase 0 contracts and error model conventions.
2. Phase 1 config loading and path/guardrail enforcement.
3. SQLite build with FTS5 support.
4. No dependency on retrieval APIs, embeddings, or provider-specific services.

### 15.1 Technology Choice Notes

Phase 2 implementation preference is Python `sqlite3` with explicit SQL statements, transactional boundaries, and `PRAGMA user_version` migration tracking.

Rationale for this phase:

1. Keeps the indexing write path simple and predictable for deterministic rebuild behavior.
2. Minimizes abstraction overhead during high-throughput ingest and reindex workflows.
3. Matches current project dependencies and phase scope.

SQLAlchemy and Alembic are acceptable future upgrades, but are not a Phase 2 requirement. Adopt them only if one or more triggers occur:

1. Migration complexity requires branching/versioned migration scripts beyond manageable explicit SQL.
2. Schema evolution requires cross-phase downgrade/upgrade orchestration in CI and release workflows.
3. Repository-wide data access patterns converge on shared ORM models that improve maintainability more than they hurt indexing throughput.

If adopted later, keep parser and index policy logic independent of ORM concerns, and confine ORM usage to infrastructure modules.

## 16. Risks And Mitigations

1. Risk: parser edge cases cause unstable section boundaries.
   - Mitigation: golden fixtures + deterministic-key assertions.
2. Risk: schema drift between code and tests.
   - Mitigation: schema bootstrap assertions and migration version checks in CI.
3. Risk: SQLite lock contention.
   - Mitigation: single writer, bounded transactions, clear retry/failure messages.
4. Risk: stale index misleads operators.
   - Mitigation: explicit drift reporting and parser-version warnings in status.

## 17. Success Metrics

- [x] Parse 1,000 files (avg 5KB) in under 5 seconds.
- [x] Full index 5,000 files (avg 5KB) in under 30 seconds.
- [x] Incremental with one changed file under 500ms (excluding startup).
- [x] 100% unchanged files skipped when freshness inputs are unchanged.
- [x] Parser version drift detected and reported correctly.
- [x] Deleted files handled correctly via tombstoning.
- [x] Status drift report under 1 second for 5,000-file vault.
- [x] Debug search under 50ms for typical queries on 250,000 blocks.

## 18. Deliverables

- `src/obsidian_memory_mcp/parser.py`
- `src/obsidian_memory_mcp/schema.py`
- `src/obsidian_memory_mcp/indexer.py`
- `src/obsidian_memory_mcp/status.py`
- `src/obsidian_memory_mcp/search_debug.py`
- `src/obsidian_memory_mcp/cli.py` (extended)
- `docs/indexing-guide.md`
- `tests/unit/test_parser.py`
- `tests/unit/test_schema.py`
- `tests/unit/test_indexer.py`
- `tests/unit/test_status.py`
- `tests/unit/test_search_debug.py`
- `tests/integration/test_indexing_workflow.py`

## 19. Open Questions

1. Should hard-delete become a configurable alternative to tombstoning in Phase 3?
2. Should health scoring be introduced in a later phase once real operational distributions are observed?
