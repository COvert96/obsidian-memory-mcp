---
tags: [archive, indexing]
type: note
status: deprecated
---
# Old Index Schema

The original index schema used a relational approach with separate tables for files, sections, and blocks. It was replaced with an FTS5 virtual table for better performance and simpler queries.

## Previous Schema

The v1 schema had three tables: `vault_files` (file metadata), `vault_sections` (heading structure), and `vault_blocks` (searchable content). Queries required joining across tables, leading to complex SQL and poor performance on large vaults.

## Why It Changed

The v1 schema was designed before FTS5 became mature. Once FTS5 was available, it provided better BM25 ranking, simpler queries, and smaller index files. Migration to FTS5 reduced query latency by 70% and index size by 40% on production vaults.

## Migration Notes

The migration from v1 to v2 schema is automatic: on startup, if the old schema is detected, the system rebuilds the index into the new FTS5 format. No manual migration is required. The rebuild takes longer for the first run, but subsequent incremental indexes are faster. See [[indexing-pipeline]] and [[fts-search-design]] for the current schema design.
