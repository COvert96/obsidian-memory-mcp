#!/usr/bin/env python3
"""Validate that a markdown file has parseable YAML frontmatter.

Illustrative helper for memory-capture skill drafts. Does not call the MCP server.
"""

from __future__ import annotations

import sys
from pathlib import Path

from obsidian_memory_mcp.markdown import extract_frontmatter


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: validate-note.py <markdown-path>", file=sys.stderr)
        return 2

    path = Path(args[0])
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1

    result = extract_frontmatter(path.read_text(encoding="utf-8"))
    if result.error is not None:
        print(result.error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
