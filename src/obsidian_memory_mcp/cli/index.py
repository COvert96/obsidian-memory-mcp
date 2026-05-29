"""CLI handlers for index commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_memory_mcp.cli.common import (
    SUBCOMMAND_ERRORS,
    SUBCOMMAND_STATUS,
    load_config,
)
from obsidian_memory_mcp.indexing import IndexMode, IndexRunResult, run_index
from obsidian_memory_mcp.status import IndexStatus, get_index_status, list_index_errors


def handle_index_command(arguments: argparse.Namespace) -> int:
    if not arguments.index_args:
        print("Missing vault path. See 'mcp-memory index --help'.")
        return 1

    subcommand = _index_subcommand(arguments)
    if subcommand is not None:
        return subcommand

    return _run_index(arguments)


def _index_subcommand(arguments: argparse.Namespace) -> int | None:
    action = arguments.index_args[0]
    if action == SUBCOMMAND_STATUS:
        if len(arguments.index_args) != 2:
            print("Usage: mcp-memory index status {vault_path}")
            return 1
        return index_status(Path(arguments.index_args[1]))
    if action == SUBCOMMAND_ERRORS:
        if len(arguments.index_args) != 2:
            print("Usage: mcp-memory index errors {vault_path}")
            return 1
        return index_errors(Path(arguments.index_args[1]))
    if len(arguments.index_args) != 1:
        print("Usage: mcp-memory index [--full] [--yes] {vault_path}")
        return 1
    return None


def _run_index(arguments: argparse.Namespace) -> int:
    vault_path = Path(arguments.index_args[0])
    if arguments.full and not arguments.yes and not confirm_full_reindex():
        print("Full reindex cancelled.")
        return 1

    config = load_config(vault_path)
    if config is None:
        return 3

    result = run_index(
        config,
        mode=IndexMode.FULL if arguments.full else IndexMode.INCREMENTAL,
    )
    print_index_result(result)
    return exit_code_for_index_result(result)


def index_status(vault_root: Path) -> int:
    config = load_config(vault_root)
    if config is None:
        return 3
    print_status(get_index_status(config))
    return 0


def index_errors(vault_root: Path) -> int:
    config = load_config(vault_root)
    if config is None:
        return 3
    errors = list_index_errors(config)
    if not errors:
        print("No index errors.")
        return 0
    for error in errors:
        path = error.vault_path or "<index>"
        print(
            f"{error.created_at} run={error.run_id} path={path} "
            f"{error.error_type}: {error.message}"
        )
    return 0


def confirm_full_reindex() -> bool:
    response = input("Full reindex rebuilds derived index data. Type YES to continue: ")
    return response == "YES"


def print_index_result(result: IndexRunResult) -> None:
    print(f"Index run {result.index_run_id}: {result.status}")
    print(f"  mode: {result.mode}")
    print(f"  files seen: {result.files_seen}")
    print(f"  files processed: {result.files_processed}")
    print(f"  files skipped: {result.files_skipped}")
    print(f"  files deleted: {result.files_deleted}")
    print(f"  files failed: {result.files_failed}")
    print(f"  sections indexed: {result.sections_indexed}")
    print(f"  blocks indexed: {result.blocks_indexed}")
    print(f"  errors: {result.errors}")
    print(f"  duration ms: {result.duration_ms}")


def print_status(status: IndexStatus) -> None:
    print(f"Vault path: {status.vault_path}")
    print(f"Index DB path: {status.index_db_path}")
    revision = status.schema_revision or "<unmigrated>"
    print(f"Schema revision: {revision}")
    print(f"Parser version: {status.parser_version}")
    print(f"Last run time: {status.last_run_time or '<none>'}")
    print(f"Last run status: {status.last_run_status or '<none>'}")
    print(f"Total markdown files: {status.total_markdown_files}")
    print(f"Indexed files: {status.indexed_files}")
    print(f"Unindexed files: {status.unindexed_files}")
    print(f"Changed files: {status.changed_files}")
    print(f"Deleted indexed files: {status.deleted_indexed_files}")
    print(f"Files with errors: {status.files_with_errors}")
    print(f"Parser version drift: {status.parser_version_drift}")
    print(f"Total sections: {status.total_sections}")
    print(f"Total blocks: {status.total_blocks}")
    print(f"Total wikilinks: {status.total_wikilinks}")
    for warning in status.warnings:
        print(f"WARNING: {warning}")


def exit_code_for_index_result(result: IndexRunResult) -> int:
    if result.status == "failed":
        return 1
    if result.status == "success_with_errors":
        return 2
    return 0
