"""Public SQLAlchemy Core database API."""

from obsidian_memory_mcp.database._engine import (
    connect_index_db,
    engine_for,
    get_connection,
)
from obsidian_memory_mcp.database._tables import (
    blocks,
    files,
    index_errors,
    index_runs,
    metadata,
    sections,
    wikilinks,
    write_audit,
)

__all__ = [
    "blocks",
    "connect_index_db",
    "engine_for",
    "files",
    "get_connection",
    "index_errors",
    "index_runs",
    "metadata",
    "sections",
    "wikilinks",
    "write_audit",
]
