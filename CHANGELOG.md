# Changelog

## 0.2.0 - 2026-05-30

Git tag: `v0.2.0`. Package version: `0.2.0`.

Stable release of the direct-write line: SQLAlchemy index layer, Alembic migrations, guarded MCP writes with audit and supersession, architecture refactor, and the five-skill agent library under `docs/skills/`. Validated by [UAT](docs/acceptance/2026-05-30-acceptance-test-v0.2.0.md) (50/50 pass).

### Fixed

- `read_section` optional `context_suffix` (contract and [retrieval guide](docs/retrieval-guide.md) aligned).
- `write_memory`, `write_note`, and `update_note` return `ERR_GUARDRAIL_VIOLATION` for Memory/ scope violations (was `ERR_INVALID_REQUEST`).
- `read_note` rejects empty `note_path` with `ERR_INVALID_REQUEST`.
- [vault-setup.md](docs/vault-setup.md) documents directory-only write-allow paths.
- `tests/integration/test_uat_regression.py` covers UAT regression cases in CI.

### Notes

The feature set below matches the [0.2.0-rc.1](#0200-rc1---2026-05-29) pre-release, plus the fixes above.

## 0.2.0-rc.1 - 2026-05-29

Pre-release: SQLAlchemy index layer, Alembic migrations, direct-write MCP tools with audit and supersession, architecture refactor, and the published agent skills library. Git tag: `v0.2.0-rc.1`. Package version: `0.2.0rc1` (PEP 440).

### Added

**Database and migrations**

- SQLAlchemy Core `Table` metadata in `database/`; indexing repositories use Core `select`/`insert`/`update`/`delete` instead of raw SQL strings.
- Alembic (`001_initial_schema`) as the versioned schema owner, including FTS5 virtual tables via migration DDL.
- `mcp-memory migrate` with auto-detect for fresh installs, legacy v0.1.x indexes, and incremental upgrades; [migration guide](docs/migration-guide.md).

**Direct-write MCP tools**

- `write_memory` and `write_note` — atomic creates with guardrails and `ERR_FILE_EXISTS` (`WriteService.create()`).
- `update_memory` and `update_note` — in-place updates with optional `expected_hash` optimistic locking and `ERR_HASH_MISMATCH`.
- `read_note` returns `content_hash` for lock tokens; append-only `write_audit` table and `mcp-memory audit writes` CLI.
- `update_memory` `supersedes` — `SupersessionService` archives outdated `Memory/` notes under `memory_archive_path` (default `Memory/archive/`) with supersession frontmatter and one audit row per operation.
- Alembic migration `002_remove_proposals` drops legacy proposal tables.
- Config `memory_archive_path`; `max_write_content_bytes` (with deprecated alias for the old proposal limit key).

**Agent skills library**

- `docs/skills/` — provider packages ([Claude Code](docs/skills/claude/), [Codex](docs/skills/openai/)) plus [shared workflows](docs/skills/shared/): **context-bootstrap**, **memory-capture**, **recall-before-answer**, **memory-maintenance**, **structured-note-template**.
- Templates, examples, and `validate-note.py` for local frontmatter checks (memory-capture).

**Tooling and CI**

- Radon complexity gate (`scripts/radon_gate.py`) in CI and release documentation.
- Reusable [quality-gates](.github/workflows/quality-gates.yml) workflow; [release](.github/workflows/release.yml) workflow creates GitHub Releases on `v*` tags with changelog extraction and tag/`pyproject.toml` version verification.

### Changed

- Bounded-context package layout with explicit `__all__` APIs, `import-linter` contracts, `cli/` entry layout, `indexing/parser/` subpackage, and shared `markdown/` and `utils/` helpers (`glob_utils`, fence parsing).
- `mcp-memory migrate` runs `upgrade head` for legacy databases that had a `files` table but no `alembic_version`, and repairs schemas stamped at head but missing `write_audit` or still carrying proposal tables.
- Runtime `metadata.create_all()` bootstrap retired; Alembic is the sole schema owner for index databases.
- Documentation, fixture vault samples, and benchmarks aligned with direct writes (no proposal MCP tools).

### Removed

- Proposal MCP tools (`propose_*`, `approve_*`, `reject_*`, changesets) and the `proposals/` package.
- SQLite proposal and changeset tables (migration 002).
- `ERR_STALE_PROPOSAL` and proposal-era CLI subcommands; deprecated config fields warn at load time.

### Upgrade Notes

1. Run `uv run mcp-memory migrate {vault}` to apply schema migrations through head (002).
2. Remove deprecated config keys such as `proposal_ttl_seconds` (validator warns if present).
3. Re-index vaults after upgrading parser or schema.
4. Upgrading from **0.1.x**: see [docs/migration-guide.md](docs/migration-guide.md).

### Known Limitations

- GitHub source release only; no PyPI publication.
- No delete MCP tool for memory files (planned for a future release).
- No hosted documentation site.

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
