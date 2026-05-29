"""CLI handler for the MCP serve command."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from obsidian_memory_mcp.cli.common import Transport
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import (
    SERVER_REGISTRY_ENV_VAR,
    load_project_registry,
)


def handle_serve_command(arguments: argparse.Namespace) -> int:
    return serve(
        transport=arguments.transport,
        registry_path=arguments.registry_path,
    )


def serve(*, transport: Transport, registry_path: Path | None) -> int:
    if registry_path is not None:
        os.environ[SERVER_REGISTRY_ENV_VAR] = str(registry_path)

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
