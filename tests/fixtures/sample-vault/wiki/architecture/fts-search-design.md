---
tags: [architecture, search, sqlite]
type: concept
---
# FTS Search Design

SQLite FTS5 (Full-Text Search version 5) provides the indexing and retrieval engine for vault search. It offers probabilistic relevance ranking, boolean query operators, and efficient incremental index updates. This document explains why FTS5 was chosen and how it is configured.

## Why SQLite FTS5

FTS5 is part of SQLite, eliminating the need for an external search engine dependency. It provides BM25 relevance scoring out-of-the-box, supports incremental updates, and is battle-tested in production systems. The index is stored as a single file (the vault's SQLite database) and benefits from SQLite's ACID guarantees.

## Schema Design

The FTS index uses a virtual table named `vault_search` with columns for `file_path`, `block_id`, `section`, `tags`, and `content`. The content column is the full-text indexed field. Additional columns store metadata necessary for filtering and result formatting.

### Virtual Table Structure

The FTS5 virtual table is created with `CREATE VIRTUAL TABLE vault_search USING fts5(file_path UNINDEXED, block_id UNINDEXED, section, tags, content)`. The UNINDEXED keyword on metadata columns reduces index size without affecting query capability — these columns are used for filtering only.

### Tokenizer Configuration

The default tokenizer splits on whitespace and punctuation. A custom tokenizer configuration could implement language-specific stemming or synonym expansion, but the default is suitable for technical documentation.

## Query Translation

User queries are translated into FTS5 syntax before execution. Unquoted searches are wrapped in phrase queries for better precision. Special characters are escaped. Query operators (AND, OR, NOT) are passed through directly.

## Ranking and Scoring

BM25 scoring balances term frequency (words appearing multiple times rank higher) with inverse document frequency (rare terms are more informative). Section-level indexing means matches in headings and subsections are ranked separately from body content, improving the relevance of short results.

## Known Limitations

FTS5 does not support phrase queries across section boundaries. Wildcards are not supported in quoted phrases. For complex queries, clients may need to use multiple search terms and filter results post-hoc. See [[indexing-pipeline]] and [[search-notes-api]] for detailed information.
