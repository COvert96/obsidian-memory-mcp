"""CLI handlers for benchmark commands."""

from __future__ import annotations

import argparse

from obsidian_memory_mcp.benchmarks import (
    evaluate_relevance_benchmark,
    measure_performance_baseline,
    report_as_json,
)
from obsidian_memory_mcp.cli.common import (
    SUBCOMMAND_PERFORMANCE,
    SUBCOMMAND_RELEVANCE,
    load_config,
)


def handle_benchmark_command(arguments: argparse.Namespace) -> int:
    if arguments.benchmark_command == SUBCOMMAND_RELEVANCE:
        return benchmark_relevance(arguments)
    if arguments.benchmark_command == SUBCOMMAND_PERFORMANCE:
        return benchmark_performance(arguments)
    print("Usage: mcp-memory benchmark {relevance|performance} ...")
    return 1


def benchmark_relevance(arguments: argparse.Namespace) -> int:
    config = load_config(arguments.vault_root)
    if config is None:
        return 3
    report = evaluate_relevance_benchmark(
        config,
        arguments.queries,
        top_k=arguments.top_k,
    )
    print(report_as_json(report) if arguments.json else report.as_text())
    return 0 if report.accuracy >= arguments.min_accuracy else 1


def benchmark_performance(arguments: argparse.Namespace) -> int:
    config = load_config(arguments.vault_root)
    if config is None:
        return 3
    baseline = measure_performance_baseline(config)
    print(report_as_json(baseline) if arguments.json else baseline.as_text())
    return 0
