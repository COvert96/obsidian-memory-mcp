"""Shared parsing for YAML frontmatter ``tags`` field values."""

from __future__ import annotations

import re
from typing import Any

_TAG_SPLIT_RE = re.compile(r"[\s,]+")


def tag_values_from_field(value: Any) -> set[str]:
    """Parse a frontmatter ``tags`` value into stripped tag strings (no case folding)."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {
            _strip_tag_prefix(part)
            for part in _TAG_SPLIT_RE.split(value)
            if part.strip()
        }
    if isinstance(value, (list, tuple)):
        return {
            _strip_tag_prefix(str(part))
            for part in value
            if str(part).strip()
        }
    text = str(value).strip()
    if not text:
        return set()
    return {_strip_tag_prefix(text)}


def _strip_tag_prefix(tag: str) -> str:
    return tag.strip().lstrip("#").strip()
