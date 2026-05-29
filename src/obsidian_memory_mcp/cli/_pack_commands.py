"""Context-pack CLI command implementations."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from obsidian_memory_mcp.utils import duration_ms
from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.cli._pack_output import (
    pack_exit_code,
    pack_issue_summary,
    print_context_pack_summary,
)

ConfigLoaderFn = Callable[[Path], ProjectConfig | None]


def pack_list(vault_root: Path, load_config: ConfigLoaderFn) -> int:
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
        issues = pack_issue_summary(result)
        print(
            f"{pack.name:<20} {len(pack.paths):>8} {len(result.files_included):>6} "
            f"{result.token_count:>7}  {issues:<6} {pack.description or ''}"
        )
        exit_code = max(exit_code, pack_exit_code(result))

    print(f"Duration ms: {duration_ms(started)}")
    return exit_code


def pack_validate(
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

    print_context_pack_summary(result, duration_ms=duration_ms(started))
    if result.tag_filtered_files:
        print("Tag-filtered files:")
        for path in result.tag_filtered_files:
            print(f"  - {path}")
    return pack_exit_code(result)


def pack_load(
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
    print_context_pack_summary(result, duration_ms=duration_ms(started))
    if result.missing_files:
        return 1
    if result.warnings:
        return 2
    return 0
