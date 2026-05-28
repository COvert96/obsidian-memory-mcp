---
tags: [operations, indexing, maintenance]
type: runbook
owner: platform-team
---
# Index Maintenance

The search index requires periodic maintenance to ensure performance and consistency. This runbook covers full rebuilds, cleanup, and monitoring for index size and health.

## When to Rebuild

Rebuild the index when: the vault has grown significantly (>10K files), you suspect the index is corrupted, or incremental indexing appears to be missing files. Rebuilds take longer than incremental updates but guarantee consistency.

## Full Rebuild Steps

Stop the MCP server, then execute `obsidian-memory index --full-rebuild` from the vault directory. The operation deletes the existing index and scans all files. Progress is printed to stdout. After rebuilding, restart the MCP server and verify search functionality.

## Cleaning Derived Data

Proposal and audit data accumulates over time. Run `obsidian-memory cleanup --prune-expired-proposals` to remove proposals older than the retention period (default 30 days). This reduces database file size. Use `--dry-run` to preview changes without applying them.

## Index Size Monitoring

Monitor the SQLite database file size: `ls -lh .vault-index.db` (Unix) or `dir .vault-index.db` (Windows). If the file is larger than 100MB, consider increasing maintenance frequency. Large indexes take longer to query, so monitor performance with `obsidian-memory search --benchmark`.

## Performance Tuning

Run `obsidian-memory optimize` to analyze index statistics and suggest improvements. The output may recommend reindexing, increasing cache, or adjusting tokenizer settings. Most vaults perform well with default settings and need optimization only after reaching 100K+ blocks. See [[incremental-indexing]] and [[troubleshooting-guide]] for more details.
