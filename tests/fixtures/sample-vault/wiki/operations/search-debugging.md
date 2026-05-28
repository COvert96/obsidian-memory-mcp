---
tags: [operations, search, debugging]
type: runbook
---
# Search Debugging

When search results are unexpected or missing, this runbook helps diagnose the issue. It covers debug mode, interpreting output, and common problems with solutions.

## Debug Mode

Enable debug mode with `obsidian-memory search --debug "query"`. This prints the translated FTS query, the number of blocks scanned, execution time, and top 5 results with scores. Debug output is written to stderr, leaving stdout for results.

## Reading Debug Output

Debug output includes the FTS5 SQL that was executed, match counts per section (headings, content), and individual result scores. A result with score 1.0 is twice as relevant as one with score 0.5. Results are sorted by score (highest first).

## Common Search Problems

### No Results Returned

The query may be too specific, or the term does not appear in indexed blocks. Try: removing quotes (phrase search is stricter), checking spelling, using wildcards (`prefix*`), or checking that the index is recent with `obsidian-memory index --status`.

### Irrelevant Top Results

BM25 ranking prioritizes rare terms. If a common term ranks poorly, it may be overridden by a less frequent term. Try: removing common words, using AND to require multiple terms, or increasing the query specificity.

### Missing Expected Note

The note may not be indexed due to: incorrect path filter, missing tags, or the index being out of date. Try: removing path filters temporarily, checking the note's frontmatter tags, or running `obsidian-memory index` to refresh.

## Adjusting Queries

Use FTS operators to refine queries: `term1 AND term2` requires both, `term1 OR term2` matches either, and `"phrase"` requires exact phrase. For example, `"proposal workflow" AND NOT deprecated` searches for proposal + workflow while excluding deprecated notes.

## Path Filter Issues

Path filters use glob patterns. Common mistakes: forgetting the wildcard (`wiki/api` matches only files in api/, not subdirectories — use `wiki/api/**`), or using backslashes on Windows (use forward slashes in patterns). See [[search-notes-api]] and [[fts-search-design]] for more details.
