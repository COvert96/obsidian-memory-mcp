"""Shared CLI helpers and command name constants."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from obsidian_memory_mcp.config import (
    ConfigLoader,
    ConfigValidationException,
    ProjectConfig,
)
from obsidian_memory_mcp.errors import ToolExecutionError
from obsidian_memory_mcp.writes import WriteAuditEntry

COMMAND_AUDIT = "audit"
COMMAND_BENCHMARK = "benchmark"
COMMAND_CONFIG = "config"
COMMAND_DEBUG = "debug"
COMMAND_INDEX = "index"
COMMAND_MIGRATE = "migrate"
COMMAND_SERVE = "serve"
SUBCOMMAND_ERRORS = "errors"
SUBCOMMAND_PERFORMANCE = "performance"
SUBCOMMAND_RELEVANCE = "relevance"
SUBCOMMAND_SEARCH = "search"
SUBCOMMAND_STATUS = "status"
SUBCOMMAND_VALIDATE = "validate"
SUBCOMMAND_WRITES = "writes"
Transport = Literal["stdio", "sse", "streamable-http"]


def load_config(vault_root: Path) -> ProjectConfig | None:
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


def format_audit_entry(entry: WriteAuditEntry) -> str:
    content_hash = (entry.content_hash or "")[:12]
    return (
        f"{entry.occurred_at.isoformat()}\t{entry.tool}\t{entry.project}\t"
        f"{entry.file_path}\t{entry.operation}\t{content_hash}"
    )
