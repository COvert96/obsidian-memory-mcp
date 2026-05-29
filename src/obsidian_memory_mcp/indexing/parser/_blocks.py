"""Block chunking for indexing."""

from __future__ import annotations

from obsidian_memory_mcp.markdown import FENCE_RE, is_fence_line
from obsidian_memory_mcp.indexing.parser._models import (
    HARD_BLOCK_MAX_TOKENS,
    TARGET_BLOCK_MAX_TOKENS,
    TARGET_BLOCK_MIN_TOKENS,
    ParsedBlock,
    ParsedSection,
)
from obsidian_memory_mcp.indexing.parser._text import estimate_markdown_tokens, sha256


def build_blocks(section: ParsedSection) -> tuple[ParsedBlock, ...]:
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


def _append_block(
    blocks: list[ParsedBlock], section: ParsedSection, content: str
) -> None:
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
            content_hash=sha256(normalized_content.encode("utf-8")),
            token_count_estimate=estimate_markdown_tokens(normalized_content),
            ordinal=ordinal,
            tags=section.tags,
        )
    )


def _section_units(content: str) -> tuple[str, ...]:
    """Split a section into units that preserve markdown structure.

    We avoid splitting inside fenced code blocks and tables so downstream token
    budgeting and previews remain predictable and semantically coherent.
    """
    lines = content.split("\n")
    units: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        unit, index = _next_section_unit(lines, index)
        units.append(unit)

    return tuple(units)


def _next_section_unit(lines: list[str], index: int) -> tuple[str, int]:
    line = lines[index]
    if is_fence_line(line):
        fenced_lines, next_index = _consume_fenced_code(lines, index)
        return "\n".join(fenced_lines), next_index
    if _is_table_line(line):
        table_lines, next_index = _consume_table(lines, index)
        return "\n".join(table_lines), next_index
    return _consume_paragraph_unit(lines, index)


def _consume_paragraph_unit(lines: list[str], start_index: int) -> tuple[str, int]:
    unit_lines: list[str] = []
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if unit_lines and (is_fence_line(line) or _is_table_line(line)):
            break
        unit_lines.append(line)
        index += 1
    return "\n".join(unit_lines), index


def _expanded_units(units: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(part for unit in units for part in _split_oversized_unit(unit))


def _split_oversized_unit(unit: str) -> tuple[str, ...]:
    """Split oversized units while keeping hard token caps.

    This is a last resort: we first attempt to keep units intact, then fall back
    to line-based splitting, and finally split pathological single long lines.
    """
    if estimate_markdown_tokens(unit) <= HARD_BLOCK_MAX_TOKENS:
        return (unit,)

    parts: list[str] = []
    current_lines: list[str] = []
    for line in unit.split("\n"):
        if estimate_markdown_tokens(line) > HARD_BLOCK_MAX_TOKENS:
            _flush_line_buffer(parts, current_lines)
            parts.extend(_split_long_line(line))
            continue

        if _line_exceeds_budget(current_lines, line):
            _flush_line_buffer(parts, current_lines)
            current_lines = [line]
        else:
            current_lines.append(line)

    _flush_line_buffer(parts, current_lines)
    return tuple(part for part in parts if part.strip())


def _flush_line_buffer(parts: list[str], current_lines: list[str]) -> None:
    if current_lines:
        parts.append("\n".join(current_lines))
        current_lines.clear()


def _line_exceeds_budget(current_lines: list[str], line: str) -> bool:
    if not current_lines:
        return False
    candidate = "\n".join([*current_lines, line])
    return estimate_markdown_tokens(candidate) > HARD_BLOCK_MAX_TOKENS


def _split_long_line(line: str) -> tuple[str, ...]:
    max_chars = HARD_BLOCK_MAX_TOKENS * 4
    return tuple(
        line[index : index + max_chars] for index in range(0, len(line), max_chars)
    )


def _consume_fenced_code(lines: list[str], start_index: int) -> tuple[list[str], int]:
    start_match = FENCE_RE.match(lines[start_index])
    if start_match is None:
        return [lines[start_index]], start_index + 1

    marker = start_match.group(1)[0]
    length = len(start_match.group(1))
    collected = [lines[start_index]]
    index = start_index + 1
    while index < len(lines):
        collected.append(lines[index])
        closing = FENCE_RE.match(lines[index])
        if (
            closing is not None
            and closing.group(1)[0] == marker
            and len(closing.group(1)) >= length
        ):
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


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and (stripped.startswith("|") or stripped.endswith("|"))


def _join_units(units: list[str]) -> str:
    return "\n\n".join(unit.strip() for unit in units if unit.strip())
