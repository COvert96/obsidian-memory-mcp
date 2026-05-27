"""Public indexing API."""

from obsidian_memory_mcp.indexing._models import (
    FileCandidate,
    IndexMode,
    IndexRunResult,
)
from obsidian_memory_mcp.indexing.service import discover_markdown_files, run_index

__all__ = [
    "FileCandidate",
    "IndexMode",
    "IndexRunResult",
    "discover_markdown_files",
    "run_index",
]
