# System Architecture

## Overview

Obsidian Memory MCP is a local MCP server for guarded access to an Obsidian-style markdown vault. The system keeps protocol and transport details in the FastMCP layer and keeps project-specific policy in small, testable domain services.

Historical architecture context from earlier phases is preserved in [design-history.md](design-history.md).

The MVP release exposes 9 MCP tools:

- `read_note`
- `read_section`
- `search_notes`
- `get_context_pack`
- `list_context_packs`
- `write_memory`
- `update_memory`
- `write_note`
- `update_note`

## Boundaries

The MCP server layer in `src/obsidian_memory_mcp/server.py` is an adapter. It resolves the project registry, loads vault config, and delegates to domain services. Business rules live in config validation, guardrails, indexing, retrieval, context pack, write/supersession, and token modules. SQLite and filesystem access are details kept behind repository/service functions.

## Package Layout Convention

Domain packages follow one convention so public vs internal API boundaries are visible in the tree:

- `__init__.py` is the package public API and defines `__all__` exports.
- Shared domain data shapes live in `_models.py`.
- Internal implementation modules are underscore-prefixed.
- Persistence modules are named `repository.py`.
- Orchestration modules are named `service.py` (function-oriented) or `manager.py` (stateful class-oriented).
- Dependencies inside a package flow from orchestration and persistence toward models, not the reverse.

Recent cleanup aligned `config/` and `context_packs/` with this convention (`_models.py` modules plus curated package-level re-exports).

## Configuration

Each vault has a `memory-mcp.yaml` file. `ConfigLoader` validates required fields, absolute vault paths, derived index locations, context pack definitions, write limits, the memory archive path, and read/write guardrails. A server-level registry maps MCP `project` names to vault roots.

## Indexing

The source of truth is markdown on disk. The index is derived data stored in SQLite at `index_db_location`. The indexing service discovers markdown files, hashes file content, parses frontmatter, sections, tags, and wikilinks, and updates SQLite tables plus FTS5 virtual tables. Incremental indexing skips unchanged files and removes deleted files from search results.

## Retrieval

`read_note` and `read_section` use guarded filesystem reads. `search_notes` queries the SQLite FTS5 index and supports path, exclude-path, and tag filters. Search results return ranked block previews with vault-relative file paths and heading metadata.

## Context Packs

Context packs are configured named bundles of files, optional sections, tags, included packs, and token budgets. The loader resolves configured paths, applies read guardrails, estimates tokens with `tiktoken`, and either rejects over-budget packs in strict mode or returns warnings in soft mode.

## Write Workflow

Writes are direct and atomic. `write_memory`/`write_note` create new files; `update_memory`/`update_note` overwrite existing ones. Each call enforces the write guardrails, the create-vs-update precondition, and an optional `expected_hash` optimistic lock, then writes via a temp-file-plus-rename and appends one row to the append-only `write_audit` log. `update_memory` additionally accepts a `supersedes` list: `SupersessionService` validates the superseded paths up front, then archives each note under `memory_archive_path` with supersession frontmatter and back-references them from the new note — all recorded in a single audit row.

## MCP Runtime Integration

FastMCP handles initialize handshake, tool discovery, Pydantic schema generation, JSON-RPC framing, and transports. Runtime release tests use the in-process MCP memory transport to verify initialization, tool listing, generated schemas, and a representative live tool call without subprocess or port lifecycle complexity.

## Design Decisions

SQLite FTS5 is used instead of embeddings because it is deterministic, local, dependency-light, and good enough for the MVP fixture benchmark. Embeddings remain a future option if measured relevance is insufficient.

Writes are proposal-based because AI clients should not mutate memory files without review. The workflow favors auditability and conflict detection over write convenience.

Indexing is CLI-driven because it is simple, reproducible, and avoids background watcher complexity. Operators decide when to refresh derived data.

## Release Limits

The release benchmark fixture contains 35 markdown files covering API, architecture, compliance, operations, and memory workflow topics. The documented performance baseline indexes 34 public files because the private fixture path is denied by the sample guardrails.

Expected fixture latency on the measured Windows machine is single-digit milliseconds for reads/searches and sub-second times for full fixture indexing and context-pack loading. These are baseline observations, not universal guarantees.

Windows and Linux are verified in CI. macOS is not advertised as a verified MVP platform.

## Future Evolution

Future releases may add semantic retrieval, file watching, config migrations, hosted documentation, broader OS verification, or PyPI publication. These are not MVP scope and should be justified by measured user need.
