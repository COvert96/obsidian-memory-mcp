"""Indexing parser data shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PARSER_VERSION = "phase2-2026-05-24"

TARGET_BLOCK_MIN_TOKENS = 300
TARGET_BLOCK_MAX_TOKENS = 700
HARD_BLOCK_MAX_TOKENS = 1000


@dataclass(frozen=True)
class ParsedHeading:
    level: int
    text: str
    slug: str
    ordinal: int
    section_key: str
    line_number: int


@dataclass(frozen=True)
class ParsedSection:
    vault_path: str
    section_key: str
    section_path: str
    heading: str | None
    heading_slug: str
    heading_ordinal: int
    level: int
    content: str
    content_hash: str
    start_line: int
    end_line: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ParsedBlock:
    vault_path: str
    section_key: str
    section_path: str
    block_key: str
    heading: str | None
    content: str
    content_hash: str
    token_count_estimate: int
    ordinal: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ParsedWikilink:
    vault_path: str
    source_section_key: str
    target: str
    alias: str | None
    raw: str


@dataclass(frozen=True)
class ParsedNote:
    vault_path: str
    frontmatter: dict[str, Any]
    frontmatter_parse_error: str | None
    headings: tuple[ParsedHeading, ...]
    sections: tuple[ParsedSection, ...]
    blocks: tuple[ParsedBlock, ...]
    wikilinks: tuple[ParsedWikilink, ...]
    tags: tuple[str, ...]
    raw_content_hash: str
    normalized_content_hash: str
    parser_version: str


@dataclass(frozen=True)
class HeadingOccurrence:
    level: int
    text: str
    slug: str
    ordinal: int
    section_key: str
    body_line_index: int
    line_number: int
    section_path: str
