from __future__ import annotations

from obsidian_memory_mcp.config import (
    ConfigValidationError,
    ConfigValidationException,
    ConfigValidator,
    ProjectConfig,
)
from obsidian_memory_mcp.config.validation import _errors, _parsers, _validator
from obsidian_memory_mcp.context_packs import ContextPackLoader, ContextPackResult
from obsidian_memory_mcp.context_packs.budget import BudgetEnforcer
from obsidian_memory_mcp.context_packs.loader import SqliteIndexQueries
from obsidian_memory_mcp.context_packs.models import DEFAULT_CONTEXT_PACK_TOKEN_BUDGET
from obsidian_memory_mcp.context_packs.resolver import ContextPackResolver
from obsidian_memory_mcp.indexing import (
    IndexMode,
    IndexRunResult,
    discover_markdown_files,
    run_index,
)
from obsidian_memory_mcp.indexing import repository as indexing_repository
from obsidian_memory_mcp.indexing import service as indexing_service
from obsidian_memory_mcp.indexing._models import FileCandidate
from obsidian_memory_mcp.proposals import (
    ProposalManager,
    ProposalOperation,
    ProposalStatus,
)
from obsidian_memory_mcp.proposals import repository as proposal_repository
from obsidian_memory_mcp.retrieval import (
    ReadNoteService,
    ReadSectionService,
    SearchService,
)
from obsidian_memory_mcp.retrieval import readers as retrieval_readers
from obsidian_memory_mcp.retrieval import search as retrieval_search


def test_context_pack_features_are_grouped_under_context_packs_package() -> None:
    assert ContextPackLoader is not None
    assert ContextPackResult is not None
    assert BudgetEnforcer is not None
    assert ContextPackResolver is not None
    assert SqliteIndexQueries is not None
    assert DEFAULT_CONTEXT_PACK_TOKEN_BUDGET > 0


def test_project_config_defaults_are_owned_by_the_model() -> None:
    assert ProjectConfig.CONFIG_FILE_NAME == "memory-mcp.yaml"
    assert ProjectConfig.DEFAULT_TAGS_SEPARATOR == ","
    assert ProjectConfig.DEFAULT_MAX_PROPOSAL_TTL_HOURS == 24
    assert ProjectConfig.DEFAULT_PROPOSAL_TTL_SECONDS == 3600
    assert ProjectConfig.DEFAULT_MAX_PROPOSAL_CONTENT_BYTES == 1024 * 1024


def test_indexing_features_are_grouped_under_indexing_package() -> None:
    assert run_index is not None
    assert discover_markdown_files is not None
    assert IndexMode is not None
    assert IndexRunResult is not None
    assert FileCandidate is not None
    assert indexing_service is not None
    assert indexing_repository is not None


def test_retrieval_features_are_grouped_under_retrieval_package() -> None:
    assert ReadNoteService is not None
    assert ReadSectionService is not None
    assert SearchService is not None
    assert retrieval_readers is not None
    assert retrieval_search is not None


def test_proposal_features_are_grouped_under_proposals_package() -> None:
    assert ProposalManager is not None
    assert ProposalOperation.CREATE == "create"
    assert ProposalStatus.PENDING == "pending"
    assert proposal_repository is not None


def test_config_validation_features_are_grouped_under_validation_package() -> None:
    assert ConfigValidator is not None
    assert ConfigValidationError is not None
    assert ConfigValidationException is not None
    assert _validator is not None
    assert _parsers is not None
    assert _errors is not None
