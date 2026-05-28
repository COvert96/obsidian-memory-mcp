---
tags: [architecture, indexing]
type: concept
---
# Indexing Pipeline

The indexing pipeline is responsible for maintaining the vault's full-text search index. It discovers markdown files, parses their contents, extracts metadata, and populates the SQLite FTS5 index with indexed blocks. The pipeline can run incrementally (scanning only modified files) or perform full rebuilds when necessary.

## Overview

The pipeline runs either on-demand or on a scheduled interval. It uses filesystem watches or file modification timestamps to detect changes. Modified files are rescanned, added files are indexed, and deleted files are removed from the index. The pipeline maintains consistency by locking the database during index updates.

## File Discovery

The file discovery phase recursively scans the vault directory for markdown files. It respects .gitignore-style patterns to exclude files or directories. Hidden files and directories (starting with .) are skipped unless explicitly included. Discovery produces a list of candidate files for parsing.

### Parsing Phase

Each markdown file is parsed to extract YAML frontmatter (tags, type, owner, status), the H1 title, and all H2/H3 sections with their content. Wikilinks are extracted and normalized for cross-reference tracking. Section splitting identifies boundaries for fine-grained indexing — sections are indexed as separate documents to improve search result relevance.

#### Frontmatter Extraction

The parser uses a YAML library to deserialize frontmatter into key-value pairs. If frontmatter is malformed, the file is skipped with a warning. Required fields are validated and missing fields are filled with defaults.

#### Section Splitting

Each heading level 2 and deeper is treated as an indexed block. Blocks are assigned unique IDs based on file path and heading hierarchy. Blocks inherit parent tags and metadata, enabling tag-based filtering of search results.

#### Wikilink Parsing

Wikilinks are extracted using regex and normalized to matching note names. Cross-reference edges are stored in a separate table for graph-based queries.

## FTS Index Update

Parsed blocks are written to the FTS virtual table in batches. Each block is indexed with its file path, section hierarchy, tags, and content. The index is then immediately usable by the search API.

## Incremental Indexing

Modified files are detected via inode timestamps (Unix) or file modification time (Windows). Only changed files are reparsed, reducing runtime for large vaults. The --full-rebuild flag forces a complete reindex regardless of timestamps. See [[system-overview]] and [[fts-search-design]] for more details.
