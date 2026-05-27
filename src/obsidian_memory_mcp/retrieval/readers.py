"""Read-note and read-section retrieval services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.markdown_parser import (
    MarkdownHeading,
    find_headings,
    matching_heading,
    section_end_index,
)
from obsidian_memory_mcp.retrieval._io import read_text, resolve_existing_note
from obsidian_memory_mcp.vault import parse_frontmatter


class ReadNoteService:
    """Read complete markdown notes through the configured read guardrails."""

    def __init__(self, config: ProjectConfig, guardrails: GuardrailEvaluator):
        self._config = config
        self._guardrails = guardrails

    def read(self, note_path: str) -> dict[str, Any]:
        resolved_path = resolve_existing_note(
            self._config, self._guardrails, note_path
        )
        raw = read_text(self._config, resolved_path)
        return {
            "file_path": resolved_path.relative_to(self._config.vault_path).as_posix(),
            "content": raw,
            "frontmatter": parse_frontmatter(raw),
            "file_size_bytes": len(raw.encode("utf-8")),
        }


class ReadSectionService:
    """Read one heading section from a guarded markdown note."""

    def __init__(self, config: ProjectConfig, guardrails: GuardrailEvaluator):
        self._config = config
        self._guardrails = guardrails

    def read(self, note_path: str, heading_name: str) -> dict[str, Any]:
        resolved_path = resolve_existing_note(
            self._config, self._guardrails, note_path
        )
        raw = read_text(self._config, resolved_path)
        section = _extract_section(raw, heading_name)
        if section is None:
            file_path = resolved_path.relative_to(self._config.vault_path).as_posix()
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_SECTION_NOT_FOUND,
                    details={"file_path": file_path, "heading_name": heading_name},
                )
            )

        return {
            "file_path": resolved_path.relative_to(self._config.vault_path).as_posix(),
            "heading": section.heading,
            "heading_level": section.heading_level,
            "content": section.content,
            "context_prefix": section.context_prefix,
        }


@dataclass(frozen=True)
class _ExtractedSection:
    heading: str
    heading_level: int
    content: str
    context_prefix: str


def _extract_section(content: str, heading_name: str) -> _ExtractedSection | None:
    lines = content.splitlines()
    headings = find_headings(lines)
    heading = matching_heading(headings, heading_name)
    if heading is None:
        return None

    end_index = section_end_index(headings, heading, line_count=len(lines))
    section_content = "\n".join(lines[heading.line_index : end_index]).rstrip()
    context_prefix = _context_prefix(lines, headings, heading.line_index)
    return _ExtractedSection(
        heading=heading.text,
        heading_level=heading.level,
        content=section_content,
        context_prefix=context_prefix,
    )


def _context_prefix(
    lines: list[str],
    headings: tuple[MarkdownHeading, ...],
    heading_index: int,
) -> str:
    frontmatter_body_start = _frontmatter_body_start(lines)
    heading_line_indexes = {heading.line_index for heading in headings}
    context: list[str] = []
    index = heading_index - 1

    while index >= frontmatter_body_start and len(context) < 3:
        line = lines[index]
        if index in heading_line_indexes:
            break
        if line.strip():
            context.append(line)
        index -= 1

    return "\n".join(reversed(context))


def _frontmatter_body_start(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index + 1
    return 0
