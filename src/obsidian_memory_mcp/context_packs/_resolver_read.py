"""Parallel filesystem reads for context-pack document resolution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from pathlib import Path

from obsidian_memory_mcp.config import ContextPackConfig
from obsidian_memory_mcp.context_packs._models import PackDocument
from obsidian_memory_mcp.context_packs._resolver_sections import select_pack_content
from obsidian_memory_mcp.context_packs._resolver_tags import matches_tags


@dataclass(frozen=True)
class DocumentCandidate:
    vault_path: str
    absolute_path: Path


@dataclass(frozen=True)
class ReadDocumentResult:
    document: PackDocument | None
    warnings: tuple[str, ...]
    tag_filtered_file: str | None = None


def read_candidates(
    candidates: list[DocumentCandidate],
    pack: ContextPackConfig,
) -> tuple[ReadDocumentResult, ...]:
    if len(candidates) <= 1:
        return tuple(read_candidate(candidate, pack) for candidate in candidates)

    max_workers = min(32, len(candidates))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return tuple(executor.map(read_candidate, candidates, repeat(pack)))


def read_candidate(
    candidate: DocumentCandidate,
    pack: ContextPackConfig,
) -> ReadDocumentResult:
    raw = candidate.absolute_path.read_text(encoding="utf-8")
    if not matches_tags(raw, pack.tags_filter):
        return ReadDocumentResult(
            document=None,
            warnings=(),
            tag_filtered_file=candidate.vault_path,
        )

    selected = select_pack_content(
        vault_path=candidate.vault_path,
        raw_content=raw,
        section_names=pack.sections,
    )
    return ReadDocumentResult(
        document=PackDocument(
            vault_path=candidate.vault_path,
            absolute_path=candidate.absolute_path,
            content=selected.content,
            fragments=selected.fragments,
        ),
        warnings=selected.warnings,
    )
