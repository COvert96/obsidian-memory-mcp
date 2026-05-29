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

### Automated release (GitHub Actions)

Pushing a tag matching `v*` triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml):

1. Runs the same [quality gates](../.github/workflows/quality-gates.yml) as CI (Ubuntu + Windows).
2. Verifies the tag maps to `pyproject.toml` `project.version` (`scripts/verify_release_tag.py`).
3. Copies the matching `CHANGELOG.md` section into `release-notes.md` (`scripts/extract_changelog.py`).
4. Creates a GitHub Release (marked **pre-release** when the tag contains `-rc`).

Manual steps before tagging:

1. Confirm CI is green on the release branch.
2. Add a `CHANGELOG.md` section whose heading starts with the tag version (for example `## 0.2.0-rc.1 - 2026-05-29`). The workflow uses that section as the release body.
3. Set `pyproject.toml` `version` to the PEP 440 form of the tag (`v0.2.0-rc.1` → `0.2.0rc1`).
4. Run `uv lock` and `uv sync` so `uv.lock` matches `pyproject.toml`.
5. Push an annotated tag, for example `git tag -a v0.2.0-rc.1 -m "0.2.0-rc.1"` then `git push origin v0.2.0-rc.1`.

Do not publish to PyPI for the MVP.

### Local dry-run (optional)

```powershell
uv run python scripts/verify_release_tag.py v0.2.0-rc.1
uv run python scripts/extract_changelog.py v0.2.0-rc.1
Get-Content release-notes.md
```

## Versioning Policy

The project uses semantic versioning. Before `1.0.0`, minor versions may include breaking changes if release notes call them out. After `1.0.0`, breaking MCP tool signature changes or config schema changes require a major version bump.

The **0.2.x** config schema drops proposal-era keys; `mcp-memory migrate` applies Alembic migration 002. Upgrading from **0.1.x** indexes is documented in [migration-guide.md](migration-guide.md).
