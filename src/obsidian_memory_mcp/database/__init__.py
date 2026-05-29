"""Public SQLAlchemy Core database API."""

from obsidian_memory_mcp.database._engine import (
    connect_index_db,
    engine_for,
    get_connection,
)
from obsidian_memory_mcp.database._tables import metadata

__all__ = ["connect_index_db", "engine_for", "get_connection", "metadata"]
