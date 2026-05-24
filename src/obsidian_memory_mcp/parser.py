"""Markdown parsing policy for deterministic vault indexing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import yaml

PARSER_VERSION = "phase2-2026-05-24"

TARGET_BLOCK_MIN_TOKENS = 300
TARGET_BLOCK_MAX_TOKENS = 700
HARD_BLOCK_MAX_TOKENS = 1000

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MARKDOWN_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9][A-Za-z0-9_/-]*)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


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
class _HeadingOccurrence:
    level: int
    text: str
    slug: str
    ordinal: int
    section_key: str
    body_line_index: int
    line_number: int
    section_path: str


@dataclass(frozen=True)
class _FenceState:
    marker: str
    length: int


def parse_markdown(
    *,
    vault_path: str,
    content: str | bytes,
    parser_version: str = PARSER_VERSION,
) -> ParsedNote:
    """Parse a markdown note into deterministic indexing structures."""

    raw_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
    text = raw_bytes.decode("utf-8")
    normalized_text = _normalize_newlines(text)
    frontmatter, frontmatter_error, body, body_start_line = _extract_frontmatter(normalized_text)
    body_lines = body.split("\n")
    note_tags = _extract_tags(frontmatter, body_lines)
    headings = _find_headings(vault_path, body_lines, body_start_line)
    sections = _build_sections(vault_path, body_lines, body_start_line, headings, note_tags)
    blocks = tuple(
        block
        for section in sections
        for block in _build_blocks(section)
    )
    wikilinks = tuple(
        link
        for section in sections
        for link in _extract_wikilinks(vault_path, section)
    )

    return ParsedNote(
        vault_path=vault_path,
        frontmatter=frontmatter,
        frontmatter_parse_error=frontmatter_error,
        headings=tuple(
            ParsedHeading(
                level=heading.level,
                text=heading.text,
                slug=heading.slug,
                ordinal=heading.ordinal,
                section_key=heading.section_key,
                line_number=heading.line_number,
            )
            for heading in headings
        ),
        sections=sections,
        blocks=blocks,
        wikilinks=wikilinks,
        tags=note_tags,
        raw_content_hash=_sha256(raw_bytes),
        normalized_content_hash=_sha256(normalized_text.encode("utf-8")),
        parser_version=parser_version,
    )


def parse_markdown_bytes(
    *,
    vault_path: str,
    content: bytes,
    parser_version: str = PARSER_VERSION,
) -> ParsedNote:
    return parse_markdown(vault_path=vault_path, content=content, parser_version=parser_version)


def estimate_markdown_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str | None, str, int]:
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, None, content, 1

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        -1,
    )
    if closing_index < 0:
        return {}, None, content, 1

    frontmatter_text = "\n".join(lines[1:closing_index])
    try:
        parsed = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as error:
        body = "\n".join(lines[closing_index + 1 :])
        return {}, f"frontmatter_parse_error: malformed YAML: {error}", body, closing_index + 2

    frontmatter = parsed if isinstance(parsed, dict) else {}
    body = "\n".join(lines[closing_index + 1 :])
    return frontmatter, None, body, closing_index + 2


def _find_headings(
    vault_path: str,
    body_lines: list[str],
    body_start_line: int,
) -> tuple[_HeadingOccurrence, ...]:
    headings: list[_HeadingOccurrence] = []
    slug_counts: dict[str, int] = {}
    heading_stack: list[tuple[int, str]] = []
    fence_state: _FenceState | None = None

    for index, line in enumerate(body_lines):
        fence_state = _next_fence_state(line, fence_state)
        if fence_state is not None and _is_fence_line(line):
            continue
        if fence_state is not None:
            continue

        match = _HEADING_RE.match(line)
        if match is None:
            continue

        level = len(match.group(1))
        text = _clean_heading_text(match.group(2))
        slug = _slugify(text)
        ordinal = slug_counts.get(slug, 0) + 1
        slug_counts[slug] = ordinal
        section_key = _section_key(vault_path, slug, ordinal)
        heading_stack = [item for item in heading_stack if item[0] < level]
        heading_stack.append((level, text))
        headings.append(
            _HeadingOccurrence(
                level=level,
                text=text,
                slug=slug,
                ordinal=ordinal,
                section_key=section_key,
                body_line_index=index,
                line_number=body_start_line + index,
                section_path=" > ".join(item[1] for item in heading_stack),
            )
        )

    return tuple(headings)


def _build_sections(
    vault_path: str,
    body_lines: list[str],
    body_start_line: int,
    headings: tuple[_HeadingOccurrence, ...],
    tags: tuple[str, ...],
) -> tuple[ParsedSection, ...]:
    if not headings:
        return (
            _section(
                vault_path=vault_path,
                heading=None,
                slug="root",
                ordinal=1,
                level=0,
                section_path="root",
                content="\n".join(body_lines),
                start_line=body_start_line,
                end_line=body_start_line + max(len(body_lines) - 1, 0),
                tags=tags,
            ),
        )

    sections: list[ParsedSection] = []
    first_heading_index = headings[0].body_line_index
    if "\n".join(body_lines[:first_heading_index]).strip():
        sections.append(
            _section(
                vault_path=vault_path,
                heading=None,
                slug="root",
                ordinal=1,
                level=0,
                section_path="root",
                content="\n".join(body_lines[:first_heading_index]),
                start_line=body_start_line,
                end_line=body_start_line + first_heading_index - 1,
                tags=tags,
            )
        )

    for index, heading in enumerate(headings):
        next_heading_index = (
            headings[index + 1].body_line_index if index + 1 < len(headings) else len(body_lines)
        )
        content_lines = body_lines[heading.body_line_index + 1 : next_heading_index]
        sections.append(
            _section(
                vault_path=vault_path,
                heading=heading.text,
                slug=heading.slug,
                ordinal=heading.ordinal,
                level=heading.level,
                section_path=heading.section_path,
                content="\n".join(content_lines),
                start_line=heading.line_number,
                end_line=body_start_line + max(next_heading_index - 1, heading.body_line_index),
                tags=tags,
            )
        )

    return tuple(sections)


def _section(
    *,
    vault_path: str,
    heading: str | None,
    slug: str,
    ordinal: int,
    level: int,
    section_path: str,
    content: str,
    start_line: int,
    end_line: int,
    tags: tuple[str, ...],
) -> ParsedSection:
    normalized_content = _normalize_newlines(content).strip("\n")
    return ParsedSection(
        vault_path=vault_path,
        section_key=_section_key(vault_path, slug, ordinal),
        section_path=section_path,
        heading=heading,
        heading_slug=slug,
        heading_ordinal=ordinal,
        level=level,
        content=normalized_content,
        content_hash=_sha256(normalized_content.encode("utf-8")),
        start_line=start_line,
        end_line=end_line,
        tags=tags,
    )


def _build_blocks(section: ParsedSection) -> tuple[ParsedBlock, ...]:
    units = _section_units(section.content)
    blocks: list[ParsedBlock] = []
    current_units: list[str] = []

    for unit in _expanded_units(units):
        if not unit.strip():
            continue

        candidate_units = [*current_units, unit]
        candidate_text = _join_units(candidate_units)
        candidate_tokens = estimate_markdown_tokens(candidate_text)
        current_tokens = estimate_markdown_tokens(_join_units(current_units))

        if not current_units:
            current_units = [unit]
        elif candidate_tokens <= HARD_BLOCK_MAX_TOKENS and (
            candidate_tokens <= TARGET_BLOCK_MAX_TOKENS
            or current_tokens < TARGET_BLOCK_MIN_TOKENS
        ):
            current_units.append(unit)
        else:
            _append_block(blocks, section, _join_units(current_units))
            current_units = [unit]

    if current_units:
        _append_block(blocks, section, _join_units(current_units))

    return tuple(blocks)


def _append_block(blocks: list[ParsedBlock], section: ParsedSection, content: str) -> None:
    normalized_content = content.strip()
    if not normalized_content:
        return

    ordinal = len(blocks) + 1
    blocks.append(
        ParsedBlock(
            vault_path=section.vault_path,
            section_key=section.section_key,
            section_path=section.section_path,
            block_key=f"{section.section_key}::block-{ordinal}",
            heading=section.heading,
            content=normalized_content,
            content_hash=_sha256(normalized_content.encode("utf-8")),
            token_count_estimate=estimate_markdown_tokens(normalized_content),
            ordinal=ordinal,
            tags=section.tags,
        )
    )


def _section_units(content: str) -> tuple[str, ...]:
    lines = content.split("\n")
    units: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if _is_fence_line(line):
            unit_lines, index = _consume_fenced_code(lines, index)
            units.append("\n".join(unit_lines))
            continue
        if _is_table_line(line):
            unit_lines, index = _consume_table(lines, index)
            units.append("\n".join(unit_lines))
            continue

        unit_lines: list[str] = []
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                break
            if unit_lines and (_is_fence_line(line) or _is_table_line(line)):
                break
            unit_lines.append(line)
            index += 1
        units.append("\n".join(unit_lines))

    return tuple(units)


def _expanded_units(units: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(part for unit in units for part in _split_oversized_unit(unit))


def _split_oversized_unit(unit: str) -> tuple[str, ...]:
    if estimate_markdown_tokens(unit) <= HARD_BLOCK_MAX_TOKENS:
        return (unit,)

    parts: list[str] = []
    current_lines: list[str] = []
    for line in unit.split("\n"):
        if estimate_markdown_tokens(line) > HARD_BLOCK_MAX_TOKENS:
            if current_lines:
                parts.append("\n".join(current_lines))
                current_lines = []
            parts.extend(_split_long_line(line))
            continue

        candidate = "\n".join([*current_lines, line])
        if current_lines and estimate_markdown_tokens(candidate) > HARD_BLOCK_MAX_TOKENS:
            parts.append("\n".join(current_lines))
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        parts.append("\n".join(current_lines))
    return tuple(part for part in parts if part.strip())


def _split_long_line(line: str) -> tuple[str, ...]:
    max_chars = HARD_BLOCK_MAX_TOKENS * 4
    return tuple(line[index : index + max_chars] for index in range(0, len(line), max_chars))


def _consume_fenced_code(lines: list[str], start_index: int) -> tuple[list[str], int]:
    start_match = _FENCE_RE.match(lines[start_index])
    if start_match is None:
        return [lines[start_index]], start_index + 1

    marker = start_match.group(1)[0]
    length = len(start_match.group(1))
    collected = [lines[start_index]]
    index = start_index + 1
    while index < len(lines):
        collected.append(lines[index])
        closing = _FENCE_RE.match(lines[index])
        if closing is not None and closing.group(1)[0] == marker and len(closing.group(1)) >= length:
            return collected, index + 1
        index += 1
    return collected, index


def _consume_table(lines: list[str], start_index: int) -> tuple[list[str], int]:
    collected: list[str] = []
    index = start_index
    while index < len(lines) and _is_table_line(lines[index]):
        collected.append(lines[index])
        index += 1
    return collected, index


def _extract_wikilinks(vault_path: str, section: ParsedSection) -> tuple[ParsedWikilink, ...]:
    links: list[ParsedWikilink] = []
    for match in _WIKILINK_RE.finditer(section.content):
        raw_target = match.group(1).strip()
        if _looks_like_media_target(raw_target):
            continue
        alias = match.group(2).strip() if match.group(2) else None
        links.append(
            ParsedWikilink(
                vault_path=vault_path,
                source_section_key=section.section_key,
                target=raw_target,
                alias=alias,
                raw=match.group(0),
            )
        )
    return tuple(links)


def _extract_tags(frontmatter: dict[str, Any], body_lines: list[str]) -> tuple[str, ...]:
    tags: set[str] = set()
    tags.update(_frontmatter_tags(frontmatter.get("tags")))

    for line in _non_code_lines(body_lines):
        cleaned = _INLINE_CODE_RE.sub("", line)
        for match in _MARKDOWN_TAG_RE.finditer(cleaned):
            tags.add(_normalize_tag(match.group(1)))

    return tuple(sorted(tag for tag in tags if tag))


def _frontmatter_tags(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {_normalize_tag(part) for part in re.split(r"[\s,]+", value) if part.strip()}
    if isinstance(value, (list, tuple)):
        return {_normalize_tag(str(part)) for part in value if str(part).strip()}
    return {_normalize_tag(str(value))}


def _non_code_lines(lines: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    fence_state: _FenceState | None = None
    for line in lines:
        if _is_fence_line(line):
            fence_state = _next_fence_state(line, fence_state)
            continue
        if fence_state is None:
            result.append(line)
    return tuple(result)


def _next_fence_state(line: str, current: _FenceState | None) -> _FenceState | None:
    match = _FENCE_RE.match(line)
    if match is None:
        return current

    marker_text = match.group(1)
    marker = marker_text[0]
    length = len(marker_text)
    if current is None:
        return _FenceState(marker=marker, length=length)
    if current.marker == marker and length >= current.length:
        return None
    return current


def _is_fence_line(line: str) -> bool:
    return _FENCE_RE.match(line) is not None


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and (stripped.startswith("|") or stripped.endswith("|"))


def _join_units(units: list[str]) -> str:
    return "\n\n".join(unit.strip() for unit in units if unit.strip())


def _looks_like_media_target(target: str) -> bool:
    return target.lower().split("#", maxsplit=1)[0].endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf")
    )


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").strip()


def _clean_heading_text(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _section_key(vault_path: str, slug: str, ordinal: int) -> str:
    return f"{vault_path}#{slug}#{ordinal}"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
