"""Command-line interface for the Obsidian Memory MCP server."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from obsidian_memory_mcp.config import (
    ConfigLoader,
    ConfigValidationException,
    ProjectConfig,
)
from obsidian_memory_mcp.cli_pack import (
    COMMAND_PACK,
    add_pack_parser,
    handle_pack_command,
)
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.indexing import IndexMode, IndexRunResult, run_index
from obsidian_memory_mcp.proposals import ProposalManager, ProposalStatus
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
_COMMAND_PROPOSALS = "proposals"
_COMMAND_SERVE = "serve"
_SUBCOMMAND_APPROVE = "approve"
_SUBCOMMAND_ERRORS = "errors"
_SUBCOMMAND_LIST = "list"
_SUBCOMMAND_REJECT = "reject"
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
    if arguments.command == COMMAND_PACK:
        return handle_pack_command(arguments, _load_config)
    if arguments.command == _COMMAND_PROPOSALS:
        return _proposals(arguments)
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

    add_pack_parser(subparsers)

    proposals_parser = subparsers.add_parser(
        _COMMAND_PROPOSALS,
        help="Review, approve, and reject guarded write proposals.",
    )
    proposal_subparsers = proposals_parser.add_subparsers(dest="proposal_command")
    proposal_list = proposal_subparsers.add_parser(
        _SUBCOMMAND_LIST,
        help="List proposals for a vault.",
        usage="mcp-memory proposals list [vault_path] [--status pending] [--file-path Memory/note.md]",
    )
    proposal_list.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )
    proposal_list.add_argument(
        "--status",
        choices=tuple(status.value for status in ProposalStatus),
        default=ProposalStatus.PENDING.value,
        help="Filter by proposal status.",
    )
    proposal_list.add_argument("--file-path", help="Filter by target vault path.")
    proposal_list.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum proposals to display.",
    )

    proposal_approve = proposal_subparsers.add_parser(
        _SUBCOMMAND_APPROVE,
        help="Approve and apply a pending proposal.",
        usage="mcp-memory proposals approve {proposal_id} [vault_path]",
    )
    proposal_approve.add_argument("proposal_id", help="Proposal ID to approve.")
    proposal_approve.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )

    proposal_reject = proposal_subparsers.add_parser(
        _SUBCOMMAND_REJECT,
        help="Reject a pending proposal without applying it.",
        usage="mcp-memory proposals reject {proposal_id} [vault_path]",
    )
    proposal_reject.add_argument("proposal_id", help="Proposal ID to reject.")
    proposal_reject.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )

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


def _proposals(arguments: argparse.Namespace) -> int:
    if arguments.proposal_command == _SUBCOMMAND_LIST:
        return _proposal_list(arguments)
    if arguments.proposal_command == _SUBCOMMAND_APPROVE:
        return _proposal_approve(arguments)
    if arguments.proposal_command == _SUBCOMMAND_REJECT:
        return _proposal_reject(arguments)

    print("Usage: mcp-memory proposals {list|approve|reject} ...")
    return 1


def _proposal_list(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3
    try:
        proposals = ProposalManager(config).list(
            status=arguments.status,
            file_path=arguments.file_path,
            limit=arguments.limit,
        )
    except ToolExecutionError as exc:
        _print_tool_error("Failed to list proposals", exc)
        return 1

    if not proposals:
        print("No proposals.")
        return 0

    now = _utc_now()
    print("ID\tPath\tOperation\tStatus\tAge")
    for proposal in proposals:
        print(
            f"{proposal.proposal_id}\t{proposal.file_path}\t"
            f"{proposal.operation.value}\t{proposal.status.value}\t"
            f"{_format_age(now, proposal.created_at)}"
        )
    return 0


def _proposal_approve(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3
    manager = ProposalManager(config)
    proposal = manager.get(arguments.proposal_id)
    if proposal is None:
        print(f"Proposal '{arguments.proposal_id}' does not exist.")
        return 1

    print(f"Proposal: {proposal.proposal_id}")
    print(f"Path: {proposal.file_path}")
    print(f"Operation: {proposal.operation.value}")
    print(f"Status: {proposal.status.value}")
    if proposal.content is not None:
        print("Preview:")
        print(proposal.content[:500])

    if proposal.status is not ProposalStatus.PENDING:
        print(f"Cannot approve proposal with status '{proposal.status.value}'.")
        return 1

    response = input("Type YES to apply this proposal: ")
    if response != "YES":
        print("Approval cancelled.")
        return 1

    try:
        result = manager.approve(arguments.proposal_id)
    except ToolExecutionError as exc:
        _print_tool_error("Approval failed", exc)
        return 1

    print(
        f"Applied {result.proposal_id} to {result.file_path} "
        f"({result.file_size_bytes} bytes)."
    )
    return 0


def _proposal_reject(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3
    try:
        result = ProposalManager(config).reject(arguments.proposal_id)
    except ToolExecutionError as exc:
        _print_tool_error("Rejection failed", exc)
        return 1

    print(f"Rejected {result.proposal_id} for {result.file_path}.")
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


def _print_tool_error(prefix: str, exc: ToolExecutionError) -> None:
    print(f"{prefix}: {exc.error.message}")
    suggestion = exc.error.details.get("suggestion")
    if suggestion:
        print(f"  {suggestion}")


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


def _exit_code_for_index_result(result: IndexRunResult) -> int:
    if result.status == "failed":
        return 1
    if result.status == "success_with_errors":
        return 2
    return 0


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _utc_now() -> float:
    return time.time()


def _format_age(now_seconds: float, created_at: datetime) -> str:
    age_seconds = max(0, int(now_seconds - created_at.timestamp()))
    if age_seconds < 60:
        return f"{age_seconds}s"
    if age_seconds < 3600:
        return f"{age_seconds // 60}m"
    if age_seconds < 86400:
        return f"{age_seconds // 3600}h"
    return f"{age_seconds // 86400}d"


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
