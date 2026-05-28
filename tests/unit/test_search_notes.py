from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.retrieval import SearchService


def _service(vault: Path) -> SearchService:
    config = ConfigLoader(vault).load()
    run_index(config, mode=IndexMode.FULL)
    return SearchService(config)


def test_search_notes_uses_heading_weighted_bm25_and_returns_result_metadata(
    vault_root: Path,
) -> None:
    (vault_root / "wiki" / "heading.md").write_text(
        "---\ntags: [compliance]\n---\n# Compliance\nGovernance evidence overview.",
        encoding="utf-8",
    )
    (vault_root / "wiki" / "body.md").write_text(
        "---\ntags: [governance]\n---\n# Governance\nCompliance appears in body text.",
        encoding="utf-8",
    )

    result = _service(vault_root).search("compliance", limit=5)

    assert result["query"] == "compliance"
    assert result["returned_count"] >= 2
    assert result["results"][0]["file_path"] == "wiki/heading.md"
    assert result["results"][0]["heading"] == "Compliance"
    assert result["results"][0]["heading_level"] == 1
    assert "compliance" in result["results"][0]["preview"].lower()
    assert isinstance(result["results"][0]["rank"], float)
    assert result["results"][0]["tags"] == ["compliance"]


def test_search_notes_filters_by_all_tags_include_paths_and_exclude_paths(
    vault_root: Path,
) -> None:
    (vault_root / "wiki" / "api").mkdir()
    (vault_root / "wiki" / "private").mkdir()
    (vault_root / "wiki" / "api" / "urgent.md").write_text(
        "---\ntags: [API, urgent]\n---\n# API\ncompliance filter target",
        encoding="utf-8",
    )
    (vault_root / "wiki" / "api" / "normal.md").write_text(
        "---\ntags: [api]\n---\n# API\ncompliance normal target",
        encoding="utf-8",
    )
    (vault_root / "wiki" / "private" / "urgent.md").write_text(
        "---\ntags: [api, urgent]\n---\n# Private\ncompliance private target",
        encoding="utf-8",
    )
    (vault_root / "wiki" / "untagged.md").write_text(
        "# Untagged\ncompliance untagged target",
        encoding="utf-8",
    )

    result = _service(vault_root).search(
        "compliance",
        limit=10,
        tags=["#urgent", "api"],
        paths=["wiki/**"],
        exclude_paths=["wiki/private/**"],
    )

    assert [item["file_path"] for item in result["results"]] == ["wiki/api/urgent.md"]


def test_search_notes_path_glob_requires_separator_for_mid_path_double_star(
    vault_root: Path,
) -> None:
    (vault_root / "wiki" / "sub" / "deep").mkdir(parents=True)
    (vault_root / "wiki" / "test.md").write_text("# Root\nneedle", encoding="utf-8")
    (vault_root / "wiki" / "sub" / "test.md").write_text(
        "# Sub\nneedle", encoding="utf-8"
    )
    (vault_root / "wiki" / "sub" / "deep" / "test.md").write_text(
        "# Deep\nneedle", encoding="utf-8"
    )
    (vault_root / "wiki" / "badtest.md").write_text("# Bad\nneedle", encoding="utf-8")

    result = _service(vault_root).search(
        "needle",
        limit=10,
        paths=["wiki/**/test.md"],
    )

    assert [item["file_path"] for item in result["results"]] == [
        "wiki/sub/deep/test.md",
        "wiki/sub/test.md",
        "wiki/test.md",
    ]


def test_search_notes_supports_multi_word_and_regex_queries(vault_root: Path) -> None:
    (vault_root / "wiki" / "exact.md").write_text(
        "# Evidence\ncomplex query compliance evidence arrives here",
        encoding="utf-8",
    )
    (vault_root / "wiki" / "near.md").write_text(
        "# Evidence\ncomplex query compliance policy evidence arrives here",
        encoding="utf-8",
    )
    service = _service(vault_root)

    multi_word = service.search("complex query", limit=10)
    regex = service.search(r"/compliance\s+evidence/", limit=10)

    assert {item["file_path"] for item in multi_word["results"]} >= {
        "wiki/exact.md",
        "wiki/near.md",
    }
    assert [item["file_path"] for item in regex["results"]] == ["wiki/exact.md"]


def test_search_notes_rejects_empty_query(vault_root: Path) -> None:
    with pytest.raises(ToolExecutionError) as exc_info:
        _service(vault_root).search("   ")

    assert exc_info.value.error.code is ErrorCode.ERR_INVALID_REQUEST
    assert exc_info.value.error.message == "query is required"


def test_search_notes_reports_missing_index_without_bootstrapping(
    vault_root: Path,
) -> None:
    service = SearchService(ConfigLoader(vault_root).load())

    with pytest.raises(ToolExecutionError) as exc_info:
        service.search("concept")

    assert exc_info.value.error.code is ErrorCode.ERR_INTERNAL
    assert exc_info.value.error.message == (
        "Search index has not been built for this project."
    )


def test_search_notes_rejects_invalid_limit_and_malformed_regex(
    vault_root: Path,
) -> None:
    service = _service(vault_root)

    with pytest.raises(ToolExecutionError) as invalid_limit:
        service.search("concept", limit=0)
    with pytest.raises(ToolExecutionError) as malformed_regex:
        service.search("/[unclosed/")

    assert invalid_limit.value.error.message == "limit must be a positive integer"
    assert malformed_regex.value.error.message.startswith("invalid regex query:")


def test_search_notes_caps_large_limit(vault_root: Path) -> None:
    for index in range(105):
        (vault_root / "wiki" / f"limit-{index:03}.md").write_text(
            f"# Limit {index:03}\nneedle",
            encoding="utf-8",
        )

    result = _service(vault_root).search("needle", limit=1_000)

    assert result["returned_count"] == 100
