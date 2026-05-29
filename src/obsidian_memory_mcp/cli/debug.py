"""CLI handlers for debug commands."""

from __future__ import annotations

import argparse

from obsidian_memory_mcp.cli.common import SUBCOMMAND_SEARCH, load_config
from obsidian_memory_mcp.search_debug import (
    DebugSearchError,
    debug_search,
    search_results_to_json,
)


def handle_debug_command(arguments: argparse.Namespace) -> int:
    if arguments.debug_command == SUBCOMMAND_SEARCH:
        return debug_search_command(arguments)
    return 1


def debug_search_command(arguments: argparse.Namespace) -> int:
    config = load_config(arguments.vault_root)
    if config is None:
        return 3
    try:
        results = debug_search(
            config,
            arguments.query,
            limit=arguments.limit,
            path=arguments.path,
            tag=arguments.tag,
        )
    except DebugSearchError as exc:
        print(exc)
        return 1
    if arguments.json:
        print(search_results_to_json(arguments.query, results))
        return 0
    print(f"Query: {arguments.query}")
    for result in results:
        print(
            f"{result.bm25_score:.4f} {result.block_key} "
            f"path={result.vault_path} section={result.section_path} "
            f"tokens={result.token_count_estimate} tags={','.join(result.tags)}"
        )
        print(f"  {result.snippet}")
    return 0
