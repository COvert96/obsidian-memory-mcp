"""CLI handlers for config commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from obsidian_memory_mcp.cli.common import SUBCOMMAND_VALIDATE
from obsidian_memory_mcp.config import ConfigLoader, ConfigValidationException


def handle_config_command(arguments: argparse.Namespace) -> int:
    if arguments.config_command == SUBCOMMAND_VALIDATE:
        return validate_config(arguments.vault_root)
    return 1


def validate_config(vault_root: Path) -> int:
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
