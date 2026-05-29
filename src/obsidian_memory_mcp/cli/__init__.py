"""Command-line interface for the Obsidian Memory MCP server."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from obsidian_memory_mcp.cli.audit import handle_audit_command
from obsidian_memory_mcp.cli.benchmark import handle_benchmark_command
from obsidian_memory_mcp.cli.common import (
    COMMAND_AUDIT,
    COMMAND_BENCHMARK,
    COMMAND_CONFIG,
    COMMAND_DEBUG,
    COMMAND_INDEX,
    COMMAND_MIGRATE,
    COMMAND_SERVE,
    SUBCOMMAND_SEARCH,
    SUBCOMMAND_VALIDATE,
    load_config,
)
from obsidian_memory_mcp.cli.config import handle_config_command
from obsidian_memory_mcp.cli.debug import handle_debug_command
from obsidian_memory_mcp.cli.index import handle_index_command
from obsidian_memory_mcp.cli.migrate import handle_migrate_command
from obsidian_memory_mcp.cli.pack import COMMAND_PACK, handle_pack_command
from obsidian_memory_mcp.cli.parser import build_argument_parser
from obsidian_memory_mcp.cli.serve import handle_serve_command

CommandHandler = Callable[[argparse.Namespace], int]

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    handler = _resolve_handler(arguments)
    if handler is None:
        parser.print_help()
        return 1
    return handler(arguments)


def _resolve_handler(arguments: argparse.Namespace) -> CommandHandler | None:
    if (
        arguments.command == COMMAND_CONFIG
        and arguments.config_command == SUBCOMMAND_VALIDATE
    ):
        return handle_config_command
    if arguments.command == COMMAND_DEBUG and arguments.debug_command != SUBCOMMAND_SEARCH:
        return None
    routes: dict[str, CommandHandler] = {
        COMMAND_BENCHMARK: handle_benchmark_command,
        COMMAND_INDEX: handle_index_command,
        COMMAND_MIGRATE: handle_migrate_command,
        COMMAND_DEBUG: handle_debug_command,
        COMMAND_AUDIT: handle_audit_command,
        COMMAND_SERVE: handle_serve_command,
    }
    if arguments.command == COMMAND_PACK:
        return _pack_handler
    return routes.get(arguments.command or "")


def _pack_handler(arguments: argparse.Namespace) -> int:
    return handle_pack_command(arguments, load_config)
