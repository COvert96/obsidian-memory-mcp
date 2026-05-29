"""Section selection helpers for context-pack documents."""

from __future__ import annotations

from dataclasses import dataclass

from obsidian_memory_mcp.markdown import (
    find_headings,
    normalize_heading_name,
    section_end_index,
)


@dataclass(frozen=True)
class SelectedContent:
    content: str
    fragments: tuple[str, ...]
    warnings: tuple[str, ...]


def select_pack_content(
    *,
    vault_path: str,
    raw_content: str,
    section_names: tuple[str, ...],
) -> SelectedContent:
    if not section_names:
        return SelectedContent(
            content=raw_content,
            fragments=split_complete_sections(raw_content),
            warnings=(),
        )

    selected, missing = extract_named_sections(raw_content, section_names)
    if not selected:
        return SelectedContent(
            content=raw_content,
            fragments=split_complete_sections(raw_content),
            warnings=(
                f"Sections not found in '{vault_path}': {', '.join(section_names)}; "
                "included full file as fallback.",
            ),
        )

    if missing:
        return SelectedContent(
            content="\n\n".join(selected),
            fragments=selected,
            warnings=(
                f"Sections not found in '{vault_path}': {', '.join(missing)}; "
                "included available sections only.",
            ),
        )

    return SelectedContent(
        content="\n\n".join(selected),
        fragments=selected,
        warnings=(),
    )


def extract_named_sections(
    content: str,
    section_names: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lines = content.splitlines()
    headings = find_headings(lines)
    target_by_normalized = {
        normalize_heading_name(name): name for name in section_names
    }
    found: set[str] = set()
    selected: list[str] = []

    for heading in headings:
        normalized = normalize_heading_name(heading.text)
        if normalized not in target_by_normalized:
            continue
        found.add(normalized)
        end_index = section_end_index(headings, heading, line_count=len(lines))
        selected.append("\n".join(lines[heading.line_index : end_index]).rstrip())

    missing = tuple(
        name for name in section_names if normalize_heading_name(name) not in found
    )
    return tuple(selected), missing


def split_complete_sections(content: str) -> tuple[str, ...]:
    lines = content.splitlines()
    headings = find_headings(lines)
    if not headings:
        return (content,) if content else ()

    fragments: list[str] = []
    first_heading = headings[0].line_index
    preamble = "\n".join(lines[:first_heading]).rstrip()
    if preamble:
        fragments.append(preamble)

    for index, heading in enumerate(headings):
        next_index = (
            headings[index + 1].line_index if index + 1 < len(headings) else len(lines)
        )
        fragment = "\n".join(lines[heading.line_index : next_index]).rstrip()
        if fragment:
            fragments.append(fragment)
    return tuple(fragments)
