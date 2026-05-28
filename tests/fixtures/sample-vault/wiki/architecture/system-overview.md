---
tags: [architecture, overview]
type: concept
---
# System Overview

The obsidian-memory MCP system provides a structured interface for reading, searching, and proposing changes to an Obsidian markdown vault. It consists of four main layers: an MCP server that handles protocol communication, an indexing service that maintains a full-text searchable index, a retrieval service that serves search and read requests, and a proposal manager that coordinates write workflows.

## Purpose

The system enables Claude and other MCP clients to reliably interact with markdown vaults without direct filesystem access. Vault boundaries are enforced via guardrails, preventing reads or writes outside configured directories. A two-step proposal workflow ensures changes are intentional and auditable.

## Components

### MCP Server Layer

The MCP server implements the Model Context Protocol, handling tool registration, parameter validation, and error propagation. It translates client tool calls into internal system calls and formats responses according to the MCP specification.

### Indexing Service

The indexing service maintains a SQLite FTS5 full-text search index. It scans the vault periodically or on-demand, extracts metadata from YAML frontmatter, parses markdown sections, and updates the index with new or modified content.

### Retrieval Service

The retrieval service answers search and read requests. It executes FTS queries, applies path and tag filters, ranks results by relevance, and formats results for client consumption. Context packs are assembled by this service.

### Proposal Manager

The proposal manager handles the two-step write workflow. It validates proposals against vault boundaries, stores proposals in the SQLite database with expiry timestamps, detects conflicts during approval, and applies approved changes to disk with audit logging.

## Data Flow

Clients submit search queries or proposals through the MCP server. Search requests flow through the retrieval service to the FTS index. Proposals flow through the proposal manager, which coordinates with indexing and retrieval services to ensure consistency. See [[indexing-pipeline]] and [[mcp-integration]] for detailed workflows.

## Integration Points

The system integrates with the local filesystem for vault access, SQLite for indexing and proposal storage, and the MCP protocol for client communication. All operations are designed to be idempotent and transactionally consistent.
