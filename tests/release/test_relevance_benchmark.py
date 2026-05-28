from __future__ import annotations

import shutil
from pathlib import Path

from obsidian_memory_mcp.benchmarks import evaluate_relevance_benchmark
from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index


FIXTURE_SOURCE = Path(__file__).parents[1] / "fixtures" / "sample-vault"
BENCHMARK_QUERIES = Path(__file__).parents[1] / "benchmarks" / "benchmark-queries.yaml"


def test_sample_vault_relevance_benchmark_meets_release_threshold(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "sample-vault"
    shutil.copytree(FIXTURE_SOURCE, vault)
    vault.joinpath(".mcp").mkdir()
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
    deny: ["wiki/private/**"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )
    config = ConfigLoader(vault).load()
    run_index(config, mode=IndexMode.FULL)

    report = evaluate_relevance_benchmark(config, BENCHMARK_QUERIES, top_k=3)

    assert report.total_queries >= 20
    assert report.accuracy >= 0.80, report.as_text()
