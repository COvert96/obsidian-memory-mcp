# PRD: Phase 6 - GitHub Open Source Release Readiness

## Introduction

Complete the MVP for a first open-source GitHub release. This phase focuses on
reproducible quality gates, benchmark evidence, in-repository documentation,
repository hygiene, and release notes. The MVP release target is GitHub only:
no PyPI publication and no browsable documentation site are required.

## Current State Snapshot (2026-05-28)

- Project uses `uv` and `uv_build`, requires Python `>=3.12`, and exposes
  `mcp-memory` and `obsidian-memory-tokens` console scripts.
- The live MCP tool surface contains 9 tools:
  `read_note`, `read_section`, `search_notes`, `get_context_pack`,
  `list_context_packs`, `propose_memory_update`, `list_proposals`,
  `approve_proposal`, and `reject_proposal`.
- Existing docs cover vault setup, indexing, retrieval, context packs,
  proposals, memory supersession, and system architecture.
- Existing CI runs `ruff`, `mypy src`, and unit tests only (`tests/unit`) on
  Windows and Linux. Integration tests exist in `tests/integration/` (5 files
  covering indexing, retrieval, approval, context packs, and memory
  supersession) but are excluded from the current CI workflow.
- `pyproject.toml` has basic metadata (`name`, `version`, `description`,
  `readme`, `requires-python`, `dependencies`, `scripts`, dev dependencies)
  but is missing `license`, `authors`, `maintainers`, and `[project.urls]`.
- `LICENSE` (Apache 2.0) is present but the copyright line still contains the
  template placeholders `[yyyy]` and `[name of copyright owner]`.
- Local verification on 2026-05-28:
  - `uv run ruff check`: passed
  - `uv run mypy src`: passed
  - `uv run pytest tests`: 236 passed, 2 skipped
- Current release gaps:
  - `README.md` is empty.
  - No `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, or release checklist.
  - No benchmark query set or benchmark runner.
  - The sample vault has only 5 markdown files, not enough for relevance
    benchmarking.
  - No explicit acceptance-test traceability matrix across Phases 0-5/2A.
  - No coverage gate or coverage report.
  - No GitHub release checklist/workflow.
  - `LICENSE` copyright placeholders are unfilled.
  - Integration tests are not included in CI.

## Architecture Alignment Update (2026-05-28)

Release readiness must validate the Phase 2A runtime contract without expanding
the release scope beyond GitHub:

- MCP initialize handshake succeeds for `mcp-memory serve`.
- Tool discovery/listing is validated from the live FastMCP server runtime.
- Runtime contract checks compare documented tool contracts with generated
  FastMCP/Pydantic tool schemas.
- CI covers the advertised support matrix. Windows and Linux are required for
  MVP; macOS should be added only if the README claims macOS support.

## Goals

- Prepare the repository for public GitHub use by a new developer or operator.
- Prove MVP behavior with automated checks, release-gate tests, and documented
  benchmark results.
- Create a deterministic benchmark question set for search relevance validation.
- Achieve `>=80%` top-3 search relevance on benchmark queries.
- Complete in-repository user, operator, integration, and maintenance docs.
- Package and version the project for source-based GitHub release.

## User Stories

### US-001: Create Fixture Vault And Benchmark Question Set

**Description:** As a QA engineer, I need a realistic fixture vault and
benchmark questions so I can measure search relevance.

**Acceptance Criteria:**
- [ ] Fixture vault exists in `tests/fixtures/sample-vault/` with 30-50+
      markdown files covering API, architecture, compliance, operations, and
      memory workflow topics.
- [ ] Fixture files include multiple heading levels, YAML frontmatter, tags,
      wikilinks, internal references, special characters, and path edge cases.
- [ ] Benchmark question set exists at `tests/benchmarks/benchmark-queries.yaml`
      with 20-30 queries and expected top-3 results.
- [ ] Each benchmark query includes query text, expected file paths, expected
      section or block when relevant, and a short relevance explanation.
- [ ] Queries cover single terms, multi-term phrases, specific topics, path/tag
      filters, and known edge cases.
- [ ] Automated benchmark runner evaluates all queries and reports pass/fail per
      query, top-3 accuracy, and aggregate accuracy.
- [ ] Benchmark expected results are understood to be deterministic for a fixed
      fixture vault. Updating fixture content requires updating expected results;
      this is expected and not a test design flaw.

### US-002: Strengthen Automated Test Suite And CI

**Description:** As a maintainer, I need automated checks so public changes do
not break release-critical behavior.

**Acceptance Criteria:**
- [ ] CI runs on pull requests and pushes to `main`.
- [ ] CI runs `uv run ruff check`, `uv run mypy src`, and
      `uv run pytest tests` (the full `tests/` directory, not only
      `tests/unit`).
- [ ] CI runs on Windows and Linux at minimum.
- [ ] Integration tests run in CI, not only unit tests. The CI `pytest` step
      is updated from `uv run pytest tests/unit` to `uv run pytest tests`.
- [ ] Release-gate tests verify MCP handshake, tool discovery, and at least one
      live runtime call through the MCP server. Runtime tests use FastMCP's
      in-process test client (`fastmcp.Client` or `mcp.testing` transport)
      rather than spawning a subprocess, to avoid port binding and process
      lifecycle complexity in CI.
- [ ] Benchmark relevance reaches `>=80%` top-3 before release.
- [ ] Coverage report is generated and the documented target is `>=80%` for
      release-critical code.
- [ ] Test environment uses isolated fixture vaults and clean derived data per
      run.

### US-003: Write In-Repository Setup And Operations Documentation

**Description:** As an operator, I need step-by-step instructions to set up and
operate the MCP server from a GitHub checkout or GitHub source install.

**Acceptance Criteria:**
- [ ] Documentation states prerequisites: Python `>=3.12`, `uv`, basic file
      system knowledge, and an Obsidian-style markdown vault.
- [ ] Documentation does not instruct users to install from PyPI for the MVP.
- [ ] Setup instructions reference `config-example.yaml` in the project root
      as the starting-point vault config template.
- [ ] Setup instructions cover:
  1. Clone or source-install from GitHub.
  2. Create or choose a vault directory.
  3. Add `memory-mcp.yaml`.
  4. Validate config.
  5. Run initial indexing.
  6. Configure and run `mcp-memory serve`.
  7. Verify setup with a known read/search call.
- [ ] Daily operations cover incremental indexing, index status, search debug,
      proposal review, proposal approval/rejection, and cleanup.
- [ ] Troubleshooting covers the most common failure modes in each category:
      setup, config, guardrails, indexing, and MCP startup. At minimum one
      scenario per category, with root cause and resolution.
- [ ] Existing docs are linked from `README.md` instead of duplicated where
      possible.

### US-004: Write Tool And Integration Reference

**Description:** As a developer integrating this MCP server into a client, I
need clear examples for every supported tool.

**Acceptance Criteria:**
- [ ] Reference covers every tool defined in `TOOL_CONTRACTS` and registered in
      `src/obsidian_memory_mcp/server.py`. `src/obsidian_memory_mcp/contracts.py`
      contains structured `TOOL_CONTRACTS` metadata for all 9 tools and is the
      authoritative source for this doc.
- [ ] Reference includes request fields, response fields, error codes, and one
      practical example for each tool.
- [ ] Reference covers error handling patterns and recovery suggestions from
      `ERROR_CATALOG`. `src/obsidian_memory_mcp/errors.py` contains the
      authoritative `ERROR_CATALOG` definition.
- [ ] Reference includes common workflows:
  - Search and retrieve.
  - Load context pack.
  - Propose, list, approve, and reject a memory update.
- [ ] Examples use the fixture vault and are copy-paste friendly where possible.

### US-005: Refresh Architecture And Design Documentation

**Description:** As someone evaluating the project, I need to understand design
decisions, tradeoffs, and release limits.

**Acceptance Criteria:**
- [ ] `docs/system-architecture.md` reflects the current implementation and
      9-tool surface. Updates are limited to accuracy corrections against the
      current implementation; adding new architectural decisions is out of scope
      for Phase 6.
- [ ] Architecture docs cover config, indexing, retrieval, context packs,
      proposals, changesets, and MCP runtime integration.
- [ ] Design decisions document why SQLite FTS is used instead of embeddings,
      why writes are proposal-based, and why indexing is CLI-driven.
- [ ] Release limits are explicit, including tested fixture scale, expected
      latency ranges, and any unverified operating systems.
- [ ] Future evolution paths are noted without making them MVP scope.

### US-006: Create Release Documentation, Versioning, And Metadata

**Description:** As a release manager, I need version information and release
notes for the GitHub release.

**Acceptance Criteria:**
- [ ] Version is read from `pyproject.toml` as the single source of truth. No
      separate `__version__.py` is required. At least one test exercises the
      version string via `importlib.metadata.version('obsidian-memory-mcp')`.
- [ ] `CHANGELOG.md` includes MVP release notes, known limitations, upgrade
      notes, and support channels.
- [ ] `pyproject.toml` includes release-ready metadata:
  - Package name, version, description, README, license, authors/maintainers.
  - Python requirement.
  - Runtime dependencies.
  - Dev/test dependencies.
  - Console scripts.
  - Project URLs pointing to the GitHub repository, issues, and docs files.
- [ ] `README.md` includes feature overview, quick start, tool summary,
      documentation links, security/safety model, and release status.
- [ ] GitHub release notes can be created from the changelog without requiring
      PyPI publication.

### US-007: Prepare Open Source Repository Hygiene

**Description:** As an open-source maintainer, I need the public repository to
set clear expectations for contributions, support, and security.

**Acceptance Criteria:**
- [ ] `LICENSE` (Apache 2.0) is present, referenced from `README.md`, and the
      copyright line has the correct year and owner with no template
      placeholders remaining.
- [ ] `CONTRIBUTING.md` documents local setup, required checks, TDD
      expectations, and pull request expectations.
- [ ] `AGENTS.md` is reviewed and either retained as-is, merged into
      `CONTRIBUTING.md`, or acknowledged via a link from `CONTRIBUTING.md`.
- [ ] `SECURITY.md` documents how to report security issues and explains that
      real private vault data must not be shared in issues.
- [ ] GitHub issue templates exist for bug reports and feature requests, or the
      README clearly states the preferred issue format.
- [ ] `.gitignore` excludes local vault data, derived indexes, caches, virtual
      environments, build artifacts, and local server registry files.
- [ ] No real private vault content, credentials, or personal data are present in
      tracked fixtures or docs.

### US-008: Create Release Acceptance Gate For MVP Criteria

**Description:** As a QA engineer, I need a release gate that verifies Phase 0-5
requirements remain true.

**Acceptance Criteria:**
- [ ] Acceptance criteria from previous PRDs are mapped to existing tests or new
      release-gate tests.
- [ ] Coverage includes:
  - Phase 0: contracts and schemas.
  - Phase 1: config loading, vault boundaries, and guardrails.
  - Phase 2A: MCP initialize handshake, tool discovery, and runtime call.
  - Phase 2: indexing, hash-based deduplication, and FTS index creation.
  - Phase 3: read/search tools, latency expectations, and relevance benchmark.
  - Phase 4: context packs, token caps, and strict budget behavior.
  - Phase 5A/5B: proposal workflow, approval requirement, audit trail,
    changesets, and memory supersession docs.
- [ ] Release gate can be run locally with `uv run` commands documented in
      `README.md` or `docs/release-checklist.md`.
- [ ] All release-gate checks pass before tagging the GitHub release.

### US-009: Establish Relevance And Performance Baselines

**Description:** As an operator, I need documented performance characteristics
and a way to detect major regressions.

**Acceptance Criteria:**
- [ ] Baselines are measured and documented in `docs/performance-baseline.md`.
- [ ] Baselines include indexing time, search latency, read latency, context pack
      load time, proposal latency, token-count accuracy checks, and index size.
- [ ] Benchmark scripts use deterministic fixture data and clear output.
- [ ] CI performance threshold failures are reserved for regressions of 10x or
      greater, measured against fixture-based baselines. Absolute time
      thresholds are documented in `docs/performance-baseline.md` but are
      machine-specific and not enforced in CI for the MVP.
- [ ] Baseline docs state the machine/OS used for measurement and do not promise
      universal performance.

### US-010: Document Versioning And Future Evolution Policy

**Description:** As a maintainer, I need a clear compatibility policy for future
public releases.

**Acceptance Criteria:**
- [ ] Semantic versioning policy is documented.
- [ ] Config compatibility commitment is documented for the current config
      schema.
- [ ] MCP tool signature compatibility expectations are documented.
- [ ] Deprecation policy states that breaking changes require a major version
      bump after `1.0.0`.
- [ ] Config migration tooling is explicitly out of scope until a real config
      schema migration exists.

## Functional Requirements

- FR-1: Benchmark fixture vault and query set must support repeatable top-3
  relevance measurement.
- FR-2: Release checks must cover Phases 0-5, including Phase 2A and Phase 5B.
- FR-3: CI must run formatting/lint, type checking, unit tests, integration
  tests, and release-gate checks.
- FR-4: Documentation must be complete as in-repository Markdown and linked from
  `README.md`.
- FR-5: Search relevance must be measured and reach `>=80%` top-3 on benchmark
  queries.
- FR-6: Performance baselines must be established and documented.
- FR-7: Release metadata, versioning, changelog, and GitHub release notes must
  be ready before tagging.
- FR-8: The release process must not require PyPI publication, ReadTheDocs,
  GitHub Pages, or another documentation site.

## Non-Goals

- No PyPI release for the MVP.
- No hosted/browsable documentation site for the MVP.
- No auto-generated API reference unless it is needed for an in-repo Markdown
  reference.
- No translation support.
- No video tutorials.
- No commercial support or SLA.
- No telemetry or usage tracking.
- No automatic updates.
- No packaged binaries or installers.

## Technical Considerations

- **Build/package manager:** `uv` and `uv_build`.
- **Test framework:** `pytest` with isolated fixtures.
- **Static checks:** `ruff` and `mypy`.
- **CI:** GitHub Actions.
- **Documentation:** In-repository Markdown, with README as the entry point.
- **Benchmarking:** Deterministic fixture data; avoid benchmark expectations
  tied to private vault content.
- **Performance measurement:** Use `time.perf_counter()` or equivalent
  monotonic timing.
- **Release:** GitHub tag and GitHub release notes. PyPI upload workflow is not
  required for MVP.
- **Security/privacy:** Public fixtures and docs must not contain real private
  vault data.
- **MCP runtime tests:** Use FastMCP's in-process test client
  (`fastmcp.Client` or `mcp.testing` transport) for MCP handshake and
  tool-discovery tests. Avoid spawning `mcp-memory serve` as a subprocess in
  CI to prevent port binding and process lifecycle complexity.
- **Tool and error reference docs:** `src/obsidian_memory_mcp/contracts.py`
  contains `TOOL_CONTRACTS` and `src/obsidian_memory_mcp/errors.py` contains
  `ERROR_CATALOG`. `docs/tool-reference.md` and `docs/error-codes.md` should
  be structured to reflect these definitions rather than duplicating them.

## Success Metrics

- [ ] `uv run ruff check` passes.
- [ ] `uv run mypy src` passes.
- [ ] `uv run pytest tests` passes.
- [ ] Release-gate checks pass locally and in CI.
- [ ] `>=80%` top-3 search relevance on benchmark queries.
- [ ] `>=80%` test coverage for release-critical code, or a documented reason
      for any uncovered release-critical path.
- [ ] All README and docs links resolve inside the repository.
- [ ] Setup from a clean clone takes less than 30 minutes for an experienced
      operator.
- [ ] CI runtime is measured after integration tests are added. The target is
      under 3 minutes for required checks; anything under 10 minutes is
      acceptable for MVP. This is an observation target, not a release gate.
- [ ] GitHub release checklist is complete before tagging.

## Open Questions

- Should performance baselines be generic or hardware-specific?
  A: Generic baseline from fixture data, with machine/OS details documented.
- Should the benchmark set be versioned separately from code?
  A: No. Keep benchmark fixtures and expected results in the repository.
- Should docs be published to a hosted site?
  A: No. In-repository Markdown is sufficient for the MVP.
- Should the release publish to PyPI?
  A: No. A GitHub release is sufficient for the MVP.
- Should CI run on Windows, Linux, and macOS?
  A: Windows and Linux are required. Add macOS only if the README claims macOS
  support for the MVP.

## Dependencies

- All Phase 0-5 work, including Phase 2A, Phase 5A, and Phase 5B, must be
  complete enough to validate through release-gate tests.
- No external hosted documentation or package registry dependency is required
  for the MVP release.

## Deliverables

- Expanded `tests/fixtures/sample-vault/` suitable for relevance benchmarking.
- `tests/benchmarks/benchmark-queries.yaml` with 20-30 benchmark queries.
- Benchmark runner invoked through `uv run`, either as a script or CLI command.
- Release-gate test coverage for MCP runtime handshake, tool discovery, and
  representative tool calls.
- CI workflow updated to run required checks on Windows and Linux.
- Coverage report and documented coverage target.
- `README.md` with overview, quick start, docs index, safety model, and release
  status.
- `CHANGELOG.md` with MVP release notes.
- `CONTRIBUTING.md`.
- `SECURITY.md`.
- `docs/tool-reference.md` or equivalent in-repo MCP tool reference.
- `docs/error-codes.md` or equivalent in-repo error reference.
- `docs/performance-baseline.md`.
- `docs/release-checklist.md`.
- Refreshed `docs/system-architecture.md`.
- Release-ready `pyproject.toml` metadata.
- Explicit version source.
- GitHub issue templates or documented issue format.
- GitHub release notes and tag checklist.
