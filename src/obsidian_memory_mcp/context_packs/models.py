"""Context-pack domain models and boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from obsidian_memory_mcp.config import ContextPackConfig

DEFAULT_CONTEXT_PACK_TOKEN_BUDGET = 8000


@dataclass(frozen=True)
class PackDocument:
    vault_path: str
    absolute_path: Path
    content: str
    fragments: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    documents: tuple[PackDocument, ...]
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]
    tag_filtered_files: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedContextPack:
    pack: ContextPackConfig
    resolution: Resolution


@dataclass(frozen=True)
class ContextPackResult:
    pack_name: str
    content: str
    token_count: int
    files_included: tuple[str, ...]
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]
    budget: int = DEFAULT_CONTEXT_PACK_TOKEN_BUDGET
    tag_filtered_files: tuple[str, ...] = ()
    original_token_count: int | None = None

    def as_response(self) -> dict[str, Any]:
        return {
            "pack_name": self.pack_name,
            "content": self.content,
            "token_count": self.token_count,
            "files_included": list(self.files_included),
            "missing_files": list(self.missing_files),
            "warnings": list(self.warnings),
        }


class IndexQueries(Protocol):
    def bm25_ranks(
        self,
        query: str,
        vault_paths: tuple[str, ...],
    ) -> dict[str, float]:
        """Return BM25 ranks keyed by vault path."""

    def indexed_at(self, vault_paths: tuple[str, ...]) -> dict[str, str]:
        """Return index timestamps keyed by vault path."""
