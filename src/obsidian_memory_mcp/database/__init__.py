"""Public SQLAlchemy Core database API."""

from obsidian_memory_mcp.database._engine import engine_for, get_connection
from obsidian_memory_mcp.database._tables import metadata

__all__ = ["engine_for", "get_connection", "metadata"]
