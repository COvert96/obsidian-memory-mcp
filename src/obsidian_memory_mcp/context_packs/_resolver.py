"""Context-pack declaration resolution and document selection."""

from __future__ import annotations

import difflib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from pathlib import Path

from obsidian_memory_mcp.config import (
    ContextPackConfig,
    GuardrailEvaluator,
    ProjectConfig,
)
from obsidian_memory_mcp.context_packs._models import (
    PackDocument,
    Resolution,
    ResolvedContextPack,
)
from obsidian_memory_mcp.context_packs._resolver_paths import (
    contains_glob,
    expand_glob,
    guard_read_path,
    resolve_explicit_path,
)
from obsidian_memory_mcp.context_packs._resolver_sections import select_pack_content
from obsidian_memory_mcp.context_packs._resolver_tags import matches_tags
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


@dataclass(frozen=True)
class _DocumentCandidate:
    vault_path: str
    absolute_path: Path


@dataclass(frozen=True)
class _ReadDocumentResult:
    document: PackDocument | None
    warnings: tuple[str, ...]
    tag_filtered_file: str | None = None


class ContextPackResolver:
    """Resolve pack declarations into ordered markdown documents."""

    def __init__(
        self,
        config: ProjectConfig,
        guardrails: GuardrailEvaluator | None = None,
    ):
        self._config = config
        self._guardrails = guardrails or GuardrailEvaluator(config)
        self._packs_by_name = {pack.name: pack for pack in config.context_packs}

    def resolve(self, pack_name: str) -> ResolvedContextPack:
        pack = self._pack(pack_name)
        return ResolvedContextPack(
            pack=pack,
            resolution=self._resolve_pack(pack, seen_paths=set(), stack=()),
        )

    def _pack(self, pack_name: str) -> ContextPackConfig:
        pack = self._packs_by_name.get(pack_name)
        if pack is not None:
            return pack

        known_pack_names = sorted(self._packs_by_name)
        close_matches = tuple(
            difflib.get_close_matches(pack_name, known_pack_names, n=3, cutoff=0.6)
        )
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INVALID_REQUEST,
                message=f"Context pack '{pack_name}' is not configured for this project.",
                details={
                    "pack_name": pack_name,
                    "known_context_packs": known_pack_names,
                    "closest_matches": list(close_matches),
                    "suggestion": (
                        "Call list_context_packs for this project and use an exact "
                        "pack_name from that result."
                    ),
                },
            )
        )

    def _resolve_pack(
        self,
        pack: ContextPackConfig,
        *,
        seen_paths: set[str],
        stack: tuple[str, ...],
    ) -> Resolution:
        if pack.name in stack:
            cycle = " -> ".join((*stack, pack.name))
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_INVALID_PROJECT,
                    message=f"Context pack include cycle detected: {cycle}.",
                    details={
                        "pack_name": pack.name,
                        "cycle": cycle,
                        "suggestion": "Remove one include_context_packs entry.",
                    },
                )
            )

        documents: list[PackDocument] = []
        missing_files: list[str] = []
        warnings: list[str] = []
        tag_filtered_files: list[str] = []

        own_files = self._resolve_own_paths(pack)
        missing_files.extend(own_files.missing_files)
        warnings.extend(own_files.warnings)
        tag_filtered_files.extend(own_files.tag_filtered_files)
        for document in own_files.documents:
            if document.vault_path in seen_paths:
                continue
            seen_paths.add(document.vault_path)
            documents.append(document)

        for included_name in pack.include_context_packs:
            included = self._resolve_pack(
                self._pack(included_name),
                seen_paths=seen_paths,
                stack=(*stack, pack.name),
            )
            documents.extend(included.documents)
            missing_files.extend(included.missing_files)
            warnings.extend(included.warnings)
            tag_filtered_files.extend(included.tag_filtered_files)

        return Resolution(
            documents=tuple(documents),
            missing_files=tuple(missing_files),
            warnings=tuple(warnings),
            tag_filtered_files=tuple(tag_filtered_files),
        )

    def _resolve_own_paths(self, pack: ContextPackConfig) -> Resolution:
        paths: list[Path] = []
        missing_files: list[str] = []
        warnings: list[str] = []

        for pattern in pack.paths:
            if contains_glob(pattern):
                matched_paths, glob_warnings = expand_glob(self._config, pattern)
                paths.extend(matched_paths)
                warnings.extend(glob_warnings)
                continue

            explicit_path = resolve_explicit_path(
                self._config, self._guardrails, pattern
            )
            if explicit_path.warning is not None:
                warnings.append(explicit_path.warning)
                continue
            if explicit_path.missing_file is not None:
                missing_files.append(explicit_path.missing_file)
                continue
            if explicit_path.absolute_path is not None:
                paths.append(explicit_path.absolute_path)

        resolved = self._documents_from_paths(
            tuple(paths), pack, warnings=tuple(warnings)
        )
        return Resolution(
            documents=resolved.documents,
            missing_files=tuple(missing_files),
            warnings=resolved.warnings,
            tag_filtered_files=resolved.tag_filtered_files,
        )

    def _documents_from_paths(
        self,
        paths: tuple[Path, ...],
        pack: ContextPackConfig,
        *,
        warnings: tuple[str, ...],
    ) -> Resolution:
        candidates: list[_DocumentCandidate] = []
        collected_warnings = list(warnings)

        for absolute_path in paths:
            resolved_path, warning = guard_read_path(
                self._config, self._guardrails, absolute_path
            )
            if warning is not None:
                collected_warnings.append(warning)
                continue
            if resolved_path is None:
                continue

            vault_path = resolved_path.relative_to(self._config.vault_path).as_posix()
            candidates.append(
                _DocumentCandidate(vault_path=vault_path, absolute_path=resolved_path)
            )

        documents: list[PackDocument] = []
        tag_filtered_files: list[str] = []
        for result in _read_candidates(candidates, pack):
            if result.document is not None:
                documents.append(result.document)
            if result.tag_filtered_file is not None:
                tag_filtered_files.append(result.tag_filtered_file)
            collected_warnings.extend(result.warnings)

        return Resolution(
            documents=tuple(documents),
            missing_files=(),
            warnings=tuple(collected_warnings),
            tag_filtered_files=tuple(tag_filtered_files),
        )


def _read_candidates(
    candidates: list[_DocumentCandidate],
    pack: ContextPackConfig,
) -> tuple[_ReadDocumentResult, ...]:
    if len(candidates) <= 1:
        return tuple(_read_candidate(candidate, pack) for candidate in candidates)

    max_workers = min(32, len(candidates))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return tuple(executor.map(_read_candidate, candidates, repeat(pack)))


def _read_candidate(
    candidate: _DocumentCandidate,
    pack: ContextPackConfig,
) -> _ReadDocumentResult:
    raw = candidate.absolute_path.read_text(encoding="utf-8")
    if not matches_tags(raw, pack.tags_filter):
        return _ReadDocumentResult(
            document=None,
            warnings=(),
            tag_filtered_file=candidate.vault_path,
        )

    selected = select_pack_content(
        vault_path=candidate.vault_path,
        raw_content=raw,
        section_names=pack.sections,
    )
    return _ReadDocumentResult(
        document=PackDocument(
            vault_path=candidate.vault_path,
            absolute_path=candidate.absolute_path,
            content=selected.content,
            fragments=selected.fragments,
        ),
        warnings=selected.warnings,
    )
