"""Command-line interface for the Obsidian Memory MCP server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from obsidian_memory_mcp.config import ConfigLoader, ConfigValidationException
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR, load_project_registry

_COMMAND_CONFIG = "config"
_COMMAND_SERVE = "serve"
_SUBCOMMAND_VALIDATE = "validate"


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == _COMMAND_CONFIG and arguments.config_command == _SUBCOMMAND_VALIDATE:
        return _validate_config(arguments.vault_root)
    if arguments.command == _COMMAND_SERVE:
        return _serve(transport=arguments.transport, registry_path=arguments.registry_path)

    parser.print_help()
    return 1


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-memory")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser(_COMMAND_CONFIG, help="Manage vault configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    validate_parser = config_subparsers.add_parser(
        _SUBCOMMAND_VALIDATE, help="Validate a vault memory-mcp.yaml."
    )
    validate_parser.add_argument("vault_root", type=Path, help="Path to the Obsidian vault root.")

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


def _serve(*, transport: str, registry_path: Path | None) -> int:
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

    from obsidian_memory_mcp.server import mcp
    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
