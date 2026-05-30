# Sample vault fixture

This tree backs integration tests, release benchmarks, and local debugging. Paths and
guardrails mirror a realistic `memory-mcp.yaml` setup.

## Historical docs

Several files under `wiki/api/` and `memory-workflow/` still describe the **removed
proposal workflow** (v0.1). They remain as markdown corpus for search and indexing
tests only. The live MCP API exposes nine direct-write tools; see
[docs/tool-reference.md](../../../docs/tool-reference.md).

## Layout

- `wiki/` — public documentation-style notes used by search and context-pack tests
- `wiki/private/` — denied by sample read guardrails (path exclusion tests)
- `Memory/` — empty in git (`.gitkeep` only); manual UAT writes `uat-*.md` here (gitignored)
- `memory-workflow/` — memory lifecycle examples
- `archive/` — deprecated schema samples for migration tests

## Manual UAT vs CI

Committed content is the stable baseline. When you run a manual UAT cycle against this
tree, ephemeral files (`memory-mcp.yaml`, `Memory/uat-*.md`, `wiki/**/uat-*.md`, SQLite
indexes) are listed in `.gitignore` so they do not pollute the next release's run.

Automated tests copy this tree into a temp directory and generate `memory-mcp.yaml` via
`tests/fixtures/sample_vault.py`, so CI does not depend on local UAT artifacts.
