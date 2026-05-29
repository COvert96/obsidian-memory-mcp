from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import obsidian_memory_mcp.indexing.repository as indexing_repository
import obsidian_memory_mcp.server as server_module
import obsidian_memory_mcp.writes._audit as writes_audit

from obsidian_memory_mcp.config import (
    ConfigValidationError,
    ConfigValidationException,
    ConfigValidator,
    ProjectConfig,
)
from obsidian_memory_mcp.context_packs import (
    DEFAULT_CONTEXT_PACK_TOKEN_BUDGET,
    ContextPackLoader,
    ContextPackResult,
    ContextPackSummary,
    SqliteIndexQueries,
)
from obsidian_memory_mcp.contracts import TOOL_CONTRACTS, ToolContract
from obsidian_memory_mcp.indexing import (
    FileCandidate,
    IndexMode,
    IndexRunResult,
    discover_markdown_files,
    run_index,
)
from obsidian_memory_mcp.markdown import parse_frontmatter
from obsidian_memory_mcp.retrieval import (
    ReadNoteService,
    ReadSectionService,
    SearchService,
)
from obsidian_memory_mcp.utils import duration_ms, normalize_vault_path


def test_context_pack_features_are_grouped_under_context_packs_package() -> None:
    assert ContextPackLoader is not None
    assert ContextPackResult is not None
    assert ContextPackSummary is not None
    assert SqliteIndexQueries is not None
    assert DEFAULT_CONTEXT_PACK_TOKEN_BUDGET > 0


def test_project_config_defaults_are_owned_by_the_model() -> None:
    assert ProjectConfig.CONFIG_FILE_NAME == "memory-mcp.yaml"
    assert ProjectConfig.DEFAULT_TAGS_SEPARATOR == ","
    assert ProjectConfig.DEFAULT_MAX_WRITE_CONTENT_BYTES == 1024 * 1024
    assert ProjectConfig.DEFAULT_MEMORY_ARCHIVE_PATH == "Memory/archive"


def test_indexing_features_are_grouped_under_indexing_package() -> None:
    assert run_index is not None
    assert discover_markdown_files is not None
    assert IndexMode is not None
    assert IndexRunResult is not None
    assert FileCandidate is not None


def test_retrieval_features_are_grouped_under_retrieval_package() -> None:
    assert ReadNoteService is not None
    assert ReadSectionService is not None
    assert SearchService is not None


def test_config_validation_features_are_grouped_under_validation_package() -> None:
    assert ConfigValidator is not None
    assert ConfigValidationError is not None
    assert ConfigValidationException is not None


def test_shared_packages_expose_public_apis() -> None:
    assert parse_frontmatter is not None
    assert normalize_vault_path is not None
    assert duration_ms is not None
    assert TOOL_CONTRACTS
    assert ToolContract is not None


def test_domain_packages_use_underscore_models_module() -> None:
    for package_name in ("config", "context_packs", "indexing", "writes"):
        module = importlib.import_module(f"obsidian_memory_mcp.{package_name}")
        assert hasattr(module, "__all__")
        models = importlib.import_module(f"obsidian_memory_mcp.{package_name}._models")
        assert models.__file__ is not None

    parser_models = importlib.import_module(
        "obsidian_memory_mcp.indexing.parser._models"
    )
    assert parser_models.__file__ is not None


def test_internal_submodules_are_not_reexported_at_package_root() -> None:
    config = importlib.import_module("obsidian_memory_mcp.config")
    assert "GuardrailEvaluator" in config.__all__
    assert "ProjectConfig" in config.__all__

    utils = importlib.import_module("obsidian_memory_mcp.utils")
    assert "_glob" not in utils.__all__
    assert "normalize_glob" in utils.__all__


def test_no_flat_duplicate_top_level_helper_modules() -> None:
    package = importlib.import_module("obsidian_memory_mcp")
    top_level_modules = {
        name
        for _finder, name, ispkg in pkgutil.iter_modules(package.__path__)
        if not ispkg
    }
    retired = {
        "glob_utils",
        "hashing",
        "paths",
        "wikilinks",
        "markdown_fence",
        "markdown_frontmatter",
        "markdown_parser",
        "contract_examples",
        "vault",
        "_time",
    }
    assert retired.isdisjoint(top_level_modules)


def test_adapters_do_not_import_internal_write_modules() -> None:
    """Keep package boundaries honest: adapters should use public package APIs."""
    server_source = Path(server_module.__file__).read_text(encoding="utf-8")
    assert "obsidian_memory_mcp.writes._service" not in server_source


def test_domain_modules_do_not_import_database_tables_module_directly() -> None:
    """`database._tables` is an internal detail; import from `database` instead."""
    repository_source = Path(indexing_repository.__file__).read_text(encoding="utf-8")
    audit_source = Path(writes_audit.__file__).read_text(encoding="utf-8")

    assert "obsidian_memory_mcp.database._tables" not in repository_source
    assert "obsidian_memory_mcp.database._tables" not in audit_source
