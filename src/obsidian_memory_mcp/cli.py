"""Command-line interface for the Obsidian Memory MCP server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Literal

from obsidian_memory_mcp.config import (
    ConfigLoader,
    ConfigValidationException,
    ProjectConfig,
)
from obsidian_memory_mcp.benchmarks import (
    RELEASE_RELEVANCE_THRESHOLD,
    evaluate_relevance_benchmark,
    measure_performance_baseline,
    report_as_json,
)
from obsidian_memory_mcp.cli_pack import (
    COMMAND_PACK,
    add_pack_parser,
    handle_pack_command,
)
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.indexing import IndexMode, IndexRunResult, run_index
from obsidian_memory_mcp.migrations import MigrationError, migrate_index_database
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
from obsidian_memory_mcp.writes import WriteAuditRepository
from obsidian_memory_mcp.writes._models import WriteAuditEntry

_COMMAND_AUDIT = "audit"
_COMMAND_CONFIG = "config"
_COMMAND_BENCHMARK = "benchmark"
_COMMAND_DEBUG = "debug"
_COMMAND_INDEX = "index"
_COMMAND_MIGRATE = "migrate"
_COMMAND_SERVE = "serve"
_SUBCOMMAND_ERRORS = "errors"
_SUBCOMMAND_SEARCH = "search"
_SUBCOMMAND_STATUS = "status"
_SUBCOMMAND_VALIDATE = "validate"
_SUBCOMMAND_RELEVANCE = "relevance"
_SUBCOMMAND_PERFORMANCE = "performance"
_SUBCOMMAND_WRITES = "writes"
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
    if arguments.command == _COMMAND_BENCHMARK:
        return _benchmark(arguments)
    if arguments.command == _COMMAND_INDEX:
        return _index(arguments)
    if arguments.command == _COMMAND_MIGRATE:
        return _migrate(arguments)
    if (
        arguments.command == _COMMAND_DEBUG
        and arguments.debug_command == _SUBCOMMAND_SEARCH
    ):
        return _debug_search(arguments)
    if arguments.command == COMMAND_PACK:
        return handle_pack_command(arguments, _load_config)
    if arguments.command == _COMMAND_AUDIT:
        return _audit(arguments)
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

    benchmark_parser = subparsers.add_parser(
        _COMMAND_BENCHMARK,
        help="Run deterministic release benchmarks.",
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command")
    relevance_parser = benchmark_subparsers.add_parser(
        _SUBCOMMAND_RELEVANCE,
        help="Measure top-k search relevance against benchmark queries.",
        usage=(
            "mcp-memory benchmark relevance {vault_path} "
            "[--queries tests/benchmarks/benchmark-queries.yaml]"
        ),
    )
    relevance_parser.add_argument("vault_root", type=Path)
    relevance_parser.add_argument(
        "--queries",
        type=Path,
        default=Path("tests/benchmarks/benchmark-queries.yaml"),
        help="Benchmark query YAML file.",
    )
    relevance_parser.add_argument("--top-k", type=int, default=3)
    relevance_parser.add_argument(
        "--min-accuracy",
        type=float,
        default=RELEASE_RELEVANCE_THRESHOLD,
        help="Minimum passing top-k accuracy.",
    )
    relevance_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    performance_parser = benchmark_subparsers.add_parser(
        _SUBCOMMAND_PERFORMANCE,
        help="Measure fixture-based performance baseline timings.",
    )
    performance_parser.add_argument("vault_root", type=Path)
    performance_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
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

    migrate_parser = subparsers.add_parser(
        _COMMAND_MIGRATE,
        help="Apply Alembic schema migrations for the vault index database.",
        usage="mcp-memory migrate [vault_path]",
        epilog=(
            "Auto-detect cases:\n"
            "  - alembic_version absent and files table present: stamp head.\n"
            "  - alembic_version absent and files table absent: upgrade head.\n"
            "  - alembic_version table present: upgrade head (pending only)."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    migrate_parser.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
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

    audit_parser = subparsers.add_parser(
        _COMMAND_AUDIT,
        help="Inspect the append-only write audit log.",
    )
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command")
    audit_writes = audit_subparsers.add_parser(
        _SUBCOMMAND_WRITES,
        help="List write_audit entries for a vault.",
        usage=(
            "mcp-memory audit writes [vault_path] "
            "[--project NAME] [--file-path PATH] [--limit 50]"
        ),
    )
    audit_writes.add_argument(
        "vault_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to the Obsidian vault root (default: current directory).",
    )
    audit_writes.add_argument("--project", help="Filter by project name.")
    audit_writes.add_argument("--file-path", help="Filter by target vault path.")
    audit_writes.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum audit entries to display.",
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


def _benchmark(arguments: argparse.Namespace) -> int:
    if arguments.benchmark_command == _SUBCOMMAND_RELEVANCE:
        return _benchmark_relevance(arguments)
    if arguments.benchmark_command == _SUBCOMMAND_PERFORMANCE:
        return _benchmark_performance(arguments)
    print("Usage: mcp-memory benchmark {relevance|performance} ...")
    return 1


def _benchmark_relevance(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3
    report = evaluate_relevance_benchmark(
        config,
        arguments.queries,
        top_k=arguments.top_k,
    )
    print(report_as_json(report) if arguments.json else report.as_text())
    return 0 if report.accuracy >= arguments.min_accuracy else 1


def _benchmark_performance(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3
    baseline = measure_performance_baseline(config)
    print(report_as_json(baseline) if arguments.json else baseline.as_text())
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


def _migrate(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
    if config is None:
        return 3

    try:
        result = migrate_index_database(config.index_db_location)
    except MigrationError as exc:
        print(f"Migration failed: {exc}")
        return 1

    if result.stamped_existing_schema:
        print("Stamped existing schema as current version.")
        return 0

    if result.applied_migration_count == 0:
        print("Already at head.")
        return 0

    print(f"Applied {result.applied_migration_count} migration(s).")
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


def _audit(arguments: argparse.Namespace) -> int:
    if arguments.audit_command == _SUBCOMMAND_WRITES:
        return _audit_writes(arguments)
    print("Usage: mcp-memory audit writes [vault_path] ...")
    return 1


def _audit_writes(arguments: argparse.Namespace) -> int:
    config = _load_config(arguments.vault_root)
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
        print(_format_audit_entry(entry))
    return 0


def _format_audit_entry(entry: WriteAuditEntry) -> str:
    content_hash = (entry.content_hash or "")[:12]
    return (
        f"{entry.occurred_at.isoformat()}\t{entry.tool}\t{entry.project}\t"
        f"{entry.file_path}\t{entry.operation}\t{content_hash}"
    )


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


def _exit_code_for_index_result(result: IndexRunResult) -> int:
    if result.status == "failed":
        return 1
    if result.status == "success_with_errors":
        return 2
    return 0


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
