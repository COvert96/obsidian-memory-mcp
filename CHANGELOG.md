# Changelog

## 0.2.0 - 2026-05-29

Direct-write release replacing the proposal workflow.

### Added

- Direct MCP write tools: `write_memory`, `update_memory`, `write_note`, `update_note` with guardrails, optimistic-lock hashes, and append-only `write_audit` logging.
- Supersession support on `update_memory` with archive paths and a single audit row per operation.
- Alembic migration `002_remove_proposals` removing legacy proposal tables.
- Shared `glob_utils`, `markdown_fence`, and `parser/` subpackage for maintainability.
- Radon complexity gate (`scripts/radon_gate.py`) in CI and release documentation.

### Changed

- Documentation, fixture vault samples, and benchmarks aligned with direct writes (no proposal MCP tools).
- CLI organized under the `cli/` package; complexity refactors in search, indexing, config validation, and status reporting.
- Project version set to `0.2.0` (tag `v0.2.0` after merge; use `v0.2.0-rc.1` for pre-release validation).

### Removed

- Proposal MCP tools and SQLite proposal/changeset tables.

### Upgrade Notes

1. Run `uv run mcp-memory migrate {vault}` to apply schema migration 002.
2. Remove deprecated config keys such as `proposal_ttl_seconds` (validator warns if present).
3. Re-index vaults after upgrading parser or schema.

## 0.1.0 - 2026-05-28

Initial MVP GitHub source release.

### Added

- FastMCP server exposing 9 tools for note reads, section reads, search, context packs, and proposal workflow operations.
- SQLite FTS5 indexing and deterministic search relevance benchmark with a 80% top-3 release threshold.
- Proposal-based writes with approval, rejection, stale proposal protection, changesets, and audit trail support.
- In-repository setup, tool, error, architecture, performance, security, contributing, and release documentation.
- GitHub Actions CI for Windows and Linux running lint, type checks, full tests, coverage, and release-gate tests.

### Known Limitations

- GitHub source release only; no PyPI publication.
- No hosted documentation site.
- No embeddings or semantic search; SQLite FTS5 is the MVP search backend.
- Indexing is CLI-driven; no file watcher is included.
- MVP CI covers Windows and Linux. macOS is not advertised as verified for this release.

### Upgrade Notes

This is the first public release. Existing local vaults should create a `memory-mcp.yaml` from `config-example.yaml` and run a full index before use.

### Support

Use GitHub issues for bugs and feature requests. Do not include private vault content, credentials, or personal data in public reports.
