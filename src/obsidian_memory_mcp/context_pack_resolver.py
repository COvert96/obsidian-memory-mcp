"""Context-pack declaration resolution and document selection."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from pathlib import Path, PurePath

from obsidian_memory_mcp.config import (
    ContextPackConfig,
    GuardrailEvaluator,
    ProjectConfig,
)
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.markdown_parser import (
    find_headings,
    normalize_heading_name,
    section_end_index,
)
from obsidian_memory_mcp.vault import parse_frontmatter

_GLOB_CHARS = frozenset("*?[")


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
class _DocumentCandidate:
    vault_path: str
    absolute_path: Path


@dataclass(frozen=True)
class _ReadDocumentResult:
    document: PackDocument | None
    warnings: tuple[str, ...]
    tag_filtered_file: str | None = None


@dataclass(frozen=True)
class _ExplicitPathResolution:
    absolute_path: Path | None = None
    missing_file: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class _SelectedContent:
    content: str
    fragments: tuple[str, ...]
    warnings: tuple[str, ...]


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
        return Resolution(
            documents=resolved.documents,
            missing_files=tuple(missing_files),
            warnings=resolved.warnings,
            tag_filtered_files=resolved.tag_filtered_files,
        )

    def _explicit_path(self, pattern: str) -> _ExplicitPathResolution:
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
    ) -> Resolution:
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
        document=PackDocument(
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
        name
        for name in section_names
        if normalize_heading_name(name) not in found
    )
    return tuple(selected), missing


def _split_complete_sections(content: str) -> tuple[str, ...]:
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
