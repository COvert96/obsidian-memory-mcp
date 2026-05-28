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
- `propose_memory_update`
- `list_proposals`
- `approve_proposal`
- `reject_proposal`

## Boundaries

The MCP server layer in `src/obsidian_memory_mcp/server.py` is an adapter. It resolves the project registry, loads vault config, and delegates to domain services. Business rules live in config validation, guardrails, indexing, retrieval, context pack, proposal, changeset, and token modules. SQLite and filesystem access are details kept behind repository/service functions.

## Configuration

Each vault has a `memory-mcp.yaml` file. `ConfigLoader` validates required fields, absolute vault paths, derived index locations, context pack definitions, proposal settings, and read/write guardrails. A server-level registry maps MCP `project` names to vault roots.

## Indexing

The source of truth is markdown on disk. The index is derived data stored in SQLite at `index_db_location`. The indexing service discovers markdown files, hashes file content, parses frontmatter, sections, tags, and wikilinks, and updates SQLite tables plus FTS5 virtual tables. Incremental indexing skips unchanged files and removes deleted files from search results.

## Retrieval

`read_note` and `read_section` use guarded filesystem reads. `search_notes` queries the SQLite FTS5 index and supports path, exclude-path, and tag filters. Search results return ranked block previews with vault-relative file paths and heading metadata.

## Context Packs

Context packs are configured named bundles of files, optional sections, tags, included packs, and token budgets. The loader resolves configured paths, applies read guardrails, estimates tokens with `tiktoken`, and either rejects over-budget packs in strict mode or returns warnings in soft mode.

## Proposal Workflow

Writes are proposal-based. `propose_memory_update` records a proposed create, update, or delete for a `Memory/**` path without changing the file. `approve_proposal` rechecks guardrails and file hashes before writing. `reject_proposal` records a terminal rejection. Audit events and changesets support grouped review and memory supersession workflows.

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
