"""CLI handlers for context-pack commands."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.cli._pack_commands import pack_list, pack_load, pack_validate

COMMAND_PACK = "pack"
SUBCOMMAND_LIST = "list"
SUBCOMMAND_LOAD = "load"
SUBCOMMAND_VALIDATE = "validate"
ConfigLoaderFn = Callable[[Path], ProjectConfig | None]


def add_pack_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    pack_parser = subparsers.add_parser(
        COMMAND_PACK,
        help="List, validate, and load configured context packs.",
    )
    pack_subparsers = pack_parser.add_subparsers(dest="pack_command")

    pack_list_parser = pack_subparsers.add_parser(
        SUBCOMMAND_LIST,
        help="List configured context packs and known issues.",
    )
    pack_list_parser.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )

    pack_validate_parser = pack_subparsers.add_parser(
        SUBCOMMAND_VALIDATE,
        help="Validate one configured context pack.",
    )
    pack_validate_parser.add_argument(
        "pack_name", help="Context pack name to validate."
    )
    pack_validate_parser.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )

    pack_load_parser = pack_subparsers.add_parser(
        SUBCOMMAND_LOAD,
        help="Print one context pack's concatenated content.",
    )
    pack_load_parser.add_argument("pack_name", help="Context pack name to load.")
    pack_load_parser.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )
    pack_load_parser.add_argument(
        "--no-strict-budget",
        action="store_false",
        dest="strict_budget",
        help="Truncate over-budget packs instead of returning an error.",
    )
    pack_load_parser.set_defaults(strict_budget=True)


def handle_pack_command(
    arguments: argparse.Namespace,
    load_config: ConfigLoaderFn,
) -> int:
    if arguments.pack_command == SUBCOMMAND_LIST:
        return pack_list(arguments.vault_root, load_config)
    if arguments.pack_command == SUBCOMMAND_VALIDATE:
        return pack_validate(arguments.vault_root, arguments.pack_name, load_config)
    if arguments.pack_command == SUBCOMMAND_LOAD:
        return pack_load(
            arguments.vault_root,
            arguments.pack_name,
            strict_budget=arguments.strict_budget,
            load_config=load_config,
        )
    print("Usage: mcp-memory pack {list|validate|load} ...")
    return 1
