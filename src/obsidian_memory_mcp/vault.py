"""Vault-level domain operations for reading and parsing markdown files."""

from __future__ import annotations

from typing import Any

import yaml


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML frontmatter from a markdown string.

    Returns an empty dict when the content has no frontmatter block,
    the block is malformed YAML, or the parsed result is not a mapping.
    """
    if not content.startswith("---"):
        return {}

    lines = content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}

    closing_index = _find_closing_fence(lines)
    if closing_index < 0:
        return {}

    frontmatter_text = "\n".join(lines[1:closing_index])
    try:
        parsed = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _find_closing_fence(lines: list[str]) -> int:
    """Return the line index of the closing '---' fence, or -1 if absent."""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return -1
