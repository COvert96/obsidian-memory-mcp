# Migration Guide

Use `mcp-memory migrate` after every version upgrade.

## Upgrading to 0.2.0-rc.1 (from 0.1.x)

1. Check out tag `v0.2.0-rc.1` (or the release branch that contains it).
2. Run `uv sync` so the installed package matches `pyproject.toml` (`0.2.0rc1`).
3. Remove deprecated config keys (for example `proposal_ttl_seconds`) from `memory-mcp.yaml`.
4. Run `mcp-memory migrate` on each vault (see below).
5. Run a full re-index: `mcp-memory index --full --yes {vault}`.

Proposal MCP tools and SQLite proposal tables are removed in 0.2.x. Use direct-write tools documented in [write-tools-guide.md](write-tools-guide.md).

## Command

```bash
mcp-memory migrate [vault_path]
```

If `vault_path` is omitted, the command uses the current working directory.

## Auto-Detect Behavior

`mcp-memory migrate` inspects `sqlite_master` and picks the correct action:

1. No `alembic_version` table and `files` table exists: treats the DB as a v0.1.0 index and runs `alembic upgrade head` (idempotent `CREATE IF NOT EXISTS` DDL).
2. No `alembic_version` table and no `files` table: treats the DB as a fresh install and runs `alembic upgrade head`.
3. `alembic_version` table exists: runs `alembic upgrade head` for incremental migrations.
4. `alembic_version` is already at head but required tables are missing (for example `write_audit`) or proposal tables were never dropped: re-stamps to base and re-runs `upgrade head` to repair the schema.

## Verify Success

Run:

```bash
mcp-memory index status [vault_path]
```

You should see normal index status output with no migration errors.

## Roll Back One Revision

If needed, roll back one migration revision:

```bash
uv run alembic downgrade -1
```

Run this from the project root and ensure `sqlalchemy.url` (or the runtime override)
targets the correct SQLite database before executing the downgrade.
