---
tags: [operations, indexing, runbook]
type: runbook
status: active
owner: platform-team
---
# Incremental Indexing

Incremental indexing updates the search index with only changed files, making it much faster than full rebuilds. This runbook explains how to run, schedule, and troubleshoot incremental indexing.

## Overview

The `obsidian-memory index` command with no flags performs incremental indexing. It detects changed, added, and deleted files using filesystem timestamps, then updates the index accordingly. The first run (full index) takes longer; subsequent runs are typically complete in seconds.

## Running the Index Command

Execute `obsidian-memory index` from the vault directory. The command prints progress (number of files scanned, changes detected, blocks indexed). Exit code 0 indicates success. Use `--verbose` for detailed output or `--full-rebuild` to force a complete reindex.

## Scheduling Indexing

Indexing can be scheduled via cron (Unix) or Task Scheduler (Windows). Example cron job for Unix: `0 * * * * cd /path/to/vault && obsidian-memory index`. This runs indexing every hour. Adjust the schedule based on how frequently your vault changes.

## Checking Index Status

Run `obsidian-memory index --status` to see when the index was last updated and how many blocks are indexed. The output shows the index timestamp, total block count, and any errors from the last run.

## Troubleshooting Stale Index

If search results seem out of date, run `obsidian-memory index --full-rebuild` to rebuild the index from scratch. This resolves corrupted indexes or timestamp inconsistencies. After rebuilding, subsequent incremental runs should be fast again. See [[indexing-pipeline]] and [[index-maintenance]] for advanced topics.
