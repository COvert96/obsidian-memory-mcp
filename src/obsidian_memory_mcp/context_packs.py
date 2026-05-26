"""Context pack loading and token-budget enforcement."""

from __future__ import annotations

import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from itertools import repeat
from pathlib import Path, PurePath
from typing import Any, Protocol

from obsidian_memory_mcp.config import (
    GuardrailEvaluator,
    ContextPackConfig,
    ProjectConfig,
)
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.schema import connect_index_db
from obsidian_memory_mcp.tokens import estimate_tokens
from obsidian_memory_mcp.vault import parse_frontmatter

DEFAULT_CONTEXT_PACK_TOKEN_BUDGET = 8000
NEAR_BUDGET_RATIO = 0.9
STALE_WARNING_TEMPLATE = (
    "File '{path}' has been modified since last index; content may be stale. "
    "Re-run indexing to refresh."
)

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
_ISO_TIMESTAMP_RE = re.compile(
    r"^(?P<head>.*?)(?:\.(?P<fraction>\d+))?(?P<zone>Z|[+-]\d{2}:\d{2})?$"
)
_GLOB_CHARS = frozenset("*?[")


@dataclass(frozen=True)
class ContextPackResult:
    pack_name: str
    content: str
    token_count: int
    files_included: tuple[str, ...]
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]
    budget: int
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


@dataclass(frozen=True)
class _PackDocument:
    vault_path: str
    absolute_path: Path
    content: str
    fragments: tuple[str, ...]


@dataclass(frozen=True)
class _DocumentCandidate:
    vault_path: str
    absolute_path: Path


@dataclass(frozen=True)
class _ReadDocumentResult:
    document: _PackDocument | None
    warnings: tuple[str, ...]
    tag_filtered_file: str | None = None


@dataclass(frozen=True)
class _Resolution:
    documents: tuple[_PackDocument, ...]
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]
    tag_filtered_files: tuple[str, ...]


@dataclass(frozen=True)
class _ResolvedPack:
    pack: ContextPackConfig
    resolution: _Resolution


@dataclass(frozen=True)
class _ExplicitPathResolution:
    absolute_path: Path | None = None
    missing_file: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class _Heading:
    line_index: int
    level: int
    text: str


@dataclass(frozen=True)
class _FenceState:
    marker: str
    length: int


class IndexQueries(Protocol):
    def bm25_ranks(
        self,
        query: str,
        vault_paths: tuple[str, ...],
    ) -> dict[str, float]:
        """Return BM25 ranks keyed by vault path."""

    def indexed_at(self, vault_paths: tuple[str, ...]) -> dict[str, str]:
        """Return index timestamps keyed by vault path."""


class SqliteIndexQueries:
    """SQLite adapter for context-pack index metadata and ranking queries."""

    def __init__(self, index_db_path: Path):
        self._index_db_path = index_db_path

    def bm25_ranks(
        self,
        query: str,
        vault_paths: tuple[str, ...],
    ) -> dict[str, float]:
        if not query or not vault_paths:
            return {}

        placeholders = ", ".join("?" for _ in vault_paths)
        sql = f"""
            SELECT blocks.vault_path, MIN(bm25(blocks_fts)) AS rank
            FROM blocks_fts
            JOIN blocks ON blocks.block_key = blocks_fts.block_key
            JOIN files ON files.id = blocks.file_id
            WHERE blocks_fts MATCH ?
              AND files.deleted_at IS NULL
              AND blocks.vault_path IN ({placeholders})
            GROUP BY blocks.vault_path
        """
        connection = connect_index_db(self._index_db_path)
        try:
            rows = connection.execute(sql, (query, *vault_paths)).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            connection.close()

        return {row["vault_path"]: float(row["rank"]) for row in rows}

    def indexed_at(self, vault_paths: tuple[str, ...]) -> dict[str, str]:
        if not vault_paths:
            return {}

        placeholders = ", ".join("?" for _ in vault_paths)
        sql = f"""
            SELECT vault_path, indexed_at
            FROM files
            WHERE deleted_at IS NULL
              AND vault_path IN ({placeholders})
        """
        connection = connect_index_db(self._index_db_path)
        try:
            rows = connection.execute(sql, vault_paths).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            connection.close()

        return {row["vault_path"]: row["indexed_at"] for row in rows}


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

    def resolve(self, pack_name: str) -> _ResolvedPack:
        pack = self._pack(pack_name)
        return _ResolvedPack(
            pack=pack,
            resolution=self._resolve_pack(pack, seen_paths=set(), stack=()),
        )

    def _pack(self, pack_name: str) -> ContextPackConfig:
        pack = self._packs_by_name.get(pack_name)
        if pack is not None:
            return pack

        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_INVALID_PROJECT,
                message=f"Context pack '{pack_name}' is not configured for this project.",
                details={
                    "pack_name": pack_name,
                    "known_context_packs": sorted(self._packs_by_name),
                    "suggestion": (
                        "Use a pack name from this project's context_packs config."
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
    ) -> _Resolution:
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

        documents: list[_PackDocument] = []
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

        return _Resolution(
            documents=tuple(documents),
            missing_files=tuple(missing_files),
            warnings=tuple(warnings),
            tag_filtered_files=tuple(tag_filtered_files),
        )

    def _resolve_own_paths(self, pack: ContextPackConfig) -> _Resolution:
        paths: list[Path] = []
        missing_files: list[str] = []
        warnings: list[str] = []

        for pattern in pack.paths:
            if _contains_glob(pattern):
                matched_paths, glob_warnings = self._expand_glob(pattern)
                paths.extend(matched_paths)
                warnings.extend(glob_warnings)
                continue

            explicit_path = self._explicit_path(pattern)
            if explicit_path.warning is not None:
                warnings.append(explicit_path.warning)
                continue
            if explicit_path.missing_file is not None:
                missing_files.append(explicit_path.missing_file)
                continue
            if explicit_path.absolute_path is not None:
                paths.append(explicit_path.absolute_path)

        resolved = self._documents_from_paths(tuple(paths), pack, warnings=tuple(warnings))
        return _Resolution(
            documents=resolved.documents,
            missing_files=tuple(missing_files),
            warnings=resolved.warnings,
            tag_filtered_files=resolved.tag_filtered_files,
        )

    def _explicit_path(self, pattern: str) -> "_ExplicitPathResolution":
        path = _normalize_vault_reference(pattern)
        if _is_unsafe_pattern(path):
            return _ExplicitPathResolution(
                warning=f"Path '{path}' was skipped because it is unsafe."
            )
        if not self._guardrails.allows_read_relative(path):
            return _ExplicitPathResolution(
                warning=f"File '{path}' was skipped because it violates read guardrails."
            )

        absolute_path = self._config.vault_path / path
        if not absolute_path.is_file():
            return _ExplicitPathResolution(missing_file=path)
        return _ExplicitPathResolution(absolute_path=absolute_path)

    def _expand_glob(self, pattern: str) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        normalized = _normalize_vault_reference(pattern)
        if _is_unsafe_pattern(normalized):
            return (), (f"Path pattern '{normalized}' was skipped because it is unsafe.",)

        matches = sorted(
            (
                path
                for path in self._config.vault_path.glob(normalized)
                if path.is_file()
            ),
            key=lambda path: path.relative_to(self._config.vault_path).as_posix(),
        )
        return tuple(matches), ()

    def _documents_from_paths(
        self,
        paths: tuple[Path, ...],
        pack: ContextPackConfig,
        *,
        warnings: tuple[str, ...],
    ) -> _Resolution:
        candidates: list[_DocumentCandidate] = []
        collected_warnings = list(warnings)

        for absolute_path in paths:
            vault_path = absolute_path.relative_to(self._config.vault_path).as_posix()
            if not self._guardrails.allows_read_relative(vault_path):
                collected_warnings.append(
                    f"File '{vault_path}' was skipped because it violates read guardrails."
                )
                continue
            if _has_symlink_segment(self._config.vault_path, absolute_path):
                try:
                    absolute_path = self._guardrails.check_read(vault_path)
                except ToolExecutionError as error:
                    collected_warnings.append(
                        f"Path '{vault_path}' was skipped: {error.error.message}"
                    )
                    continue

            candidates.append(
                _DocumentCandidate(vault_path=vault_path, absolute_path=absolute_path)
            )

        documents: list[_PackDocument] = []
        tag_filtered_files: list[str] = []
        for result in _read_candidates(candidates, pack):
            if result.document is not None:
                documents.append(result.document)
            if result.tag_filtered_file is not None:
                tag_filtered_files.append(result.tag_filtered_file)
            collected_warnings.extend(result.warnings)

        return _Resolution(
            documents=tuple(documents),
            missing_files=(),
            warnings=tuple(collected_warnings),
            tag_filtered_files=tuple(tag_filtered_files),
        )


class BudgetEnforcer:
    """Apply strict and soft context-pack token budgets."""

    def __init__(self, index_queries: IndexQueries):
        self._index_queries = index_queries

    def enforce(
        self,
        result: ContextPackResult,
        documents: tuple[_PackDocument, ...],
        pack: ContextPackConfig,
        *,
        strict_budget: bool,
    ) -> ContextPackResult:
        if result.token_count <= result.budget:
            return _with_near_budget_warning(result)
        if strict_budget:
            raise _budget_error(result)
        return _with_near_budget_warning(self._truncate_to_budget(result, documents, pack))

    def _truncate_to_budget(
        self,
        result: ContextPackResult,
        documents: tuple[_PackDocument, ...],
        pack: ContextPackConfig,
    ) -> ContextPackResult:
        ranked_documents = self._rank_for_truncation(pack, result, documents)
        kept_documents: list[_PackDocument] = []
        emitted_parts: list[str] = []
        included_paths: set[str] = set()

        for document in ranked_documents:
            full_part = _format_document(document)
            if _candidate_fits(emitted_parts, full_part, result.budget):
                emitted_parts.append(full_part)
                kept_documents.append(document)
                included_paths.add(document.vault_path)
                continue

            for fragment in document.fragments:
                fragment_part = _format_fragment(document.vault_path, fragment)
                if _candidate_fits(emitted_parts, fragment_part, result.budget):
                    emitted_parts.append(fragment_part)
                    included_paths.add(document.vault_path)
                else:
                    break

        content = "".join(emitted_parts)
        token_count = estimate_tokens(content)
        omitted_count = len(
            [path for path in result.files_included if path not in included_paths]
        )
        warning = (
            f"Context pack '{result.pack_name}' truncated from "
            f"{result.token_count} to {token_count} tokens to fit budget "
            f"{result.budget}; omitted {omitted_count} file(s)."
        )
        return replace(
            result,
            content=content,
            token_count=token_count,
            files_included=tuple(
                path for path in result.files_included if path in included_paths
            ),
            warnings=(*result.warnings, warning),
            original_token_count=result.token_count,
        )

    def _rank_for_truncation(
        self,
        pack: ContextPackConfig,
        result: ContextPackResult,
        documents: tuple[_PackDocument, ...],
    ) -> tuple[_PackDocument, ...]:
        order_by_path = {
            vault_path: index for index, vault_path in enumerate(result.files_included)
        }
        included_documents = tuple(
            document for document in documents if document.vault_path in order_by_path
        )
        rank_by_path = self._index_queries.bm25_ranks(
            _ranking_query(pack),
            tuple(document.vault_path for document in included_documents),
        )
        if not rank_by_path:
            return included_documents

        return tuple(
            sorted(
                included_documents,
                key=lambda document: _truncation_rank_key(
                    document.vault_path,
                    rank_by_path,
                    order_by_path,
                ),
            )
        )


class ContextPackLoader:
    """Load context packs through resolver, index, and budget boundaries."""

    def __init__(
        self,
        config: ProjectConfig,
        *,
        resolver: ContextPackResolver | None = None,
        index_queries: IndexQueries | None = None,
        budget_enforcer: BudgetEnforcer | None = None,
    ):
        resolved_index_queries = index_queries or SqliteIndexQueries(
            config.index_db_location
        )
        self._resolver = resolver or ContextPackResolver(config)
        self._index_queries = resolved_index_queries
        self._budget_enforcer = budget_enforcer or BudgetEnforcer(
            resolved_index_queries
        )

    def load(
        self,
        pack_name: str,
        *,
        strict_budget: bool = True,
    ) -> ContextPackResult:
        resolved = self._resolved_result(pack_name)
        return self._budget_enforcer.enforce(
            resolved[0],
            resolved[1],
            resolved[2],
            strict_budget=strict_budget,
        )

    def inspect(self, pack_name: str) -> ContextPackResult:
        result, _documents, _pack = self._resolved_result(pack_name)
        return _with_near_budget_warning(result)

    def _resolved_result(
        self,
        pack_name: str,
    ) -> tuple[ContextPackResult, tuple[_PackDocument, ...], ContextPackConfig]:
        resolved_pack = self._resolver.resolve(pack_name)
        documents = resolved_pack.resolution.documents
        content = _format_documents(documents)
        token_count = estimate_tokens(content)
        result = ContextPackResult(
            pack_name=pack_name,
            content=content,
            token_count=token_count,
            files_included=tuple(document.vault_path for document in documents),
            missing_files=resolved_pack.resolution.missing_files,
            warnings=(
                *resolved_pack.resolution.warnings,
                *_stale_warnings(documents, self._index_queries),
            ),
            budget=_budget_for(resolved_pack.pack),
            tag_filtered_files=resolved_pack.resolution.tag_filtered_files,
        )
        return result, documents, resolved_pack.pack


@dataclass(frozen=True)
class _SelectedContent:
    content: str
    fragments: tuple[str, ...]
    warnings: tuple[str, ...]


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
    if not _matches_tags(raw, pack.tags_filter):
        return _ReadDocumentResult(
            document=None,
            warnings=(),
            tag_filtered_file=candidate.vault_path,
        )

    selected = _select_pack_content(
        vault_path=candidate.vault_path,
        raw_content=raw,
        section_names=pack.sections,
    )
    return _ReadDocumentResult(
        document=_PackDocument(
            vault_path=candidate.vault_path,
            absolute_path=candidate.absolute_path,
            content=selected.content,
            fragments=selected.fragments,
        ),
        warnings=selected.warnings,
    )


def _select_pack_content(
    *,
    vault_path: str,
    raw_content: str,
    section_names: tuple[str, ...],
) -> _SelectedContent:
    if not section_names:
        return _SelectedContent(
            content=raw_content,
            fragments=_split_complete_sections(raw_content),
            warnings=(),
        )

    selected, missing = _extract_named_sections(raw_content, section_names)
    if not selected:
        return _SelectedContent(
            content=raw_content,
            fragments=_split_complete_sections(raw_content),
            warnings=(
                f"Sections not found in '{vault_path}': {', '.join(section_names)}; "
                "included full file as fallback.",
            ),
        )

    if missing:
        return _SelectedContent(
            content="\n\n".join(selected),
            fragments=selected,
            warnings=(
                f"Sections not found in '{vault_path}': {', '.join(missing)}; "
                "included available sections only.",
            ),
        )

    return _SelectedContent(
        content="\n\n".join(selected),
        fragments=selected,
        warnings=(),
    )


def _extract_named_sections(
    content: str,
    section_names: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lines = content.splitlines()
    headings = _find_headings(lines)
    target_by_normalized = {
        _normalize_heading_name(name): name for name in section_names
    }
    found: set[str] = set()
    selected: list[str] = []

    for heading in headings:
        normalized = _normalize_heading_name(heading.text)
        if normalized not in target_by_normalized:
            continue
        found.add(normalized)
        end_index = _section_end_index(headings, heading, line_count=len(lines))
        selected.append("\n".join(lines[heading.line_index : end_index]).rstrip())

    missing = tuple(
        name
        for name in section_names
        if _normalize_heading_name(name) not in found
    )
    return tuple(selected), missing


def _split_complete_sections(content: str) -> tuple[str, ...]:
    lines = content.splitlines()
    headings = _find_headings(lines)
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


def _find_headings(lines: list[str]) -> tuple[_Heading, ...]:
    headings: list[_Heading] = []
    fence_state: _FenceState | None = None
    for index, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)
        if fence_match is not None:
            fence_state = _next_fence_state(fence_match, fence_state)
            continue
        if fence_state is not None:
            continue

        match = _HEADING_RE.match(line)
        if match is None:
            continue
        headings.append(
            _Heading(
                line_index=index,
                level=len(match.group(1)),
                text=_clean_heading_text(match.group(2)),
            )
        )
    return tuple(headings)


def _section_end_index(
    headings: tuple[_Heading, ...],
    current: _Heading,
    *,
    line_count: int,
) -> int:
    for heading in headings:
        if heading.line_index > current.line_index and heading.level <= current.level:
            return heading.line_index
    return line_count


def _next_fence_state(
    match: re.Match[str],
    current: _FenceState | None,
) -> _FenceState | None:
    marker_text = match.group(1)
    suffix = match.group(2).strip()
    marker = marker_text[0]
    length = len(marker_text)
    if current is None:
        return _FenceState(marker=marker, length=length)
    if current.marker == marker and length >= current.length and not suffix:
        return None
    return current


def _matches_tags(content: str, tags_filter: tuple[str, ...]) -> bool:
    if not tags_filter:
        return True
    available = _frontmatter_tags(content)
    required = {_normalize_tag(tag) for tag in tags_filter}
    return required.issubset(available)


def _frontmatter_tags(content: str) -> set[str]:
    value = parse_frontmatter(content).get("tags")
    if value is None:
        return set()
    if isinstance(value, str):
        return {
            _normalize_tag(part)
            for part in re.split(r"[\s,]+", value)
            if part.strip()
        }
    if isinstance(value, (list, tuple)):
        return {_normalize_tag(str(part)) for part in value if str(part).strip()}
    return {_normalize_tag(str(value))}


def _format_documents(documents: tuple[_PackDocument, ...]) -> str:
    return "".join(_format_document(document) for document in documents)


def _format_document(document: _PackDocument) -> str:
    return _format_fragment(document.vault_path, document.content)


def _format_fragment(vault_path: str, content: str) -> str:
    return f"<!-- From: {vault_path} -->\n{content}\n\n"


def _candidate_fits(parts: list[str], next_part: str, budget: int) -> bool:
    return estimate_tokens("".join((*parts, next_part))) <= budget


def _budget_for(pack: ContextPackConfig) -> int:
    return pack.token_budget or DEFAULT_CONTEXT_PACK_TOKEN_BUDGET


def _budget_error(result: ContextPackResult) -> ToolExecutionError:
    excess_tokens = result.token_count - result.budget
    return ToolExecutionError(
        build_error(
            ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET,
            details={
                "pack_name": result.pack_name,
                "current_token_count": result.token_count,
                "budget": result.budget,
                "excess_tokens": excess_tokens,
                "files_included": list(result.files_included),
                "missing_files": list(result.missing_files),
                "warnings": list(result.warnings),
                "suggestion": (
                    "Use a smaller pack or call get_context_pack with "
                    "strict_budget=false."
                ),
            },
        )
    )


def _truncation_rank_key(
    vault_path: str,
    rank_by_path: dict[str, float],
    order_by_path: dict[str, int],
) -> tuple[int, float, int]:
    order = order_by_path[vault_path]
    indexed_rank = rank_by_path.get(vault_path)
    if indexed_rank is not None:
        return (0, indexed_rank, order)
    return (1, 0.0, order)


def _stale_warnings(
    documents: tuple[_PackDocument, ...],
    index_queries: IndexQueries,
) -> tuple[str, ...]:
    indexed_at_by_path = index_queries.indexed_at(
        tuple(document.vault_path for document in documents)
    )
    warnings: list[str] = []
    for document in documents:
        indexed_at = indexed_at_by_path.get(document.vault_path)
        indexed_at_ns = _indexed_at_to_ns(indexed_at) if indexed_at else None
        if indexed_at_ns is None:
            continue
        if document.absolute_path.stat().st_mtime_ns > indexed_at_ns:
            warnings.append(STALE_WARNING_TEMPLATE.format(path=document.vault_path))
    return tuple(warnings)


def _with_near_budget_warning(result: ContextPackResult) -> ContextPackResult:
    if result.budget <= 0 or result.token_count <= result.budget * NEAR_BUDGET_RATIO:
        return result

    warning = (
        f"Context pack '{result.pack_name}' is near its token budget: "
        f"{result.token_count}/{result.budget} tokens."
    )
    if warning in result.warnings:
        return result
    return replace(result, warnings=(*result.warnings, warning))


def _contains_glob(pattern: str) -> bool:
    return any(character in pattern for character in _GLOB_CHARS)


def _normalize_vault_reference(value: str) -> str:
    return value.replace("\\", "/").lstrip("/")


def _is_unsafe_pattern(pattern: str) -> bool:
    path = PurePath(pattern)
    return path.is_absolute() or ".." in path.parts


def _has_symlink_segment(vault_root: Path, path: Path) -> bool:
    try:
        relative_parts = path.relative_to(vault_root).parts
    except ValueError:
        return True

    current = vault_root
    for part in relative_parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()


def _normalize_heading_name(value: str) -> str:
    return _clean_heading_text(value.lstrip("#").strip()).casefold()


def _clean_heading_text(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def _ranking_query(pack: ContextPackConfig) -> str:
    terms: list[str] = []
    for pattern in pack.paths:
        terms.extend(re.findall(r"[A-Za-z0-9_/-]+", pattern))
    normalized_terms = []
    for term in terms:
        for piece in re.split(r"[/_.-]+", term):
            if piece and piece not in {"md"}:
                normalized_terms.append(piece)
    unique_terms = tuple(dict.fromkeys(normalized_terms))
    return " OR ".join(_quote_fts_term(term) for term in unique_terms)


def _quote_fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def _indexed_at_to_ns(value: str) -> int | None:
    match = _ISO_TIMESTAMP_RE.match(value)
    if match is None:
        return None

    fraction = match.group("fraction") or ""
    zone = match.group("zone") or ""
    normalized_zone = "+00:00" if zone == "Z" else zone
    parse_fraction = fraction[:6].ljust(6, "0") if fraction else ""
    parse_value = match.group("head")
    if parse_fraction:
        parse_value = f"{parse_value}.{parse_fraction}"
    parse_value = f"{parse_value}{normalized_zone}"

    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed_utc = parsed.astimezone(UTC)
    whole_second = parsed_utc.replace(microsecond=0)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = whole_second - epoch
    seconds = delta.days * 86_400 + delta.seconds
    fractional_ns = int(fraction[:9].ljust(9, "0")) if fraction else 0
    return seconds * 1_000_000_000 + fractional_ns
