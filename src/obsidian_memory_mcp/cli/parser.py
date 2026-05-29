"""Argument parser construction for the mcp-memory CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_memory_mcp.benchmarks import RELEASE_RELEVANCE_THRESHOLD
from obsidian_memory_mcp.cli.common import (
    COMMAND_AUDIT,
    COMMAND_BENCHMARK,
    COMMAND_CONFIG,
    COMMAND_DEBUG,
    COMMAND_INDEX,
    COMMAND_MIGRATE,
    COMMAND_SERVE,
    SUBCOMMAND_PERFORMANCE,
    SUBCOMMAND_RELEVANCE,
    SUBCOMMAND_SEARCH,
    SUBCOMMAND_VALIDATE,
    SUBCOMMAND_WRITES,
)
from obsidian_memory_mcp.cli.pack import add_pack_parser


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-memory")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser(
        COMMAND_CONFIG, help="Manage vault configuration."
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    validate_parser = config_subparsers.add_parser(
        SUBCOMMAND_VALIDATE, help="Validate a vault memory-mcp.yaml."
    )
    validate_parser.add_argument(
        "vault_root", type=Path, help="Path to the Obsidian vault root."
    )

    benchmark_parser = subparsers.add_parser(
        COMMAND_BENCHMARK,
        help="Run deterministic release benchmarks.",
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command")
    relevance_parser = benchmark_subparsers.add_parser(
        SUBCOMMAND_RELEVANCE,
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
        SUBCOMMAND_PERFORMANCE,
        help="Measure fixture-based performance baseline timings.",
    )
    performance_parser.add_argument("vault_root", type=Path)
    performance_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    index_parser = subparsers.add_parser(
        COMMAND_INDEX,
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
        COMMAND_MIGRATE,
        help="Apply Alembic schema migrations for the vault index database.",
        usage="mcp-memory migrate [vault_path]",
        epilog=(
            "Auto-detect cases:\n"
            "  - alembic_version absent and files table present: upgrade head.\n"
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
        COMMAND_DEBUG, help="Run developer diagnostics."
    )
    debug_subparsers = debug_parser.add_subparsers(dest="debug_command")
    search_parser = debug_subparsers.add_parser(
        SUBCOMMAND_SEARCH,
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
        COMMAND_AUDIT,
        help="Inspect the append-only write audit log.",
    )
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command")
    audit_writes = audit_subparsers.add_parser(
        SUBCOMMAND_WRITES,
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

    serve_parser = subparsers.add_parser(COMMAND_SERVE, help="Run the MCP server.")
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
