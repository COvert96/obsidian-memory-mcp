"""CLI formatting helpers for context-pack commands."""

from __future__ import annotations

from obsidian_memory_mcp.context_packs import ContextPackResult


def print_context_pack_summary(
    result: ContextPackResult,
    *,
    duration_ms: int,
) -> None:
    print("Files included:")
    for path in result.files_included:
        print(f"  - {path}")
    print(f"Token count: {result.token_count}")
    print("Missing files:")
    if result.missing_files:
        for path in result.missing_files:
            print(f"  - {path}")
    else:
        print("  <none>")
    print("Warnings:")
    if result.warnings:
        for warning in result.warnings:
            print(f"  - {warning}")
    else:
        print("  <none>")
    print(f"Duration ms: {duration_ms}")


def pack_issue_summary(result: ContextPackResult) -> str:
    issues: list[str] = []
    if result.missing_files:
        issues.append(f"{len(result.missing_files)} missing")
    if result.warnings:
        issues.append(f"{len(result.warnings)} warnings")
    if result.token_count > result.budget:
        issues.append("over budget")
    elif result.token_count > result.budget * 0.9:
        issues.append("near budget")
    return ", ".join(issues) or "none"


def pack_exit_code(result: ContextPackResult) -> int:
    if result.missing_files:
        return 1
    if (
        result.warnings
        or result.token_count > result.budget
        or result.token_count > result.budget * 0.9
    ):
        return 2
    return 0
