# Indexing Guide

The SQLite index is derived data. Markdown files in the Obsidian vault remain the
source of truth, and direct database edits are unsupported. If the database is
stale or inconsistent, rebuild it from the vault.

## First-Time Index

1. Create and validate `memory-mcp.yaml` in the vault root:

   ```powershell
   uv run mcp-memory config validate C:\path\to\vault
   ```

2. Build the initial index:

   ```powershell
   uv run mcp-memory index C:\path\to\vault
   ```

The command creates the configured SQLite database, bootstraps the schema, parses
eligible markdown files, and writes files, sections, blocks, wikilinks, errors,
run metadata, and FTS rows.

## Incremental Cycle

Run the same command after editing notes:

```powershell
uv run mcp-memory index C:\path\to\vault
```

Incremental indexing checks file path, size, modified time, and parser version
before reading file bodies. Unchanged files are skipped. If file metadata changed,
the indexer reads the file and hashes it; unchanged content updates metadata
without reparsing.

## Full Reindex And Repair

Full reindexing reparses all eligible markdown files and recreates derived rows.
Use it when repairing stale or corrupt derived index state, after manual database
deletion, or when troubleshooting FTS inconsistency.

Interactive full reindex:

```powershell
uv run mcp-memory index --full C:\path\to\vault
```

Non-interactive repair:

```powershell
uv run mcp-memory index --full --yes C:\path\to\vault
```

## Parser Version Invalidation

The parser version is stored with each indexed file. When the parser version
changes, existing rows are reported as parser drift and are reindexed on the next
incremental run.

Check drift:

```powershell
uv run mcp-memory index status C:\path\to\vault
```

## Deleted Files

Deleted markdown files are tombstoned by default. The `files` row remains with a
`deleted_at` value, while derived rows in `sections`, `blocks`, `wikilinks`, and
`blocks_fts` are removed. If the path reappears, the indexer treats it as new or
changed, clears the tombstone on success, and rebuilds derived rows.

## Status Interpretation

```powershell
uv run mcp-memory index status C:\path\to\vault
```

Status reports:

- Vault path and index database path.
- Schema and parser versions.
- Last run time and status.
- Total markdown files, indexed files, unindexed files, changed files, deleted
  indexed files, and files with errors.
- Total sections, blocks, and wikilinks.
- Warnings for parser drift and when more than 10% of eligible files have
  indexing errors.

`changed files` is based on file metadata only and does not reparse bodies.
`unindexed files` are eligible markdown files with no active file row.
`deleted indexed files` are active file rows whose vault path is no longer present
on disk.

## Error Inspection

```powershell
uv run mcp-memory index errors C:\path\to\vault
```

Malformed YAML frontmatter is non-fatal: the body is indexed, the run exits with
success-with-errors, and the file keeps its latest error marker until the
frontmatter is fixed and reindexed.

## Debug Search

```powershell
uv run mcp-memory debug search C:\path\to\vault "query" --limit 10
uv run mcp-memory debug search C:\path\to\vault "query" --path wiki/ --tag compliance
uv run mcp-memory debug search C:\path\to\vault "query" --json
```

Debug search reads from `blocks_fts` joined to canonical block/file metadata. It
prints the query match, block key, vault path, section path, heading, BM25 score,
snippet, token estimate, and tags. SQLite FTS5 BM25 scores are ordered with lower
numeric values as better matches, so debug search prints results from lowest
BM25 score to highest. Use it to inspect why a block matched and how FTS ranked
the result.

## Troubleshooting

### Stale Index

Run status. If changed, deleted, unindexed, or parser-drift counts are non-zero,
run incremental indexing. If the numbers remain wrong, run the explicit repair:

```powershell
uv run mcp-memory index --full --yes C:\path\to\vault
```

### Unindexed Files

Confirm the file has a `.md` extension, is under the configured vault root, is not
inside `.git/`, `.obsidian/`, `.trash/`, or `.mcp/`, and is allowed by
`write_constraints.read`.

### Malformed YAML

Run `mcp-memory index errors`. Fix the frontmatter syntax and rerun indexing. The
note body remains searchable while the frontmatter error is present.

### Permission Denied

Check OS file permissions and whether another process has the file locked. The
run continues for other files, but the affected file is counted as failed.

### Database Locked

Close other processes using the index database and rerun the command. The indexer
uses one writer path and WAL mode, but external write locks can still block a run.

### FTS Inconsistency

Run a full repair:

```powershell
uv run mcp-memory index --full --yes C:\path\to\vault
```

The indexer explicitly deletes and inserts FTS rows in the same transaction as
block changes. A full repair recreates derived rows from vault content.

### Parser Drift

Status warns when indexed files were produced by an older parser version. Run
incremental indexing to refresh stale rows.

### Unexpected Query Matches

Use debug search with `--json`, `--path`, and `--tag` to inspect the exact block,
snippet, tags, and BM25 score. Adjust vault content or future retrieval ranking
only after confirming what FTS matched.
