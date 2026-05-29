"""Small text helpers for the indexing parser."""

from __future__ import annotations

import hashlib
import re


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def clean_heading_text(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def section_key(vault_path: str, slug: str, ordinal: int) -> str:
    return f"{vault_path}#{slug}#{ordinal}"


def estimate_markdown_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)
