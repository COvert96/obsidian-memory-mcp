"""Alembic environment for obsidian-memory-mcp SQLite migrations."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL

from obsidian_memory_mcp.database._tables import metadata  # type: ignore[import-untyped]

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic uses this metadata for autogenerate comparisons and `alembic check`.
target_metadata = metadata


def _include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    if type_ == "table" and reflected and name is not None and name.startswith(
        "blocks_fts"
    ):
        return False

    # SQLite reflection reports INTEGER/TEXT primary-key columns as nullable unless
    # NOT NULL is explicitly specified. Skip PK nullable-only diffs to keep
    # `alembic check` focused on real schema drift.
    if type_ == "column" and reflected and compare_to is not None:
        reflected_is_primary_key = bool(getattr(object_, "primary_key", False))
        metadata_is_primary_key = bool(getattr(compare_to, "primary_key", False))
        if reflected_is_primary_key and metadata_is_primary_key:
            return False

    return True


def _sqlalchemy_url_for_online_migrations() -> str:
    """Resolve the DB URL for online migrations.

    - CLI usage of `mcp-memory migrate` passes `index_db_location` via
      `Config.attributes`, so migrations run against the configured vault DB.
    - Standalone Alembic CLI usage falls back to `sqlalchemy.url` in `alembic.ini`.
    """
    override = config.attributes.get("index_db_location")
    if override is None:
        configured_url = config.get_main_option("sqlalchemy.url")
        if not configured_url:
            raise RuntimeError("sqlalchemy.url must be set for online migrations.")
        return configured_url
    if isinstance(override, Path):
        database_path = str(override)
    elif isinstance(override, str):
        database_path = override
    else:
        raise TypeError("index_db_location attribute must be a str or Path.")

    return URL.create("sqlite+pysqlite", database=database_path).render_as_string(
        hide_password=False
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url must be set for offline migrations.")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=_include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    section = config.get_section(config.config_ini_section)
    configuration = dict(section) if section is not None else {}
    configuration["sqlalchemy.url"] = _sqlalchemy_url_for_online_migrations()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # SQLite schema changes often require batch mode because SQLite has
        # limited ALTER TABLE support (e.g., no DROP COLUMN in older versions).
        # For migrations that modify columns, prefer:
        # `with op.batch_alter_table("table_name") as batch_op: ...`
        #
        # Alembic autogenerate cannot model FTS5 virtual tables. Always inspect
        # generated revisions and add/update FTS DDL statements manually.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
