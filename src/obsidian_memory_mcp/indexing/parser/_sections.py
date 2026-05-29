"""Section assembly for indexing."""

from __future__ import annotations

from obsidian_memory_mcp.indexing.parser._models import HeadingOccurrence, ParsedSection
from obsidian_memory_mcp.indexing.parser._text import (
    normalize_newlines,
    section_key,
    sha256,
)


def build_sections(
    vault_path: str,
    body_lines: list[str],
    body_start_line: int,
    headings: tuple[HeadingOccurrence, ...],
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
            headings[index + 1].body_line_index
            if index + 1 < len(headings)
            else len(body_lines)
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
                end_line=body_start_line
                + max(next_heading_index - 1, heading.body_line_index),
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
    normalized_content = normalize_newlines(content).strip("\n")
    return ParsedSection(
        vault_path=vault_path,
        section_key=section_key(vault_path, slug, ordinal),
        section_path=section_path,
        heading=heading,
        heading_slug=slug,
        heading_ordinal=ordinal,
        level=level,
        content=normalized_content,
        content_hash=sha256(normalized_content.encode("utf-8")),
        start_line=start_line,
        end_line=end_line,
        tags=tags,
    )
