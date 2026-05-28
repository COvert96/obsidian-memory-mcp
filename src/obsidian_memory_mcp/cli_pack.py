"""CLI handlers for context-pack commands."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from obsidian_memory_mcp._time import duration_ms
from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.context_packs import ContextPackLoader, ContextPackResult
from obsidian_memory_mcp.errors import ToolExecutionError

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
        return _pack_list(arguments.vault_root, load_config)
    if arguments.pack_command == SUBCOMMAND_VALIDATE:
        return _pack_validate(arguments.vault_root, arguments.pack_name, load_config)
    if arguments.pack_command == SUBCOMMAND_LOAD:
        return _pack_load(
            arguments.vault_root,
            arguments.pack_name,
            strict_budget=arguments.strict_budget,
            load_config=load_config,
        )
    print("Usage: mcp-memory pack {list|validate|load} ...")
    return 1


def _pack_list(vault_root: Path, load_config: ConfigLoaderFn) -> int:
    started = time.perf_counter()
    config = load_config(vault_root)
    if config is None:
        return 1

    loader = ContextPackLoader(config)
    exit_code = 0
    print("Name                 Patterns  Files  Tokens  Issues  Description")
    for pack in config.context_packs:
        try:
            result = loader.inspect(pack.name)
        except ToolExecutionError as exc:
            print(f"{pack.name:<20} <error> {exc.error.message}")
            exit_code = 1
            continue
        issues = _pack_issue_summary(result)
        print(
            f"{pack.name:<20} {len(pack.paths):>8} {len(result.files_included):>6} "
            f"{result.token_count:>7}  {issues:<6} {pack.description or ''}"
        )
        exit_code = max(exit_code, _pack_exit_code(result))

    print(f"Duration ms: {duration_ms(started)}")
    return exit_code


def _pack_validate(
    vault_root: Path,
    pack_name: str,
    load_config: ConfigLoaderFn,
) -> int:
    started = time.perf_counter()
    config = load_config(vault_root)
    if config is None:
        return 1

    try:
        result = ContextPackLoader(config).inspect(pack_name)
    except ToolExecutionError as exc:
        print(f"Context pack validation failed: {exc.error.message}")
        suggestion = exc.error.details.get("suggestion")
        if suggestion:
            print(f"  {suggestion}")
        return 1

    _print_context_pack_summary(result, duration_ms=duration_ms(started))
    if result.tag_filtered_files:
        print("Tag-filtered files:")
        for path in result.tag_filtered_files:
            print(f"  - {path}")
    return _pack_exit_code(result)


def _pack_load(
    vault_root: Path,
    pack_name: str,
    *,
    strict_budget: bool,
    load_config: ConfigLoaderFn,
) -> int:
    started = time.perf_counter()
    config = load_config(vault_root)
    if config is None:
        return 1

    try:
        result = ContextPackLoader(config).load(
            pack_name,
            strict_budget=strict_budget,
        )
    except ToolExecutionError as exc:
        print(f"Context pack load failed: {exc.error.message}")
        for key in ("current_token_count", "budget", "excess_tokens", "suggestion"):
            if key in exc.error.details:
                print(f"  {key}: {exc.error.details[key]}")
        return 1

    print(result.content, end="" if result.content.endswith("\n") else "\n")
    _print_context_pack_summary(result, duration_ms=duration_ms(started))
    if result.missing_files:
        return 1
    if result.warnings:
        return 2
    return 0


def _print_context_pack_summary(
    result: ContextPackResult,
    *,
    duration_ms: int,
) -> None:
    print("Files included:")
    for path in result.files_included:
        print(f"  - {path}")
    print(f"Token count: {result.token_count}")
    print("Missing files:")
    if result.missing_files:
        for path in result.missing_files:
            print(f"  - {path}")
    else:
        print("  <none>")
    print("Warnings:")
    if result.warnings:
        for warning in result.warnings:
            print(f"  - {warning}")
    else:
        print("  <none>")
    print(f"Duration ms: {duration_ms}")


def _pack_issue_summary(result: ContextPackResult) -> str:
    issues: list[str] = []
    if result.missing_files:
        issues.append(f"{len(result.missing_files)} missing")
    if result.warnings:
        issues.append(f"{len(result.warnings)} warnings")
    if result.token_count > result.budget:
        issues.append("over budget")
    elif result.token_count > result.budget * 0.9:
        issues.append("near budget")
    return ", ".join(issues) or "none"


def _pack_exit_code(result: ContextPackResult) -> int:
    if result.missing_files:
        return 1
    if (
        result.warnings
        or result.token_count > result.budget
        or result.token_count > result.budget * 0.9
    ):
        return 2
    return 0
