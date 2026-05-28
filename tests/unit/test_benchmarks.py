from __future__ import annotations

from pathlib import Path

from obsidian_memory_mcp.benchmarks import evaluate_relevance_benchmark
from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index


def _write_config(vault: Path) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["wiki/**/*.md"]
write_constraints:
  read:
    allow: ["wiki/**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )


def test_relevance_benchmark_reports_query_results_and_accuracy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.joinpath("wiki").mkdir(parents=True)
    vault.joinpath(".mcp").mkdir()
    vault.joinpath("wiki", "search.md").write_text(
        "# Search\nSQLite FTS ranking supports deterministic search results.",
        encoding="utf-8",
    )
    vault.joinpath("wiki", "proposal.md").write_text(
        "# Proposal\nApproval workflow keeps memory writes reviewable.",
        encoding="utf-8",
    )
    _write_config(vault)
    benchmark_path = tmp_path / "queries.yaml"
    benchmark_path.write_text(
        """
queries:
  - id: search-ranking
    query: "SQLite FTS ranking"
    expected:
      - path: "wiki/search.md"
        section: "Search"
    explanation: "Search design content should be ranked first."
  - id: proposal-approval
    query: "approval workflow"
    expected:
      - path: "wiki/proposal.md"
        section: "Proposal"
    explanation: "Proposal workflow content should be ranked first."
""",
        encoding="utf-8",
    )

    config = ConfigLoader(vault).load()
    run_index(config, mode=IndexMode.FULL)

    report = evaluate_relevance_benchmark(config, benchmark_path, top_k=3)

    assert report.total_queries == 2
    assert report.passed_queries == 2
    assert report.accuracy == 1.0
    assert [result.query_id for result in report.results] == [
        "search-ranking",
        "proposal-approval",
    ]
