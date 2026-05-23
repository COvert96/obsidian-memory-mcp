# PRD: Phase 6 - Benchmarking, Documentation, and Release Readiness

## Introduction

Complete the MVP with comprehensive testing, benchmarking, documentation, and packaging. This phase ensures the system is production-ready, well-documented, and measurable against quality gates (relevance, performance, safety).

## Goals

- Create benchmark question sets for search relevance validation
- Achieve >=80% top-3 search relevance on benchmark queries
- Write complete user and operator documentation
- Set up CI/CD test automation
- Package and version MCP server for release

## User Stories

### US-001: Create fixture vault and benchmark question set
**Description:** As a QA engineer, I need a realistic fixture vault and benchmark questions so I can measure search relevance.

**Acceptance Criteria:**
- [ ] Fixture vault created in `tests/fixtures/sample-vault/` with:
  - 50+ markdown files covering diverse topics (API, architecture, compliance, operations)
  - Multiple heading levels and section structures
  - YAML frontmatter with tags and metadata
  - Wikilinks and internal references
  - Special characters and edge cases
- [ ] Benchmark question set (20-30 queries) with expected top-3 results documented
- [ ] Queries cover: single term, multi-term phrases, specific topics, edge cases
- [ ] Each benchmark query has: query text, expected top-3 file paths, relevance explanation
- [ ] Sample queries:
  - "API authentication" → should return API docs, not auth logs
  - "compliance risk" → should return policy docs, not bug reports
  - "database migration" → should return architecture docs
- [ ] Automated benchmark runner: `mcp-memory benchmark run` evaluates search on all queries
- [ ] Benchmark report shows: pass/fail per query, top-3 accuracy, coverage

### US-002: Implement automated test suite and CI/CD
**Description:** As a developer, I need automated tests so code changes don't break existing functionality.

**Acceptance Criteria:**
- [ ] Test suite structure:
  - Unit tests: `tests/unit/` covering individual modules (parser, indexer, retrieval, proposals)
  - Integration tests: `tests/integration/` covering end-to-end workflows
  - Acceptance tests: `tests/acceptance/` covering Phase 0-5 success criteria
- [ ] All tests pass locally and in CI
- [ ] Test coverage target: >=80% of codebase (excluding CLI scaffolding)
- [ ] CI/CD pipeline (GitHub Actions or similar):
  - Runs on every commit to main branch
  - Unit tests must pass (15-20 seconds)
  - Integration tests must pass (30-40 seconds)
  - Benchmark relevance must reach >=80% top-3 (60 seconds)
  - Code coverage report generated
- [ ] Exit codes and failure reporting clear (pass/fail/warning)
- [ ] Test environment: isolated fixture vault, clean database per run

### US-003: Write operator setup and operations guide
**Description:** As an operator, I need step-by-step instructions to set up and operate the MCP server.

**Acceptance Criteria:**
- [ ] Documentation covers:
  1. Prerequisites: Python 3.9+, pip, basic file system knowledge
  2. Installation: `pip install obsidian-memory-mcp`
  3. Vault setup: creating vault directory, config file, guardrails
  4. Initial indexing: running `mcp-memory index` on new vault
  5. Verifying setup: sanity checks (config valid, index exists, tools responsive)
  6. Daily operations: incremental indexing, proposal review, monitoring
  7. Troubleshooting: common errors and solutions
- [ ] Includes screenshots or example command output
- [ ] Walkthrough doable in <20 minutes for experienced operator
- [ ] Troubleshooting guide covers 10+ common issues

### US-004: Write developer integration guide
**Description:** As a developer integrating this MCP server into my tools, I need clear examples.

**Acceptance Criteria:**
- [ ] Guide covers:
  1. MCP server startup and configuration
  2. Connecting via MCP client (e.g., Claude, Anthropic SDK)
  3. Tool invocation examples for all 7 tools
  4. Error handling patterns (error codes, recovery)
  5. Context pack usage best practices
  6. Proposal workflow example (propose → list → approve)
- [ ] Code examples in Python and pseudocode
- [ ] Real example using fixture vault (copy-paste ready)
- [ ] Common patterns: search and retrieve, propose and apply, context packs

### US-005: Write architect/design documentation
**Description:** As someone evaluating this system, I need to understand design decisions and tradeoffs.

**Acceptance Criteria:**
- [ ] Architecture document covers:
  1. System overview (layers: config, indexing, retrieval, proposals)
  2. Data flow diagrams (markdown → index → search → context pack)
  3. Design decisions: why SQLite FTS vs embeddings, why propose-only, why CLI-based indexing
  4. Tradeoffs documented: latency vs accuracy, safety vs automation, MVP scope
  5. Scalability limits: tested up to 5000-file vault
  6. Future evolution paths noted (embeddings, caching, watching)
- [ ] Decision log: key decisions with rationale and alternatives considered
- [ ] Performance characteristics: typical latencies, index size, query cost

### US-006: Create release documentation and changelog
**Description:** As a release manager, I need version info and release notes.

**Acceptance Criteria:**
- [ ] Version file: `src/obsidian_memory_mcp/__version__.py` with semantic version
- [ ] CHANGELOG.md with MVP release notes:
  - Feature summary (what's included, what's not)
  - Installation instructions
  - Known limitations
  - Support contact
- [ ] pyproject.toml updated with:
  - Package metadata (name, version, description, author)
  - Dependencies (jsonschema, sqlite, pyyaml, etc.)
  - Entry points (CLI commands)
  - Test/dev dependencies
- [ ] README.md updated with:
  - Feature overview
  - Quick start (install, configure, index)
  - Links to full docs
  - Contributing guidelines

### US-007: Set up documentation site and API reference
**Description:** As a user, I need browsable documentation and auto-generated API reference.

**Acceptance Criteria:**
- [ ] Documentation site structure:
  - Overview/introduction
  - Quick start guide
  - Tool reference: all 7 MCP tools documented
  - Error code reference: all error codes with examples
  - FAQ: common questions
- [ ] API reference auto-generated from code:
  - Module docstrings
  - Function signatures and return types
  - Type hints preserved
- [ ] All links functional (no 404s in docs)
- [ ] Docs buildable locally: `make build-docs` or similar
- [ ] Docs published (GitHub pages, ReadTheDocs, or similar)

### US-008: Create acceptance test suite for MVP criteria
**Description:** As a QA engineer, I need automated acceptance tests to verify all Phase 0-5 requirements are met.

**Acceptance Criteria:**
- [ ] Acceptance tests cover success criteria from all previous phases:
  - Phase 0: tool contracts match specs, schemas validated
  - Phase 1: config loading, vault boundaries, guardrails enforced
  - Phase 2: indexing completes, hash-based dedup works, FTS index built
  - Phase 3: read/search tools work, <100ms latency, >=80% relevance
  - Phase 4: context packs load, token cap enforced, hard limit not exceeded
  - Phase 5: proposals don't write immediately, approval workflow required, audit trail complete
- [ ] Each test verifies one acceptance criterion
- [ ] Tests use fixture vault and realistic data
- [ ] All tests pass before release

### US-009: Set up performance benchmarking and monitoring
**Description:** As an operator, I need to know system performance characteristics and track changes.

**Acceptance Criteria:**
- [ ] Performance benchmarks measured and documented:
  - Indexing: time to index 5000-file vault, time per file
  - Search: response time for 10 typical queries
  - Read: response time for read_note, read_section
  - Context pack: load time, token count accuracy
  - Proposal: creation, listing, approval latency
- [ ] Baseline numbers recorded: `docs/performance-baseline.md`
- [ ] Performance regression test: if any operation >20% slower than baseline, warning in CI
- [ ] Profiling script: `scripts/profile.py` to measure latencies on fixture vault
- [ ] Memory usage documented: index size for 5000-file vault

### US-010: Prepare for multi-version support and evolution
**Description:** As a maintainer, I need a path for future updates while maintaining backward compatibility.

**Acceptance Criteria:**
- [ ] Version strategy documented: semantic versioning (MAJOR.MINOR.PATCH)
- [ ] Backward compatibility commitment: config v1 supported in v1.x releases
- [ ] Deprecation policy: breaking changes require major version bump
- [ ] Config migration: tooling to upgrade config format if needed
- [ ] Tool versioning: MCP tool signatures versioned in future if needed

## Functional Requirements

- FR-1: Benchmark question set with 20-30 queries and expected results
- FR-2: Automated test suite covering all 5 previous phases
- FR-3: CI/CD pipeline runs unit/integration/acceptance tests on every commit
- FR-4: All documentation (operator, developer, architecture) complete and tested
- FR-5: Search relevance measured: >=80% top-3 on benchmark queries
- FR-6: Performance baselines established and regression tests in place
- FR-7: Release packaging and versioning in place
- FR-8: Documentation site published and all links functional

## Non-Goals

- No translation support (English-only for MVP)
- No video tutorials (text docs only)
- No commercial support or SLA
- No telemetry or usage tracking
- No automatic updates (manual install/upgrade)

## Technical Considerations

- **Test Framework:** pytest with fixtures
- **CI/CD:** GitHub Actions (or equivalent)
- **Documentation:** Markdown with automated site generation (MkDocs or similar)
- **Benchmarking:** Consistent hardware/environment for fair comparisons
- **Performance Measurement:** Use `timeit` or `time.perf_counter()` for accurate latencies
- **Release:** PyPI package upload via GitHub Actions on version tag

## Success Metrics

- [ ] >=80% top-3 search relevance on all benchmark queries
- [ ] 100% of acceptance test criteria pass
- [ ] <5% performance regression in any operation vs baseline
- [ ] All documentation links functional (0 broken links)
- [ ] Setup from scratch takes <30 minutes for experienced operator
- [ ] >=80% test coverage of codebase
- [ ] CI/CD complete within 3 minutes (unit + integration + benchmark)
- [ ] Operator can handle setup, indexing, and proposal review without support

## Open Questions

- Should performance baselines be per-hardware-spec or generic?
  A: Generic.
- Should benchmark set be versioned separately from code?
  A: Not for MVP.
- Should docs be auto-generated from code examples or manually maintained?
  A: Auto-generated.
- Should CI/CD run on Windows, Linux, and macOS or just Linux?
  A: Yes Windows, Linux, and macOS.

## Dependencies

- All Phases 0-5 must be complete
- No external dependencies beyond Phases 0-5

## Deliverables

- `tests/fixtures/sample-vault/` with 50+ markdown files for testing
- `tests/benchmarks/benchmark-queries.yaml` with 20-30 questions and expected results
- `tests/acceptance/` with acceptance test suite for all phases
- `tests/integration/` and `tests/unit/` expanded with complete coverage
- `.github/workflows/ci.yml` (or equivalent) with test automation
- `docs/operator-guide.md` — setup and operations
- `docs/developer-guide.md` — integration examples
- `docs/architecture.md` — design decisions and tradeoffs
- `docs/performance-baseline.md` — documented latencies and measurements
- `docs/api-reference.md` — auto-generated from code
- `docs/faq.md` — common questions
- `docs/error-codes.md` — all error codes with examples
- `CHANGELOG.md` with MVP release notes
- `README.md` updated with quick start and feature overview
- `src/obsidian_memory_mcp/__version__.py` with version constant
- `pyproject.toml` with package metadata and dependencies
- `scripts/profile.py` — performance profiling script
- `scripts/benchmark.py` — benchmark runner
- Documentation site generated and published
