"""YAML frontmatter extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class FrontmatterParseResult:
    frontmatter: dict[str, Any]
    error: str | None
    body: str
    body_start_line: int


def extract_frontmatter(content: str) -> FrontmatterParseResult:
    """Parse an optional YAML frontmatter block and return the remaining body."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return FrontmatterParseResult({}, None, content, 1)

    closing_index = _closing_fence_index(lines)
    if closing_index < 0:
        return FrontmatterParseResult({}, None, content, 1)

    frontmatter_text = "\n".join(lines[1:closing_index])
    try:
        parsed = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as error:
        body = "\n".join(lines[closing_index + 1 :])
        return FrontmatterParseResult(
            {},
            f"frontmatter_parse_error: malformed YAML: {error}",
            body,
            closing_index + 2,
        )

    frontmatter = parsed if isinstance(parsed, dict) else {}
    body = "\n".join(lines[closing_index + 1 :])
    return FrontmatterParseResult(frontmatter, None, body, closing_index + 2)


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Return frontmatter mapping only; errors and non-mappings yield an empty dict."""
    result = extract_frontmatter(content)
    if result.error is not None:
        return {}
    return result.frontmatter


def _closing_fence_index(lines: list[str]) -> int:
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return -1
