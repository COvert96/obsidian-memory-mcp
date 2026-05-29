"""Context pack loading service and index-query adapters."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from obsidian_memory_mcp.config import ContextPackConfig, ProjectConfig
from obsidian_memory_mcp.context_packs._budget import (
    BudgetEnforcer,
    format_documents,
    with_near_budget_warning,
)
from obsidian_memory_mcp.context_packs._models import (
    DEFAULT_CONTEXT_PACK_TOKEN_BUDGET,
    ContextPackResult,
    ContextPackSummary,
    IndexQueries,
    PackDocument,
)
from obsidian_memory_mcp.context_packs._index_queries import SqliteIndexQueries
from obsidian_memory_mcp.context_packs._resolver import ContextPackResolver
from obsidian_memory_mcp.tokens import estimate_tokens

STALE_WARNING_TEMPLATE = (
    "File '{path}' has been modified since last index; content may be stale. "
    "Re-run indexing to refresh."
)

_ISO_TIMESTAMP_RE = re.compile(
    r"^(?P<head>.*?)(?:\.(?P<fraction>\d+))?(?P<zone>Z|[+-]\d{2}:\d{2})?$"
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
        self._configured_packs = config.context_packs
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
        result, documents, pack = self._resolved_result(pack_name)
        return self._budget_enforcer.enforce(
            result,
            documents,
            pack,
            strict_budget=strict_budget,
        )

    def inspect(self, pack_name: str) -> ContextPackResult:
        result, _documents, _pack = self._resolved_result(pack_name)
        return with_near_budget_warning(result)

    def list_packs(self) -> tuple[ContextPackSummary, ...]:
        return tuple(_pack_summary(pack) for pack in self._configured_packs)

    def _resolved_result(
        self,
        pack_name: str,
    ) -> tuple[ContextPackResult, tuple[PackDocument, ...], ContextPackConfig]:
        resolved_pack = self._resolver.resolve(pack_name)
        documents = resolved_pack.resolution.documents
        content = format_documents(documents)
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


def _budget_for(pack: ContextPackConfig) -> int:
    return pack.token_budget or DEFAULT_CONTEXT_PACK_TOKEN_BUDGET


def _pack_summary(pack: ContextPackConfig) -> ContextPackSummary:
    return ContextPackSummary(
        pack_name=pack.name,
        description=pack.description,
        token_budget=_budget_for(pack),
        path_patterns=pack.paths,
        sections=pack.sections,
        tags_filter=pack.tags_filter,
        include_context_packs=pack.include_context_packs,
    )


def _stale_warnings(
    documents: tuple[PackDocument, ...],
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


def _indexed_at_to_ns(value: str) -> int | None:
    match = _ISO_TIMESTAMP_RE.match(value)
    if match is None:
        return None

    parse_value = _iso_timestamp_for_parse(match)

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
    fraction = match.group("fraction") or ""
    fractional_ns = int(fraction[:9].ljust(9, "0")) if fraction else 0
    return seconds * 1_000_000_000 + fractional_ns


def _iso_timestamp_for_parse(match: re.Match[str]) -> str:
    fraction = match.group("fraction") or ""
    zone = match.group("zone") or ""
    normalized_zone = "+00:00" if zone == "Z" else zone
    parse_fraction = fraction[:6].ljust(6, "0") if fraction else ""
    parse_value = match.group("head")
    if parse_fraction:
        parse_value = f"{parse_value}.{parse_fraction}"
    return f"{parse_value}{normalized_zone}"
