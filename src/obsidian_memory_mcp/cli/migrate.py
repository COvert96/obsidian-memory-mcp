"""CLI handlers for migrate commands."""

from __future__ import annotations

import argparse

from obsidian_memory_mcp.cli.common import load_config
from obsidian_memory_mcp.migrations import MigrationError, migrate_index_database


def handle_migrate_command(arguments: argparse.Namespace) -> int:
    config = load_config(arguments.vault_root)
    if config is None:
        return 3

    try:
        result = migrate_index_database(config.index_db_location)
    except MigrationError as exc:
        print(f"Migration failed: {exc}")
        return 1

    if result.applied_migration_count == 0:
        print("Already at head.")
        return 0

    print(f"Applied {result.applied_migration_count} migration(s).")
    return 0
