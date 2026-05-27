# PRD: Obsidian Memory MCP MVP — Master Roadmap

## Introduction

This document provides a high-level overview of the Obsidian Memory MCP MVP implementation, organized into sequential phases. Each phase builds on previous phases and delivers measurable functionality. This master document should be read before diving into individual phase PRDs.

## Architecture Alignment Update (2026-05-23)

This roadmap is aligned to `docs/system-architecture.md` with the following locked decisions:

1. Phase sequence is now: **0 -> 1 -> 2A -> 2 -> 3 -> 4 -> 5A -> 5B -> 6**.
2. `Phase 2A` is a dedicated MCP SDK bootstrap phase (FastMCP server + `read_note` + serve command + project registry).
3. Runtime tool validation shifts to FastMCP/Pydantic type-hint schemas; JSON schemas/contracts remain documentation and verification artifacts.
4. Project resolution uses a **server registry file** (`project -> vault_root`) for multi-project runtime.
5. Default context-pack budget is **8000 tokens** (per-pack override still supported).
6. Server lifecycle for MVP is long-running stdio.

## Vision

Build a reusable, multi-project Obsidian memory Model Context Protocol (MCP) server where each project is configured via a vault-local config file. The system provides deterministic, token-budgeted retrieval of vault content, guarded write workflows, and clear audit trails—all without requiring embeddings, vectors, or complex dependencies.

## Core Principles

1. **Safety First:** Propose-only updates, explicit approval required, no automatic writes
2. **Deterministic:** Same input always produces same output; reproducible indexing and search
3. **Low Friction:** CLI-based, no UI required; works with any Obsidian vault
4. **Clear Boundaries:** Vault root isolation, path normalization, guardrail enforcement
5. **Measurable:** Benchmarked search relevance, performance baselines, audit trails

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│ MCP Client (Claude, Anthropic SDK, custom tools)       │
└───────────────────┬─────────────────────────────────────┘
                    │ MCP Protocol
┌───────────────────▼─────────────────────────────────────┐
│ MCP Server (obsidian-memory-mcp)                        │
├─────────────────────────────────────────────────────────┤
│ Tools Layer:                                            │
│ ├─ read_note, read_section (Phase 3)                    │
│ ├─ search_notes (Phase 3)                               │
│ ├─ get_context_pack (Phase 4)                           │
│ ├─ propose_memory_update (Phase 5A)                     │
│ ├─ list_proposals, approve_proposal (Phase 5A)          │
│ └─ CLI commands (Phases 1-6)                            │
├─────────────────────────────────────────────────────────┤
│ Core Services:                                          │
│ ├─ ConfigLoader (Phase 1)                               │
│ ├─ MarkdownParser & Indexer (Phase 2)                   │
│ ├─ RetrievalService (Phase 3)                           │
│ ├─ ContextPackService (Phase 4)                         │
│ ├─ ProposalManager (Phase 5A)                           │
│ ├─ Memory supersession workflows (Phase 5B)             │
│ └─ ValidationLayer (Phase 0)                            │
├─────────────────────────────────────────────────────────┤
│ Storage:                                                │
│ ├─ Vault Files (markdown + frontmatter)                 │
│ └─ SQLite DB (index, proposals, audit log)              │
└─────────────────────────────────────────────────────────┘
```

## Phase Timeline and Dependencies

**Superseding order:** execute phases as `0 -> 1 -> 2A -> 2 -> 3 -> 4 -> 5A -> 5B -> 6`.

```
Phase 0: Foundation & Contracts (2-4 hrs)
  ├─ Tool specifications
  ├─ Error model
  ├─ Token estimator
  └─ Schema validation
  
Phase 1: Config & Safety (4-6 hrs)
  ├─ (depends on Phase 0)
  ├─ Config loader
  ├─ Vault boundaries
  └─ Guardrails
  
Phase 2A: MCP SDK Bootstrap (2-4 hrs)
  ├─ (depends on Phase 0-1)
  ├─ FastMCP server bootstrap
  ├─ `mcp-memory serve`
  └─ `read_note` proof-of-runtime + project registry

Phase 2: Indexing (6-8 hrs)
  ├─ (depends on Phase 0-1 and Phase 2A)
  ├─ Markdown parser
  ├─ SQLite schema + FTS5
  └─ CLI index commands
  
Phase 3: Retrieval (6-8 hrs)
  ├─ (depends on Phase 0-2)
  ├─ read_note, read_section tools
  ├─ search_notes with FTS
  └─ Relevance ranking
  
Phase 4: Context Packs (4-6 hrs)
  ├─ (depends on Phase 0-2)
  ├─ get_context_pack tool
  ├─ Token budget enforcement
  └─ Missing file detection
  
Phase 5A: Core Proposal Workflow (4-6 hrs, only if a real write workflow exists)
  ├─ (depends on Phase 0-2)
  ├─ propose_memory_update tool
  ├─ Approval workflow
  ├─ Hash conflict detection
  └─ Minimal lifecycle logging

Phase 5B: Advanced Proposal Workflows (4-6 hrs, only if 5A proves insufficient)
  ├─ (depends on Phase 5A)
  ├─ grouped logical changesets
  ├─ Memory/ supersession workflows
  ├─ richer operator tooling
  └─ richer audit/reporting only if usage demands it
  
Phase 6: Release & QA (4-6 hrs)
  ├─ (depends on Phase 0-5A; 5B included if built)
  ├─ Benchmarking & relevance
  ├─ Complete documentation
  ├─ CI/CD setup
  └─ Release packaging
```

## MVP Scope: What's Included

### Tools (7 total)
1. `read_note` — retrieve full markdown file
2. `read_section` — retrieve specific section by heading
3. `search_notes` — full-text search with filtering
4. `get_context_pack` — load curated file bundles with token budget
5. `propose_memory_update` — create non-mutating update proposal
6. `list_proposals` — view pending proposals
7. `approve_proposal` — apply approved proposals to vault

### Features
- Per-project configuration (one config file per vault)
- Vault path isolation and guardrails (no directory traversal)
- Markdown parsing with YAML frontmatter, headings, sections
- SQLite FTS5 indexing for fast search
- Deterministic token estimation (default 8000-token context-pack budget, strict enforcement configurable per pack)
- Explicit approval workflow for all writes (no auto-write)
- Audit trail of all proposed/approved/applied updates
- CLI commands for indexing, proposal management, status checking

### Non-MVP (Out of Scope)
- Automatic file watching or scheduled indexing
- Semantic/embedding-based search (FTS-only for MVP)
- Caching or performance optimization beyond baselines
- Authentication/multi-user controls
- UI or web interface
- Telemetry or usage tracking

## Quality Gates (Success Criteria)

| Gate | Target | Phase |
|------|--------|-------|
| Search relevance (top-3) | >=80% | Phase 6 |
| Tool contract spec complete | 100% | Phase 0 |
| Vault boundary enforcement | 100% pass | Phase 1 |
| Index completeness | 100% of vault | Phase 2 |
| Read tool latency | <50ms | Phase 3 |
| Search tool latency | <100ms | Phase 3 |
| Context pack token accuracy | ±5% | Phase 4 |
| Hard token cap enforcement | 100% | Phase 4 |
| Proposal approval required | 100% | Phase 5A |
| Proposal workflow replaces a real manual write workflow | yes | Phase 5A |
| Lifecycle records sufficient for support/debugging | yes | Phase 5A |
| Contradictory memory remains traceable after supersession | yes | Phase 5B |
| Test coverage | >=80% | Phase 6 |
| Documentation completeness | 100% | Phase 6 |

## Key Decisions

1. **SQLite FTS5, not embeddings:** Deterministic, requires no GPU, fast enough for MVP
2. **Propose-only model:** Prevent accidental/malicious overwrites, enable review
3. **CLI-based indexing:** No automatic watching; operator controls when index updates
4. **Per-vault config:** Enable multi-project deployments with isolated constraints
5. **No semantic search MVP:** Add later if relevance insufficient; FTS is baseline
6. **Default 8000-token budget:** Better fit for modern context windows while keeping strict budget controls
7. **Vault file immutability (read-only):** Indexing reads files, doesn't modify them; only proposals/approval modify

## Implementation Effort Estimate

| Phase | Duration | Effort |
|-------|----------|--------|
| Phase 0 | 1 week | 2-4 hours |
| Phase 1 | 1 week | 4-6 hours |
| Phase 2A | 0.5 week | 2-4 hours |
| Phase 2 | 1.5 weeks | 6-8 hours |
| Phase 3 | 1.5 weeks | 6-8 hours |
| Phase 4 | 1 week | 4-6 hours |
| Phase 5A | 1 week | 4-6 hours |
| Phase 5B | 1 week | 4-6 hours |
| Phase 6 | 1.5 weeks | 4-6 hours |
| **Total** | **10 weeks** | **36-54 hours** |

(Estimates assume 1 developer, with some parallelism possible in Phases 3-5B)

## Deliverables by Phase

### Phase 0 — Specification & Contracts
- Tool contract specification (YAML/JSON)
- Error code enumeration
- Token estimator function
- Schema validation framework
- Phase-specific acceptance tests

### Phase 1 — Configuration & Safety
- Config loader and validator
- Path normalization and guardrail evaluator
- Vault setup guide
- Config validation CLI command
- Phase-specific integration tests

### Phase 2A — MCP SDK Bootstrap
- FastMCP server bootstrap (`server.py`)
- Project registry mapping (`project -> vault_root`)
- `mcp-memory serve` CLI command
- First runtime tool (`read_note`) with mapped MCP errors
- Runtime smoke tests (initialize, list tools, call tool)

### Phase 2 — Markdown Indexing
- Markdown parser (frontmatter, headings, sections)
- SQLite schema and FTS5 setup
- Indexer service (full and incremental)
- CLI index commands (`mcp-memory index`, `mcp-memory status`)
- Indexing guide

### Phase 3 — Retrieval Tools
- ReadNoteService, ReadSectionService, SearchService
- MCP tool implementations (read_note, read_section, search_notes)
- Relevance ranking and result formatting
- Fixture vault for testing
- Tool documentation and examples

### Phase 4 — Context Packs
- ContextPackLoader and token budget enforcement
- `get_context_pack` MCP tool
- Pack configuration and validation
- Stale file detection
- CLI pack management commands

### Phase 5A — Core Proposal Workflow
- ProposalManager with core lifecycle
- `propose_memory_update`, `list_proposals`, `approve_proposal` MCP tools
- Hash-based conflict detection
- Minimal lifecycle logging
- CLI review/approval/reject commands first

### Phase 5B — Advanced Proposal Workflows
- Grouped logical changesets
- Memory supersession and archival workflows
- Richer proposal review/management commands only if needed
- Richer audit/reporting only if needed

### Phase 6 — Testing, Documentation, Release
- Benchmark question set and relevance runner
- Complete test suite (unit, integration, acceptance)
- Operator guide, developer guide, architecture docs
- CI/CD pipeline
- Release packaging and changelog

## How to Use This PRD

1. **For Planning:** Read this document for overall vision and timeline
2. **For Implementation:** Read the individual phase PRDs in order (Phase 0 → Phase 1 → Phase 2A → Phase 2 → Phase 3 → Phase 4 → Phase 5A → Phase 5B → Phase 6)
3. **For Dependencies:** Check "Dependencies" section in each phase PRD before starting
4. **For Success Criteria:** Each phase PRD lists acceptance criteria and success metrics

## Open Questions for Stakeholders

1. Should the MVP support more than 5000 files, or optimize for that?
2. Is the default 8000-token context-pack budget still appropriate for MVP workflows?
3. Should proposal approval require authentication/signing?
4. Should we add search result ranking/relevance scoring in MVP, or validate FTS sufficiency first?
5. What's the priority order if resources are limited (e.g., retrieval tools before context packs)?

## Next Steps

1. Review and approve this master PRD and all phase PRDs
2. Assign Phase 0 to developer(s)
3. Set up git repository with phase branches
4. Create fixture vault and test infrastructure
5. Begin Phase 0 implementation
6. Schedule phase completion reviews before moving to next phase

## References

- [Phase 0 PRD: Foundation and Contracts](prd-phase-0-foundation.md)
- [Phase 1 PRD: Project Config and Safety](prd-phase-1-config-safety.md)
- [Phase 2A PRD: MCP SDK Bootstrap](prd-phase-2a-mcp-sdk-bootstrap.md)
- [Phase 2 PRD: Markdown Indexing](prd-phase-2-indexing.md)
- [Phase 3 PRD: Retrieval Tools](prd-phase-3-retrieval.md)
- [Phase 4 PRD: Context Packs](prd-phase-4-context-packs.md)
- [Phase 5 PRD: Proposal Workflow Overview](prd-phase-5-proposals.md)
- [Phase 5A PRD: Core Proposal Workflow](prd-phase-5a-proposals.md)
- [Phase 5B PRD: Advanced Proposal Workflows and Memory Supersession](prd-phase-5b-proposals.md)
- [Phase 6 PRD: Testing, Docs, Release](prd-phase-6-release.md)
