# Release Checklist

Run these commands before tagging a GitHub release:

```powershell
uv run ruff check
uv run mypy --strict src
uv run python scripts/radon_gate.py
uv run pytest --cov=obsidian_memory_mcp --cov-report=term-missing --cov-report=xml --cov-fail-under=80 tests
uv run pytest tests/release
uv run mcp-memory benchmark relevance C:\path\to\fixture-vault --queries tests/benchmarks/benchmark-queries.yaml --min-accuracy 0.80
```

The benchmark command requires a valid `memory-mcp.yaml` and a built index. The release tests create isolated fixture vaults automatically.

## Acceptance Traceability

| Phase | Release coverage |
|---|---|
| Phase 0: contracts and schemas | `tests/unit/test_contracts.py`, `tests/release/test_runtime_contract.py` compares `TOOL_CONTRACTS` with live FastMCP schemas. |
| Phase 1: config loading, vault boundaries, guardrails | `tests/unit/test_config_validation.py`, `tests/unit/test_guardrails.py`, `tests/unit/test_path_traversal.py`. |
| Phase 2A: MCP initialize, tool discovery, runtime call | `tests/release/test_runtime_contract.py` uses the in-process MCP memory transport. |
| Phase 2: indexing, hash deduplication, FTS creation | `tests/unit/test_indexer.py`, `tests/integration/test_indexing_workflow.py`. |
| Phase 3: read/search tools, latency, relevance | `tests/integration/test_retrieval_tools.py`, `tests/release/test_relevance_benchmark.py`, `tests/benchmarks/benchmark-queries.yaml`. |
| Phase 4: context packs, token caps, strict budget | `tests/unit/test_context_packs.py`, `tests/unit/test_context_pack_truncation.py`, `tests/integration/test_context_pack_tools.py`. |
| Phase 5: direct writes, audit trail, supersession | `tests/unit/test_write_service.py`, `tests/unit/test_write_audit.py`, `tests/unit/test_supersession_service.py`, `tests/integration/test_write_tools.py`. |

## GitHub Release Steps

Tag only after feature work is merged to `main` and the quality gates above pass.

| Tag | Purpose |
|-----|---------|
| `v0.2.0-rc.1` | Pre-release on GitHub; run the full quality gates table and fixture benchmarks |
| `v0.2.0` | Final release after RC validation |

1. Confirm CI is green on `main`.
2. Confirm `CHANGELOG.md` has release notes and known limitations.
3. Confirm `pyproject.toml` version is the intended tag version.
4. Create a signed or annotated tag, for example `v0.1.0`.
5. Create a GitHub release using the changelog section as release notes.
6. Do not publish to PyPI for the MVP.

## Versioning Policy

The project uses semantic versioning. Before `1.0.0`, minor versions may include breaking changes if release notes call them out. After `1.0.0`, breaking MCP tool signature changes or config schema changes require a major version bump.

The current config schema is supported for the `0.1.x` line. Config migration tooling is out of scope until a real schema migration exists.
