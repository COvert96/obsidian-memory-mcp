"""Public indexing API."""

from obsidian_memory_mcp.indexing._models import (
    FileCandidate,
    IndexMode,
    IndexRunResult,
)
from obsidian_memory_mcp.indexing._discovery import discover_markdown_files
from obsidian_memory_mcp.indexing.parser import (
    PARSER_VERSION,
    ParsedNote,
    parse_markdown,
    parse_markdown_bytes,
)
from obsidian_memory_mcp.indexing.service import run_index

__all__ = [
    "FileCandidate",
    "IndexMode",
    "IndexRunResult",
    "PARSER_VERSION",
    "ParsedNote",
    "discover_markdown_files",
    "parse_markdown",
    "parse_markdown_bytes",
    "run_index",
]
