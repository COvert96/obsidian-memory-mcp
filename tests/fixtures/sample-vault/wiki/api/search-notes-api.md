---
tags: [api, search, retrieval]
type: reference
---
# Search Notes API

The Search Notes API allows clients to query the FTS index with full-text search, filtered by path patterns, tags, and other metadata. Results are ranked by relevance and paginated for efficient retrieval.

## Overview

Search Notes provides a single tool `search_notes` that accepts a query string and optional filter parameters. The query is translated into an FTS5 SQL expression, executed against the indexed vault, and results are returned with rank scores and context snippets.

## Query Syntax

The query parameter accepts plain text or FTS5 boolean syntax. Plain text queries are automatically wrapped in a phrase search for better recall. FTS5 syntax supports AND, OR, NOT operators and quoted phrases. For example, `"proposal workflow" AND NOT deprecated` searches for proposals mentioning workflow but excludes deprecated notes.

## Filter Parameters

Results can be filtered by `paths` (array of glob patterns to include), `exclude_paths` (array of glob patterns to exclude), and `tags` (array of tags that must all be present). Multiple patterns in the same filter use OR logic, while different filter types use AND. For example, `paths: ["wiki/api/*"]` with `tags: ["api"]` returns only API files with the api tag.

### BM25 Scoring

Results are ranked using BM25, a probabilistic relevance model that accounts for term frequency, inverse document frequency, and document length. Shorter documents mentioning the query term multiple times rank higher than longer documents with single mentions.

### Path and Tag Filters

Path filters are matched against the vault-relative file path and support glob patterns like `*.md` and `**/private/*`. Tag filters require all specified tags to be present on a note. Filter combinations enable precise targeting of search scopes.

## Result Format

Each result includes `file_path`, `note_name`, `rank_score`, `matching_sections` (array of section headings), and `snippet` (a sentence-level excerpt highlighting the matched content). Results are paginated with optional cursor-based pagination. See [[fts-search-design]] and [[retrieval-tools]] for implementation details.
