from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_memory_mcp.config import ConfigLoader, ConfigValidationException


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "config" and arguments.config_command == "validate":
        return _validate_config(arguments.vault_root)

    parser.print_help()
    return 1


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-memory")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Manage vault project configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    validate_parser = config_subparsers.add_parser("validate", help="Validate a vault memory-mcp.yaml.")
    validate_parser.add_argument("vault_root", type=Path, help="Path to the Obsidian vault root.")

    return parser


def _validate_config(vault_root: Path) -> int:
    try:
        config = ConfigLoader(vault_root).load()
    except ConfigValidationException as error:
        print(f"Config is invalid: {error.error.message}")
        for validation_error in error.validation_errors:
            print(f"- {validation_error.message}")
        if not error.validation_errors and error.error.details.get("suggestion"):
            print(f"- {error.error.details['suggestion']}")
        return 1

    print(f"Config is valid: {config.vault_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
