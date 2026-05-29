"""Deterministic benchmark runners for release readiness checks."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from obsidian_memory_mcp.utils import duration_ms
from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.context_packs import ContextPackLoader
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.retrieval import ReadNoteService, SearchService
from obsidian_memory_mcp.config import GuardrailEvaluator
from obsidian_memory_mcp.status import get_index_status
from obsidian_memory_mcp.writes import WriteService

RELEASE_RELEVANCE_THRESHOLD = 0.80


@dataclass(frozen=True)
class ExpectedSearchResult:
    path: str
    section: str | None = None
    block: str | None = None


@dataclass(frozen=True)
class BenchmarkQuery:
    query_id: str
    query: str
    expected: tuple[ExpectedSearchResult, ...]
    explanation: str
    tags: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryBenchmarkResult:
    query_id: str
    query: str
    passed: bool
    expected_paths: tuple[str, ...]
    top_paths: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class RelevanceBenchmarkReport:
    results: tuple[QueryBenchmarkResult, ...]
    top_k: int

    @property
    def total_queries(self) -> int:
        return len(self.results)

    @property
    def passed_queries(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def accuracy(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.passed_queries / self.total_queries

    def as_dict(self) -> dict[str, Any]:
        return {
            "top_k": self.top_k,
            "total_queries": self.total_queries,
            "passed_queries": self.passed_queries,
            "accuracy": self.accuracy,
            "results": [asdict(result) for result in self.results],
        }

    def as_text(self) -> str:
        lines = [
            (
                f"Top-{self.top_k} accuracy: {self.accuracy:.1%} "
                f"({self.passed_queries}/{self.total_queries})"
            )
        ]
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(
                f"{status} {result.query_id}: expected={list(result.expected_paths)} "
                f"top={list(result.top_paths)}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class PerformanceBaseline:
    indexing_ms: int
    search_ms: int
    read_ms: int
    context_pack_ms: int
    write_ms: int
    token_count: int
    indexed_files: int
    index_size_bytes: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    def as_text(self) -> str:
        return "\n".join(
            [
                f"indexing_ms: {self.indexing_ms}",
                f"search_ms: {self.search_ms}",
                f"read_ms: {self.read_ms}",
                f"context_pack_ms: {self.context_pack_ms}",
                f"write_ms: {self.write_ms}",
                f"token_count: {self.token_count}",
                f"indexed_files: {self.indexed_files}",
                f"index_size_bytes: {self.index_size_bytes}",
            ]
        )


def load_benchmark_queries(path: Path) -> tuple[BenchmarkQuery, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = raw.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Benchmark file must contain a non-empty 'queries' list.")
    return tuple(_parse_query(item) for item in queries)


def evaluate_relevance_benchmark(
    config: ProjectConfig,
    benchmark_path: Path,
    *,
    top_k: int = 3,
) -> RelevanceBenchmarkReport:
    service = SearchService(config)
    results: list[QueryBenchmarkResult] = []
    for benchmark_query in load_benchmark_queries(benchmark_path):
        payload = service.search(
            benchmark_query.query,
            limit=top_k,
            tags=list(benchmark_query.tags),
            paths=list(benchmark_query.paths),
            exclude_paths=list(benchmark_query.exclude_paths),
        )
        top_paths = tuple(result["file_path"] for result in payload["results"])
        expected_paths = tuple(expected.path for expected in benchmark_query.expected)
        passed = any(path in top_paths for path in expected_paths)
        results.append(
            QueryBenchmarkResult(
                query_id=benchmark_query.query_id,
                query=benchmark_query.query,
                passed=passed,
                expected_paths=expected_paths,
                top_paths=top_paths,
                explanation=benchmark_query.explanation,
            )
        )
    return RelevanceBenchmarkReport(results=tuple(results), top_k=top_k)


def measure_performance_baseline(config: ProjectConfig) -> PerformanceBaseline:
    started = time.perf_counter()
    run_index(config, mode=IndexMode.FULL)
    indexing_ms = duration_ms(started)

    search_service = SearchService(config)
    started = time.perf_counter()
    search_service.search("proposal workflow", limit=5)
    search_ms = duration_ms(started)

    reader = ReadNoteService(config, GuardrailEvaluator(config))
    started = time.perf_counter()
    reader.read("wiki/architecture/system-overview.md")
    read_ms = duration_ms(started)

    pack_loader = ContextPackLoader(config)
    started = time.perf_counter()
    pack = pack_loader.load(config.context_packs[0].name, strict_budget=False)
    context_pack_ms = duration_ms(started)

    write_service = WriteService(config)
    started = time.perf_counter()
    write_service.create(
        "Memory/performance-baseline.md",
        "# Performance Baseline\nFixture write latency check.\n",
    )
    write_ms = duration_ms(started)

    status = get_index_status(config)
    return PerformanceBaseline(
        indexing_ms=indexing_ms,
        search_ms=search_ms,
        read_ms=read_ms,
        context_pack_ms=context_pack_ms,
        write_ms=write_ms,
        token_count=pack.token_count,
        indexed_files=status.indexed_files,
        index_size_bytes=config.index_db_location.stat().st_size,
    )


def report_as_json(report: RelevanceBenchmarkReport | PerformanceBaseline) -> str:
    return json.dumps(report.as_dict(), indent=2, sort_keys=True)


def _parse_query(raw: object) -> BenchmarkQuery:
    if not isinstance(raw, dict):
        raise ValueError("Each benchmark query must be a mapping.")
    query_id = _required_string(raw, "id")
    query = _required_string(raw, "query")
    explanation = _required_string(raw, "explanation")
    expected_raw = raw.get("expected")
    if not isinstance(expected_raw, list) or not expected_raw:
        raise ValueError(f"Benchmark query '{query_id}' must define expected results.")
    filters = raw.get("filters", {})
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        raise ValueError(f"Benchmark query '{query_id}' filters must be a mapping.")
    return BenchmarkQuery(
        query_id=query_id,
        query=query,
        expected=tuple(_parse_expected(item, query_id) for item in expected_raw),
        explanation=explanation,
        tags=tuple(_string_list(filters, "tags")),
        paths=tuple(_string_list(filters, "paths")),
        exclude_paths=tuple(_string_list(filters, "exclude_paths")),
    )


def _parse_expected(raw: object, query_id: str) -> ExpectedSearchResult:
    if not isinstance(raw, dict):
        raise ValueError(
            f"Benchmark query '{query_id}' expected result must be a mapping."
        )
    return ExpectedSearchResult(
        path=_required_string(raw, "path"),
        section=_optional_string(raw, "section"),
        block=_optional_string(raw, "block"),
    )


def _required_string(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Benchmark field '{key}' must be a non-empty string.")
    return value


def _optional_string(raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Benchmark field '{key}' must be a non-empty string.")
    return value


def _string_list(raw: dict[str, object], key: str) -> list[str]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Benchmark filter '{key}' must be a list of strings.")
    return value
