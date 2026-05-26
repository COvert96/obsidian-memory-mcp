from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexer import IndexMode, run_index
from obsidian_memory_mcp.search_debug import (
    DebugSearchError,
    debug_search,
    search_results_to_json,
)


def _config(vault: Path):
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )
    return ConfigLoader(vault).load()


def test_debug_search_returns_canonical_metadata_snippet_score_and_filters(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "archive").mkdir()
    (vault / "wiki" / "alpha.md").write_text(
        "---\ntags: [project]\n---\n# Alpha\nsearchable compliance note",
        encoding="utf-8",
    )
    (vault / "archive" / "beta.md").write_text(
        "# Beta\nsearchable archived note", encoding="utf-8"
    )
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    all_results = debug_search(config, "searchable", limit=10)
    path_results = debug_search(config, "searchable", limit=10, path="wiki/")
    tag_results = debug_search(config, "searchable", limit=10, tag="project")
    json_payload = search_results_to_json("searchable", tag_results)

    assert {result.vault_path for result in all_results} == {
        "wiki/alpha.md",
        "archive/beta.md",
    }
    assert [result.vault_path for result in path_results] == ["wiki/alpha.md"]
    assert [result.vault_path for result in tag_results] == ["wiki/alpha.md"]
    assert tag_results[0].block_key.startswith("wiki/alpha.md#alpha#1::block-")
    assert tag_results[0].heading == "Alpha"
    assert isinstance(tag_results[0].bm25_score, float)
    assert "searchable" in tag_results[0].snippet
    assert tag_results[0].token_count_estimate > 0
    assert '"query": "searchable"' in json_payload


def test_debug_search_orders_lowest_bm25_first_as_most_relevant(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "strong.md").write_text(
        "# Strong\nneedle needle needle filler filler filler",
        encoding="utf-8",
    )
    (vault / "weak.md").write_text(
        "# Weak\nneedle filler filler filler filler filler",
        encoding="utf-8",
    )
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    results = debug_search(config, "needle", limit=10)

    assert [result.vault_path for result in results[:2]] == ["strong.md", "weak.md"]
    assert results[0].bm25_score < results[1].bm25_score


def test_debug_search_rejects_malformed_fts_query(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\nbody", encoding="utf-8")
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    with pytest.raises(DebugSearchError, match="Invalid debug search query"):
        debug_search(config, "AND")


def test_path_filter_treats_like_metacharacters_as_literal_path_characters(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "client_projects").mkdir(parents=True)
    (vault / "clientXprojects").mkdir()
    (vault / "literal%path").mkdir()
    (vault / "literalXpath").mkdir()
    (vault / "client_projects" / "alpha.md").write_text("# A\nneedle", encoding="utf-8")
    (vault / "clientXprojects" / "beta.md").write_text("# B\nneedle", encoding="utf-8")
    (vault / "literal%path" / "gamma.md").write_text("# C\nneedle", encoding="utf-8")
    (vault / "literalXpath" / "delta.md").write_text("# D\nneedle", encoding="utf-8")
    config = _config(vault)
    run_index(config, mode=IndexMode.FULL)

    underscore_results = debug_search(config, "needle", path="client_projects/")
    percent_results = debug_search(config, "needle", path="literal%path/")

    assert [result.vault_path for result in underscore_results] == [
        "client_projects/alpha.md"
    ]
    assert [result.vault_path for result in percent_results] == [
        "literal%path/gamma.md"
    ]
