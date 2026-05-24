# PRD: Phase 2A - MCP SDK Bootstrap

## Introduction

Stand up a working MCP server runtime before Phase 2 indexing so the project validates protocol, transport, tool discovery, and error mapping early. This phase adopts the official `mcp` SDK (`FastMCP`) and keeps existing Phase 0-1 domain safety/config modules.

## Goals

- Adopt `mcp` SDK as the protocol/runtime layer.
- Add a running `mcp-memory serve` command using stdio transport.
- Register one working tool (`read_note`) as a thin adapter.
- Introduce project-to-vault registry mapping for multi-project runtime.
- Preserve existing config, path safety, and guardrail logic.

## User Stories

### US-001: Start MCP server from CLI
**Description:** As an operator, I need one command to start the MCP server so clients can connect and initialize.

**Acceptance Criteria:**
- [x] `mcp-memory serve` starts a long-running MCP server on stdio.
- [x] Server responds to MCP initialize handshake.
- [x] Startup failures are actionable (missing dependency, missing registry, invalid registry).

### US-002: Resolve projects through a server registry file
**Description:** As a tool caller, I need `project` identifiers to resolve consistently to vault roots.

**Acceptance Criteria:**
- [x] Server registry file maps `project -> vault_root` using YAML.
- [x] Unknown project returns `ERR_INVALID_PROJECT`.
- [x] Registry supports multiple projects in one server process.
- [x] Registry path can be provided explicitly to CLI.

### US-003: Register first FastMCP tool (`read_note`)
**Description:** As an MCP client, I need to discover and call a real tool to validate runtime wiring.

**Acceptance Criteria:**
- [x] `read_note` appears in MCP tool listing.
- [x] `read_note` resolves project registry, loads vault config, enforces guardrails, reads note content.
- [x] Missing files return `ERR_MISSING_FILE`.
- [x] Traversal/guardrail violations return `ERR_GUARDRAIL_VIOLATION`.

### US-004: Map domain errors to MCP tool errors
**Description:** As a client integrator, I need structured error payloads via MCP `isError` responses.

**Acceptance Criteria:**
- [x] Runtime errors map to MCP tool error responses with JSON payload containing `{code,message,details}`.
- [x] HTTP status is not required in runtime error model.
- [x] Existing error codes remain stable.

## Functional Requirements

- FR-1: Add `mcp>=1.27,<2` dependency.
- FR-2: Add `server.py` with FastMCP server factory and `read_note` handler registration.
- FR-3: Add `mcp-memory serve` CLI command and transport option (`stdio` default).
- FR-4: Add registry loader for project resolution.
- FR-5: Keep validation/contracts/schemas as documentation/verification artifacts, not runtime dispatch for FastMCP handlers.

## Non-Goals

- No indexing, retrieval ranking, context-pack assembly, or proposal persistence logic (handled in later phases).
- No HTTP auth, no UI, no background jobs.
- No auto-approve proposal policy in MVP.

## Dependencies

- Phase 0 complete (error codes, contracts/docs).
- Phase 1 complete (config loader, path normalization, guardrails).

## Deliverables

- `src/obsidian_memory_mcp/server.py` with FastMCP bootstrap and `read_note` tool handler.
- `src/obsidian_memory_mcp/server_registry.py` with project-to-vault mapping.
- `src/obsidian_memory_mcp/cli.py` updated with `serve` command.
- Unit tests for CLI serve wiring, registry resolution, FastMCP tool listing/calls, and mapped errors.

