"""Context-pack token-budget enforcement."""

from __future__ import annotations

import re
from dataclasses import replace

from obsidian_memory_mcp.config import ContextPackConfig
from obsidian_memory_mcp.context_packs._models import (
    ContextPackResult,
    IndexQueries,
    PackDocument,
)
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.retrieval._fts_query import quote_fts_term
from obsidian_memory_mcp.tokens import estimate_tokens

NEAR_BUDGET_RATIO = 0.9


class BudgetEnforcer:
    """Apply strict and soft context-pack token budgets."""

    def __init__(self, index_queries: IndexQueries):
        self._index_queries = index_queries

    def enforce(
        self,
        result: ContextPackResult,
        documents: tuple[PackDocument, ...],
        pack: ContextPackConfig,
        *,
        strict_budget: bool,
    ) -> ContextPackResult:
        if result.token_count <= result.budget:
            return with_near_budget_warning(result)
        if strict_budget:
            raise _budget_error(result)
        return with_near_budget_warning(
            self._truncate_to_budget(result, documents, pack)
        )

    def _truncate_to_budget(
        self,
        result: ContextPackResult,
        documents: tuple[PackDocument, ...],
        pack: ContextPackConfig,
    ) -> ContextPackResult:
        ranked_documents = self._rank_for_truncation(pack, result, documents)
        content, included_paths = _emit_truncated_content(
            ranked_documents,
            result.budget,
        )
        return _truncation_result(result, content, included_paths)

    def _rank_for_truncation(
        self,
        pack: ContextPackConfig,
        result: ContextPackResult,
        documents: tuple[PackDocument, ...],
    ) -> tuple[PackDocument, ...]:
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


def format_documents(documents: tuple[PackDocument, ...]) -> str:
    return "".join(format_document(document) for document in documents)


def format_document(document: PackDocument) -> str:
    return format_fragment(document.vault_path, document.content)


def format_fragment(vault_path: str, content: str) -> str:
    return f"<!-- From: {vault_path} -->\n{content}\n\n"


def with_near_budget_warning(result: ContextPackResult) -> ContextPackResult:
    if result.budget <= 0 or result.token_count <= result.budget * NEAR_BUDGET_RATIO:
        return result

    warning = (
        f"Context pack '{result.pack_name}' is near its token budget: "
        f"{result.token_count}/{result.budget} tokens."
    )
    if warning in result.warnings:
        return result
    return replace(result, warnings=(*result.warnings, warning))


def _emit_truncated_content(
    ranked_documents: tuple[PackDocument, ...],
    budget: int,
) -> tuple[str, set[str]]:
    emitted_parts: list[str] = []
    included_paths: set[str] = set()

    for document in ranked_documents:
        full_part = format_document(document)
        if _candidate_fits(emitted_parts, full_part, budget):
            emitted_parts.append(full_part)
            included_paths.add(document.vault_path)
            continue

        for fragment in document.fragments:
            fragment_part = format_fragment(document.vault_path, fragment)
            if _candidate_fits(emitted_parts, fragment_part, budget):
                emitted_parts.append(fragment_part)
                included_paths.add(document.vault_path)
            else:
                break

    return "".join(emitted_parts), included_paths


def _truncation_result(
    result: ContextPackResult,
    content: str,
    included_paths: set[str],
) -> ContextPackResult:
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


def _candidate_fits(parts: list[str], next_part: str, budget: int) -> bool:
    return estimate_tokens("".join((*parts, next_part))) <= budget


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
    return " OR ".join(quote_fts_term(term) for term in unique_terms)
