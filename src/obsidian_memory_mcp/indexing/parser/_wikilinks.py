"""Wikilink extraction for indexing."""

from __future__ import annotations

from obsidian_memory_mcp.indexing.parser._models import ParsedSection, ParsedWikilink
from obsidian_memory_mcp.utils import iter_non_embedded_wikilinks


def extract_wikilinks(
    vault_path: str, section: ParsedSection
) -> tuple[ParsedWikilink, ...]:
    links: list[ParsedWikilink] = []
    for token in iter_non_embedded_wikilinks(section.content):
        raw_target = token.target.strip()
        if _looks_like_media_target(raw_target):
            continue
        alias = token.alias.strip() if token.alias else None
        links.append(
            ParsedWikilink(
                vault_path=vault_path,
                source_section_key=section.section_key,
                target=raw_target,
                alias=alias,
                raw=token.raw,
            )
        )
    return tuple(links)


def _looks_like_media_target(target: str) -> bool:
    return (
        target.lower()
        .split("#", maxsplit=1)[0]
        .endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"))
    )
