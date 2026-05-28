# Migration Guide

Use `mcp-memory migrate` after every version upgrade.

## Command

```bash
mcp-memory migrate [vault_path]
```

If `vault_path` is omitted, the command uses the current working directory.

## Auto-Detect Behavior

`mcp-memory migrate` inspects `sqlite_master` and picks the correct action:

1. No `alembic_version` table and `files` table exists: treats the DB as a v0.1.0 schema and runs `alembic stamp head`.
2. No `alembic_version` table and no `files` table: treats the DB as a fresh install and runs `alembic upgrade head`.
3. `alembic_version` table exists: runs `alembic upgrade head` for incremental migrations.

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
