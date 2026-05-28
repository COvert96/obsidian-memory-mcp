# Changelog

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
