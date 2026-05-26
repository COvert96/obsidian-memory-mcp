"""Command-line interface for the Obsidian Memory MCP server."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Literal

from obsidian_memory_mcp.config import (
    ConfigLoader,
    ConfigValidationException,
    ProjectConfig,
)
from obsidian_memory_mcp.context_packs import ContextPackLoader, ContextPackResult
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.indexer import IndexMode, IndexRunResult, run_index
from obsidian_memory_mcp.search_debug import (
    DebugSearchError,
    debug_search,
    search_results_to_json,
)
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import (
    SERVER_REGISTRY_ENV_VAR,
    load_project_registry,
)
from obsidian_memory_mcp.status import IndexStatus, get_index_status, list_index_errors

_COMMAND_CONFIG = "config"
_COMMAND_DEBUG = "debug"
_COMMAND_INDEX = "index"
_COMMAND_PACK = "pack"
_COMMAND_SERVE = "serve"
_SUBCOMMAND_ERRORS = "errors"
_SUBCOMMAND_LIST = "list"
_SUBCOMMAND_LOAD = "load"
_SUBCOMMAND_SEARCH = "search"
_SUBCOMMAND_STATUS = "status"
_SUBCOMMAND_VALIDATE = "validate"
Transport = Literal["stdio", "sse", "streamable-http"]


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if (
        arguments.command == _COMMAND_CONFIG
        and arguments.config_command == _SUBCOMMAND_VALIDATE
    ):
        return _validate_config(arguments.vault_root)
    if arguments.command == _COMMAND_INDEX:
        return _index(arguments)
    if (
        arguments.command == _COMMAND_DEBUG
        and arguments.debug_command == _SUBCOMMAND_SEARCH
    ):
        return _debug_search(arguments)
    if arguments.command == _COMMAND_PACK:
        return _pack(arguments)
    if arguments.command == _COMMAND_SERVE:
        return _serve(
            transport=arguments.transport, registry_path=arguments.registry_path
        )

    parser.print_help()
    return 1


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-memory")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser(
        _COMMAND_CONFIG, help="Manage vault configuration."
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    validate_parser = config_subparsers.add_parser(
        _SUBCOMMAND_VALIDATE, help="Validate a vault memory-mcp.yaml."
    )
    validate_parser.add_argument(
        "vault_root", type=Path, help="Path to the Obsidian vault root."
    )

    index_parser = subparsers.add_parser(
        _COMMAND_INDEX,
        help="Build, repair, and inspect the markdown index.",
        usage=(
            "mcp-memory index [--full] [--yes] {vault_path} | "
            "mcp-memory index status {vault_path} | "
            "mcp-memory index errors {vault_path}"
        ),
    )
    index_parser.add_argument("--full", action="store_true", help="Run a full reindex.")
    index_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm full reindex repair without an interactive prompt.",
    )
    index_parser.add_argument(
        "index_args",
        nargs="*",
        help="Vault path, or one of: status {vault_path}, errors {vault_path}.",
    )

    debug_parser = subparsers.add_parser(
        _COMMAND_DEBUG, help="Run developer diagnostics."
    )
    debug_subparsers = debug_parser.add_subparsers(dest="debug_command")
    search_parser = debug_subparsers.add_parser(
        _SUBCOMMAND_SEARCH,
        help="Inspect FTS search ranking and snippets.",
        usage=(
            'mcp-memory debug search {vault_path} "{query}" '
            "[--limit 10] [--path wiki/] [--tag tag] [--json]"
        ),
    )
    search_parser.add_argument(
        "vault_root", type=Path, help="Path to the Obsidian vault root."
    )
    search_parser.add_argument("query", help="FTS query to inspect.")
    search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results to return."
    )
    search_parser.add_argument(
        "--path", help="Restrict results to a vault-relative path prefix."
    )
    search_parser.add_argument("--tag", help="Restrict results to blocks with the tag.")
    search_parser.add_argument(
        "--json", action="store_true", help="Emit structured JSON output."
    )

    pack_parser = subparsers.add_parser(
        _COMMAND_PACK,
        help="List, validate, and load configured context packs.",
    )
    pack_subparsers = pack_parser.add_subparsers(dest="pack_command")

    pack_list_parser = pack_subparsers.add_parser(
        _SUBCOMMAND_LIST,
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
        _SUBCOMMAND_VALIDATE,
        help="Validate one configured context pack.",
    )
    pack_validate_parser.add_argument("pack_name", help="Context pack name to validate.")
    pack_validate_parser.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )

    pack_load_parser = pack_subparsers.add_parser(
        _SUBCOMMAND_LOAD,
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

    serve_parser = subparsers.add_parser(_COMMAND_SERVE, help="Run the MCP server.")
    serve_parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport to use (default: stdio).",
    )
    serve_parser.add_argument(
        "--registry-path",
        type=Path,
        default=None,
        help="Path to the server registry file (default: memory-mcp-server.yaml).",
    )

    return parser


def _validate_config(vault_root: Path) -> int:
    try:
        config = ConfigLoader(vault_root).load()
    except ConfigValidationException as exc:
        print(f"Config is invalid: {exc.error.message}")
        for error in exc.validation_errors:
            print(f"  - {error.message}")
        if not exc.validation_errors and exc.error.details.get("suggestion"):
            print(f"  - {exc.error.details['suggestion']}")
        return 1

    print(f"Config is valid: {config.vault_path}")
    return 0


def _index(arguments: argparse.Namespace) -> int:
    if not arguments.index_args:
        print("Missing vault path. See 'mcp-memory index --help'.")
        return 1

    action = arguments.index_args[0]
    if action == _SUBCOMMAND_STATUS:
        if len(arguments.index_args) != 2:
            print("Usage: mcp-memory index status {vault_path}")
            return 1
        return _index_status(Path(arguments.index_args[1]))
    if action == _SUBCOMMAND_ERRORS:
        if len(arguments.index_args) != 2:
            print("Usage: mcp-memory index errors {vault_path}")
            return 1
        return _index_errors(Path(arguments.index_args[1]))
    if len(arguments.index_args) != 1:
        print("Usage: mcp-memory index [--full] [--yes] {vault_path}")
        return 1
    if arguments.full and not arguments.yes and not _confirm_full_reindex():
        print("Full reindex cancelled.")
        return 1

    config = _load_config(Path(action))
    if config is None:
        return 3

    result = run_index(
        config,
        mode=IndexMode.FULL if arguments.full else IndexMode.INCREMENTAL,
    )
    _print_index_result(result)
    return _exit_code_for_index_result(result)


def _index_status(vault_root: Path) -> int:
    config = _load_config(vault_root)
    if config is None:
        return 3
    status = get_index_status(config)
    _print_status(status)
    return 0


def _index_errors(vault_root: Path) -> int:
    config = _load_config(vault_root)
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


def _debug_search(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
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


def _pack(arguments: argparse.Namespace) -> int:
    if arguments.pack_command == _SUBCOMMAND_LIST:
        return _pack_list(arguments.vault_root)
    if arguments.pack_command == _SUBCOMMAND_VALIDATE:
        return _pack_validate(arguments.vault_root, arguments.pack_name)
    if arguments.pack_command == _SUBCOMMAND_LOAD:
        return _pack_load(
            arguments.vault_root,
            arguments.pack_name,
            strict_budget=arguments.strict_budget,
        )
    print("Usage: mcp-memory pack {list|validate|load} ...")
    return 1


def _pack_list(vault_root: Path) -> int:
    started = time.perf_counter()
    config = _load_config(vault_root)
    if config is None:
        return 1

    loader = ContextPackLoader(config)
    results: list[ContextPackResult] = []
    exit_code = 0
    print("Name                 Patterns  Files  Tokens  Issues  Description")
    for pack in config.context_packs:
        try:
            result = loader.inspect(pack.name)
        except ToolExecutionError as exc:
            print(f"{pack.name:<20} <error> {exc.error.message}")
            exit_code = 1
            continue
        results.append(result)
        issues = _pack_issue_summary(result)
        print(
            f"{pack.name:<20} {len(pack.paths):>8} {len(result.files_included):>6} "
            f"{result.token_count:>7}  {issues:<6} {pack.description or ''}"
        )
        exit_code = max(exit_code, _pack_exit_code(result))

    print(f"Duration ms: {_duration_ms(started)}")
    return exit_code


def _pack_validate(vault_root: Path, pack_name: str) -> int:
    started = time.perf_counter()
    config = _load_config(vault_root)
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

    _print_context_pack_summary(result, duration_ms=_duration_ms(started))
    if result.tag_filtered_files:
        print("Tag-filtered files:")
        for path in result.tag_filtered_files:
            print(f"  - {path}")
    return _pack_exit_code(result)


def _pack_load(vault_root: Path, pack_name: str, *, strict_budget: bool) -> int:
    started = time.perf_counter()
    config = _load_config(vault_root)
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
    _print_context_pack_summary(result, duration_ms=_duration_ms(started))
    if result.missing_files:
        return 1
    if result.warnings:
        return 2
    return 0


def _load_config(vault_root: Path) -> ProjectConfig | None:
    try:
        return ConfigLoader(vault_root).load()
    except ConfigValidationException as exc:
        print(f"Config is invalid: {exc.error.message}")
        for error in exc.validation_errors:
            print(f"  - {error.message}")
        if not exc.validation_errors and exc.error.details.get("suggestion"):
            print(f"  - {exc.error.details['suggestion']}")
        return None
    except ToolExecutionError as exc:
        print(f"Guardrail violation: {exc.error.message}")
        suggestion = exc.error.details.get("suggestion")
        if suggestion:
            print(f"  {suggestion}")
        return None


def _confirm_full_reindex() -> bool:
    response = input("Full reindex rebuilds derived index data. Type YES to continue: ")
    return response == "YES"


def _print_index_result(result: IndexRunResult) -> None:
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


def _print_status(status: IndexStatus) -> None:
    print(f"Vault path: {status.vault_path}")
    print(f"Index DB path: {status.index_db_path}")
    print(f"Schema version: {status.schema_version}")
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


def _exit_code_for_index_result(result: IndexRunResult) -> int:
    if result.status == "failed":
        return 1
    if result.status == "success_with_errors":
        return 2
    return 0


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _serve(*, transport: Transport, registry_path: Path | None) -> int:
    if registry_path is not None:
        os.environ[SERVER_REGISTRY_ENV_VAR] = str(registry_path)

    # Validate the registry eagerly so a bad config fails at startup, not mid-request.
    try:
        load_project_registry()
    except ToolExecutionError as exc:
        print(f"Failed to start server: {exc.error.message}")
        suggestion = exc.error.details.get("suggestion")
        if suggestion:
            print(f"  {suggestion}")
        return 1

    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
