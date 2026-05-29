"""CLI handlers for audit commands."""

from __future__ import annotations

import argparse

from obsidian_memory_mcp.cli.common import (
    SUBCOMMAND_WRITES,
    format_audit_entry,
    load_config,
)
from obsidian_memory_mcp.writes import WriteAuditRepository


def handle_audit_command(arguments: argparse.Namespace) -> int:
    if arguments.audit_command == SUBCOMMAND_WRITES:
        return audit_writes(arguments)
    print("Usage: mcp-memory audit writes [vault_path] ...")
    return 1


def audit_writes(arguments: argparse.Namespace) -> int:
    config = load_config(arguments.vault_root)
    if config is None:
        return 3
    if arguments.limit < 1:
        print("Limit must be a positive integer.")
        return 1

    entries = WriteAuditRepository(config).list(
        project=arguments.project,
        file_path=arguments.file_path,
        limit=arguments.limit,
    )
    if not entries:
        print("No audit entries.")
        return 0

    print("occurred_at\ttool\tproject\tfile_path\toperation\tcontent_hash")
    for entry in entries:
        print(format_audit_entry(entry))
    return 0
