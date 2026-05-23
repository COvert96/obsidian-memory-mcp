# Architecture Design Document: Obsidian MCP Memory Server

## 1. Executive Summary

This project builds an MCP server that gives AI agents structured, safe access to Obsidian vaults for memory and context retrieval. The recommended architecture uses the official `mcp` Python SDK (maintained by Anthropic) for all protocol concerns — transport, JSON-RPC framing, tool registration, schema generation — and focuses custom development exclusively on the domain layer: vault access, guardrails, indexing, retrieval, and the proposal-based write workflow.

The project has completed Phase 0 (contracts, error model, validation) and Phase 1 (config, guardrails, path safety). Phases 0–1 produced high-quality domain logic that should be preserved. However, the contract-first approach built JSON schemas and validation infrastructure that overlaps with what the `mcp` SDK provides automatically. The migration path is to adopt the SDK as the server backbone, wire existing domain modules into FastMCP tool handlers, and retire the protocol-level scaffolding that the SDK makes redundant.

The result is a smaller codebase where the team writes domain logic and the SDK handles everything between the client and the tool handler function signature.

---

## 2. Problem Statement

The system solves two problems:

1. **AI agents lack persistent, structured project memory.** LLM context windows are ephemeral. Agents working on software projects need a way to retrieve relevant context (architecture docs, decisions, specifications) from a curated knowledge base without manual copy-pasting. Obsidian vaults are a natural fit because developers already use them for project documentation, and their markdown-plus-frontmatter format is machine-parseable.

2. **Unguarded vault writes are dangerous.** Allowing an AI agent to freely modify project documentation risks data loss, incoherent edits, or security violations (e.g., writing outside the vault). The system enforces a propose-approve workflow where agents can suggest changes but a human (or policy) must approve them.

**Why architectural guidance is needed now:** The project is entering Phase 2 (indexing), which introduces SQLite, a markdown parser, and the first real data pipeline. This is the last clean point to make foundational decisions — particularly whether to adopt the `mcp` SDK — before the implementation surface area grows significantly. Phases 3–5 each add MCP tool implementations that will be shaped by whatever server framework is in place.

---

## 3. Goals

1. Expose 7 MCP tools (read_note, read_section, search_notes, get_context_pack, propose_memory_update, list_proposals, approve_proposal) that AI agents can call via the MCP protocol.
2. Enforce vault isolation: all file access confined to the configured vault root, with configurable allow/deny path policies.
3. Provide deterministic full-text search over vault content using SQLite FTS5 — no embeddings, no GPU, no external services.
4. Support token-budgeted context packs: curated bundles of vault files that fit within a specified token limit.
5. Implement a propose-only write model: agents propose changes, operators approve them, with hash-based conflict detection and audit logging.
6. Support multi-project use: one MCP server can serve multiple vaults, each with its own configuration.
7. Ship as a pip-installable Python package that works on Windows, macOS, and Linux with Python 3.12+.

---

## 4. Non-Goals

- **Semantic/embedding search.** FTS5 is the search backend for the MVP. Embeddings may be added later if relevance is insufficient.
- **Automatic file watching.** Index updates are triggered manually via CLI. No filesystem watcher, no background daemon.
- **Authentication or multi-user access control.** The server runs locally. The operator is the trust boundary.
- **UI or web interface.** CLI and MCP protocol only.
- **Real-time collaboration.** Single-writer model; no conflict resolution beyond hash checking.
- **Non-markdown file types.** Only `.md` files with optional YAML frontmatter.
- **Plugin system or third-party extensibility.** The tool surface is fixed for the MVP.

---

## 5. Current Concerns

### Risk: Reinventing MCP protocol infrastructure

The project currently has zero dependency on the `mcp` Python SDK. Instead, Phase 0 built:

- `contracts.py` — hand-crafted tool contract definitions (name, description, error codes, examples)
- `validation.py` — JSON Schema Draft 2020-12 validation with a `validate_tool_handler` decorator
- 7 JSON schema files in `src/obsidian_memory_mcp/schemas/` — one per tool, defining request/response shapes
- `errors.py` — custom error codes, response model, error catalog with HTTP-style status codes

This infrastructure mirrors what the `mcp` SDK provides out of the box:

| Concern | Current project | `mcp` SDK |
|---|---|---|
| Tool registration | Manual `TOOL_CONTRACTS` dict | `@mcp.tool()` decorator |
| Input schema | Hand-written JSON Schema files | Auto-generated from Python type hints |
| Input validation | Custom `validate_tool_payload()` | Pydantic model validation |
| Error responses | Custom `ErrorResponse` dataclass | `CallToolResult(isError=True)` |
| Transport | Not implemented yet (Phase 6) | stdio, Streamable HTTP, SSE built-in |
| JSON-RPC framing | Not implemented yet | Full JSON-RPC 2.0 implementation |
| Capability negotiation | Not implemented yet | Automatic |

**Assessment:** Phases 0–1 produced solid domain logic (config loading, guardrails, path normalization, token estimation) that is genuinely custom. But the protocol scaffolding — schemas, validation decorators, contract definitions — duplicates SDK functionality. Continuing to build on this foundation means the project will eventually reimplement transport, framing, and capability negotiation (Phase 6's scope), which is exactly what the SDK exists to prevent.

### Risk: Over-engineering before validation

The project has detailed PRDs for 6 phases, extensive JSON specifications, machine-readable tool specs, and MCP inspector examples — but no working MCP server yet. The risk is that the specification-heavy approach delays feedback. A simpler path: stand up a working MCP server with 1–2 tools, validate it against a real vault, then iterate.

---

## 6. Key Architectural Decisions

### KAD-1: Use the `mcp` Python SDK for the server layer

**Decision:** Should the project use the official `mcp` Python SDK or build a custom MCP protocol implementation?

**Recommendation:** Adopt `mcp` (v1.27+) with its FastMCP high-level API.

**Rationale:**
- The SDK is maintained by Anthropic, MIT-licensed, with 23k+ GitHub stars and weekly releases.
- It handles JSON-RPC 2.0, transport (stdio, HTTP, SSE), capability negotiation, schema generation from type hints, and Pydantic-based validation.
- Building this from scratch would require thousands of lines of protocol code that the SDK already provides and tests.
- FastMCP's decorator pattern (`@mcp.tool()`) turns tool handlers into simple Python functions. The project's domain logic (vault access, guardrails) plugs in directly.

**Tradeoffs:**
- Adds `mcp` and its transitive dependencies (anyio, httpx, pydantic, starlette) to the project. This increases the dependency footprint from 3 packages to ~15.
- The SDK is at v1.x (beta label), though it's production-used by Anthropic's own tools. Breaking changes between major versions are possible.
- Pydantic replaces jsonschema for input validation. The existing JSON schema files become documentation rather than runtime artifacts.

**Reversibility:** Medium. Adopting the SDK shapes how tools are registered and how the server starts. Switching away later would require rewriting the server entry point and tool registration, but domain logic (vault access, indexing, proposals) remains untouched.

---

### KAD-2: Obsidian vault access via direct filesystem reads

**Decision:** How should the server access the Obsidian vault?

**Recommendation:** Continue using direct filesystem access (pathlib) through the existing `paths.py` module, guarded by `guardrails.py`.

**Rationale:**
- Obsidian vaults are local directories of markdown files. There is no Obsidian API needed — the vault is just a folder.
- The project already has robust path normalization (`paths.py`) with traversal protection, symlink resolution, and vault boundary enforcement.
- The guardrail evaluator (`guardrails.py`) implements glob-based allow/deny policies that are already tested.
- No network calls, no Obsidian plugin dependency, no sync issues.

**Tradeoffs:**
- Cannot access vaults that are only available via Obsidian Sync or cloud storage without local filesystem mounting.
- File locking is not implemented; concurrent writes from Obsidian and the MCP server could conflict. The proposal system mitigates this with hash-based conflict detection.

**Reversibility:** High. Vault access is behind a small interface (`paths.py` + `guardrails.py`). If an Obsidian API adapter were needed later, it could replace the filesystem calls without changing tool logic.

---

### KAD-3: Memory/context representation as plain markdown with YAML frontmatter

**Decision:** How should memories and context be represented in the vault?

**Recommendation:** Plain markdown files with YAML frontmatter for metadata. No custom binary format, no separate database for content.

**Rationale:**
- Obsidian already uses this format. Staying compatible means vault content is editable in Obsidian, visible in git, and diff-friendly.
- Frontmatter stores structured metadata (tags, type, project, dates). Body stores unstructured content.
- The SQLite database is an index, not the source of truth. The vault files are authoritative.

**Tradeoffs:**
- Querying structured data across files requires indexing (the SQLite layer). You cannot query frontmatter fields without first parsing and indexing them.
- No schema enforcement on frontmatter — files can have arbitrary or missing fields. Validation happens at index time, not write time.

**Reversibility:** High. This is the natural Obsidian format. Changing it would mean changing the tool, not the other way around.

---

### KAD-4: Agent queries via MCP tools; updates via proposal workflow

**Decision:** How should agents query and update memory?

**Recommendation:** Read operations (read_note, read_section, search_notes, get_context_pack) execute immediately and return results. Write operations go through the proposal workflow (propose_memory_update → list_proposals → approve_proposal).

**Rationale:**
- Reads are safe and idempotent — no reason to gate them beyond guardrail policies.
- Writes are dangerous in an AI agent context. The propose-approve model ensures a human reviews changes before they hit disk.
- Hash-based conflict detection (comparing file hash at proposal time vs. approval time) prevents lost updates if the file changed between proposal and approval.

**Tradeoffs:**
- The approval step adds friction. For workflows where agents need to write frequently (e.g., auto-journaling), this may be too slow. A future "auto-approve" policy per path could address this.
- Proposals expire (TTL-based). If not approved within the window, they must be recreated.

**Reversibility:** High. The proposal system is additive. Adding auto-approve or direct-write for specific paths is a policy change, not an architecture change.

---

### KAD-5: Project-specific context via per-vault configuration

**Decision:** How should project-specific context be separated from global/shared memory?

**Recommendation:** Each vault has its own `memory-mcp.yaml` configuration file. The MCP server loads configurations per vault path. There is no global configuration or shared memory store across vaults.

**Rationale:**
- The project already implements this in Phase 1 (`config/loader.py`, `config/model.py`). It works.
- Per-vault config means each project controls its own access policies, context packs, and index location.
- No cross-vault queries needed for MVP. Each `project` identifier in tool calls maps to a vault.

**Tradeoffs:**
- No shared memory across projects. If an agent needs context from multiple projects, it must query each separately.
- Config duplication: common patterns (e.g., default guardrails) must be copied across vaults. No config inheritance.

**Reversibility:** High. Adding a global config layer or cross-vault queries later would extend the existing model, not replace it.

---

### KAD-6: SQLite FTS5 for initial search and indexing

**Decision:** How should indexing and search work initially?

**Recommendation:** SQLite with FTS5 (full-text search), stored in a file specified by `index_db_location` in the vault config. Manual indexing via CLI.

**Rationale:**
- SQLite is in the Python standard library (no additional dependency). FTS5 is a built-in SQLite extension available in Python 3.12+.
- Deterministic ranking: same query always returns same results (unlike embedding-based search which depends on model versions).
- Fast enough: <100ms search latency for 5000-file vaults is achievable with FTS5.
- The Phase 2 PRD already specifies the schema: `files`, `sections`, `wikilinks` tables + `sections_fts` virtual table.

**Tradeoffs:**
- FTS5 is keyword-based. It won't find conceptually related content that doesn't share keywords. The 80% top-3 relevance target may be hard to hit for abstract queries.
- No built-in ranking by semantic relevance. BM25 (FTS5's ranking function) is the ceiling without adding a re-ranker.
- Index must be manually rebuilt when vault content changes. Stale index = stale search results.

**Reversibility:** Medium. Replacing SQLite FTS5 with an embedding-based search would require changing the indexer, the search service, and adding an embedding model dependency. But the tool interface (`search_notes`) stays the same — the change is internal.

---

### KAD-7: Configuration via YAML file in vault root

**Decision:** How should configuration be handled?

**Recommendation:** Keep the current approach: a `memory-mcp.yaml` file at the vault root, loaded and validated by `config/loader.py` and `config/validator.py`.

**Rationale:**
- Already implemented and tested in Phase 1.
- YAML is human-readable, supports comments, and is familiar to developers.
- The validator provides actionable error messages (field paths, recovery suggestions).
- Config is cached per vault path to avoid re-parsing on every tool call.

**Tradeoffs:**
- YAML parsing quirks (e.g., `yes`/`no` as booleans, implicit type coercion). The validator mitigates this with explicit type checks.
- No hot-reloading — config changes require server restart. Acceptable for MVP.

**Reversibility:** High. Config format can be changed without affecting domain logic, since all access goes through `ProjectConfig` dataclass.

---

### KAD-8: Errors, permissions, and unsafe file operations

**Decision:** How should errors, permissions, and safety be managed?

**Recommendation:** Layer safety at three levels:

1. **Path safety** (`paths.py`): Normalize paths, block traversal attacks, resolve symlinks, enforce vault boundary. This runs before any file I/O.
2. **Policy safety** (`guardrails.py`): Evaluate allow/deny glob patterns from config. Deny overrides allow. This runs after path normalization.
3. **Operation safety** (proposal system): Writes never happen directly. The proposal workflow provides a review step and hash-based conflict detection.

Error handling should use the existing `ErrorCode` enum and `ErrorResponse` model internally, mapped to MCP's `CallToolResult(isError=True, content=[TextContent(text=json)])` at the tool handler boundary.

**Rationale:**
- Defense in depth: even if one layer has a bug, the others catch the violation.
- The existing implementation is thorough — path traversal tests cover URL-encoded attacks, symlink escapes, Windows path normalization.
- Mapping to MCP's error model (isError flag on successful JSON-RPC responses) keeps protocol compliance simple.

**Tradeoffs:**
- Three safety layers add latency to every file operation (microseconds, not milliseconds — acceptable).
- The error model diverges from MCP's flat error string. The project's structured errors (code + message + details) provide better debugging but require serialization to text for MCP transport.

**Reversibility:** High. Safety layers are composable and independently testable.

---

## 7. Recommended Architecture

### Component diagram

```
┌──────────────────────────────────────────────────────────┐
│ MCP Client (Claude Code, Anthropic SDK, etc.)            │
└────────────────────┬─────────────────────────────────────┘
                     │ MCP Protocol (stdio / HTTP)
┌────────────────────▼─────────────────────────────────────┐
│ MCP Server Layer  (mcp SDK — FastMCP)                    │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Tool Handlers (thin adapter functions)               │ │
│ │  @mcp.tool() read_note(...)                          │ │
│ │  @mcp.tool() search_notes(...)                       │ │
│ │  @mcp.tool() get_context_pack(...)                   │ │
│ │  @mcp.tool() propose_memory_update(...)              │ │
│ │  ...                                                 │ │
│ └──────────┬───────────────────────────────────────────┘ │
└────────────┼─────────────────────────────────────────────┘
             │ Python function calls
┌────────────▼─────────────────────────────────────────────┐
│ Domain Layer  (project-specific, custom code)            │
│                                                          │
│ ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│ │ Config      │  │ Vault        │  │ Safety          │  │
│ │ loader.py   │  │ paths.py     │  │ guardrails.py   │  │
│ │ model.py    │  │              │  │ errors.py       │  │
│ │ validator.py│  │              │  │                 │  │
│ └─────────────┘  └──────────────┘  └─────────────────┘  │
│                                                          │
│ ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│ │ Indexing    │  │ Retrieval    │  │ Proposals       │  │
│ │ parser.py   │  │ reader.py    │  │ proposals.py    │  │
│ │ indexer.py  │  │ search.py    │  │ audit.py        │  │
│ │ schema.py   │  │ packs.py     │  │                 │  │
│ └─────────────┘  └──────────────┘  └─────────────────┘  │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ Storage: SQLite (FTS5 index, proposals, audit log)  │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ Vault Files: Markdown + YAML frontmatter (readonly) │  │
│ └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Component responsibilities

**MCP Server Layer** (`server.py` — new file)
- Uses `mcp.server.fastmcp.FastMCP` to create the server instance.
- Registers each tool via `@mcp.tool()` decorators.
- Tool handler functions are thin adapters: validate the `project` parameter, load config, call the appropriate domain service, catch domain exceptions, and return `CallToolResult`.
- Responsible for transport lifecycle (stdio for MVP, HTTP later).
- Does not contain business logic.

**Config** (`config/` — existing, keep as-is)
- `loader.py`: Loads and caches `memory-mcp.yaml` per vault path.
- `model.py`: Immutable dataclasses for `ProjectConfig`, `AccessPolicy`, `ContextPackConfig`.
- `validator.py`: Validates config fields, detects circular context pack references, produces actionable errors.
- `guardrails.py`: Evaluates read/write access policies using compiled glob patterns.

**Vault Access** (`paths.py` — existing, keep as-is)
- Normalizes vault-relative paths to absolute paths within the vault boundary.
- Blocks path traversal, symlink escapes, and absolute paths outside the vault.

**Safety** (`errors.py` — existing, adapt)
- `ErrorCode` enum and `ErrorResponse` dataclass stay.
- Add a helper to serialize `ErrorResponse` into MCP's `CallToolResult(isError=True)` format.
- Remove HTTP status codes from `ErrorDefinition` — MCP doesn't use HTTP status codes for tool errors.

**Indexing** (`parser.py`, `indexer.py`, `schema.py` — Phase 2, new)
- `parser.py`: Markdown parser extracting frontmatter, headings, sections, wikilinks from `.md` files.
- `schema.py`: SQLite schema creation (files, sections, wikilinks tables + FTS5 virtual table).
- `indexer.py`: Walks vault files, parses them, writes to SQLite. Supports full and incremental reindex using SHA-256 file hashes.

**Retrieval** (`reader.py`, `search.py`, `packs.py` — Phases 3–4, new)
- `reader.py`: Implements `read_note` and `read_section` by reading vault files through the safety layers.
- `search.py`: Implements `search_notes` using FTS5 queries with BM25 ranking.
- `packs.py`: Implements `get_context_pack` by loading configured file sets, concatenating content, and enforcing token budgets.

**Proposals** (`proposals.py`, `audit.py` — Phase 5, new)
- `proposals.py`: Manages the lifecycle of write proposals (create, list, approve, expire). Stores proposals in SQLite with hash snapshots.
- `audit.py`: Logs all proposal actions (created, approved, rejected, expired) to an audit table.

**Tokens** (`tokens.py` — existing, keep as-is)
- Token estimation using tiktoken's GPT-4 encoder. Used by context pack budget enforcement.

**CLI** (`cli.py` — existing, extend)
- `mcp-memory config validate <vault>` — existing.
- `mcp-memory index <vault>` — Phase 2.
- `mcp-memory serve` — Phase 6 (starts the MCP server).

**Tests** (`tests/` — existing, extend per phase)
- Unit tests for each domain module.
- Integration tests using a fixture vault.
- Acceptance tests verifying phase success criteria.

---

## 8. Data Model

### Vault files (source of truth)

```
vault-root/
├── memory-mcp.yaml          # Project configuration
├── wiki/
│   ├── concepts/
│   │   └── compliance.md     # Markdown note with frontmatter
│   └── decisions/
│       └── adr-001.md
├── docs/
│   └── prd/
│       └── master.md
└── Memory/                   # Agent-writable area (per guardrails)
    └── company-summary.md
```

### Markdown note structure

```yaml
---
type: concept                # Arbitrary frontmatter fields
tags: [compliance, policy]
created: 2026-01-15
---

# Compliance as Code

## Definition
Compliance controls encoded as executable rules.

## Benefits
- Automated verification
- Audit trail
```

### SQLite index schema (Phase 2)

```sql
-- Indexed vault files
CREATE TABLE files (
    id          INTEGER PRIMARY KEY,
    vault_path  TEXT NOT NULL UNIQUE,   -- Relative to vault root
    file_hash   TEXT NOT NULL,          -- SHA-256 of file content
    frontmatter TEXT,                   -- JSON-serialized frontmatter dict
    tags        TEXT,                   -- Comma-separated tags for filtering
    indexed_at  TEXT NOT NULL           -- ISO 8601 timestamp
);

-- Parsed sections within files
CREATE TABLE sections (
    id            INTEGER PRIMARY KEY,
    file_id       INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    heading       TEXT NOT NULL,
    heading_level INTEGER NOT NULL,     -- 1=H1, 2=H2, 3=H3
    content       TEXT NOT NULL,        -- Full section text including heading
    content_hash  TEXT NOT NULL,        -- SHA-256 of section content
    char_count    INTEGER NOT NULL,
    UNIQUE(file_id, heading_level, heading)
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE sections_fts USING fts5(
    heading, content,
    content=sections,
    content_rowid=id
);

-- Wikilinks between notes
CREATE TABLE wikilinks (
    id        INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    target    TEXT NOT NULL,            -- Wikilink target (e.g., "Page Name")
    display   TEXT                      -- Display text if different
);

-- Write proposals (Phase 5)
CREATE TABLE proposals (
    id          TEXT PRIMARY KEY,       -- UUID
    vault_path  TEXT NOT NULL,
    operation   TEXT NOT NULL,          -- "create", "update", "append"
    content     TEXT NOT NULL,
    old_hash    TEXT,                   -- NULL for create operations
    new_hash    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending, applied, rejected, expired
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    applied_at  TEXT
);

-- Audit log (Phase 5)
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    action      TEXT NOT NULL,          -- "created", "applied", "rejected", "expired"
    timestamp   TEXT NOT NULL,
    details     TEXT                    -- JSON with additional context
);
```

### Memory records

Memory records are regular markdown files in designated vault directories (e.g., `Memory/`). They follow the same format as any vault note. The "memory" semantics come from:

1. The guardrail policy allowing agent writes to `Memory/**`.
2. The context pack configuration including memory files in agent context.
3. Frontmatter conventions (e.g., `type: memory`, `source: agent`) — not enforced by the system, but useful for filtering.

There is no separate memory data model. Memories are vault files.

---

## 9. MCP Tool Surface

### Initial tool set (7 tools)

#### `read_note`
- **Purpose:** Read a full markdown note from the vault.
- **Inputs:** `project: str`, `note_path: str`
- **Outputs:** `project`, `file_path`, `content`, `frontmatter: dict`, `file_size_bytes: int`
- **Safety:** Path normalization, vault boundary check, read guardrail policy evaluation. Rejects paths outside vault or matching deny patterns.

#### `read_section`
- **Purpose:** Read a specific heading section from a note, with optional context lines.
- **Inputs:** `project: str`, `note_path: str`, `heading_name: str`, `context_lines: int = 2`
- **Outputs:** `project`, `file_path`, `heading`, `heading_level: int`, `content`, `context_lines: int`
- **Safety:** Same as `read_note`, plus section-not-found error if heading doesn't exist.

#### `search_notes`
- **Purpose:** Full-text search over indexed vault content.
- **Inputs:** `project: str`, `query: str`, `limit: int = 10`, `tags: list[str] = []`, `paths: list[str] = []`
- **Outputs:** `project`, `query`, `results: list[SearchResult]`, `returned_count: int`
- **Safety:** Query is parameterized (no SQL injection). Results filtered by read guardrail policy.

#### `get_context_pack`
- **Purpose:** Load a curated, token-budgeted bundle of vault files.
- **Inputs:** `project: str`, `pack_name: str`, `strict_budget: bool = True`
- **Outputs:** `project`, `pack_name`, `content: str`, `token_count: int`, `files_included: list[str]`, `missing_files: list[str]`, `warnings: list[str]`
- **Safety:** Token budget enforced (hard cap prevents context overflow). Missing files reported but don't fail the request.

#### `propose_memory_update`
- **Purpose:** Create a write proposal without modifying the vault.
- **Inputs:** `project: str`, `file_path: str`, `operation: str` ("create"|"update"|"append"), `content: str`
- **Outputs:** `project`, `proposal_id: str`, `file_path`, `operation`, `old_hash: str | null`, `new_hash: str`, `ttl_seconds: int`
- **Safety:** Write guardrail policy evaluated. File hash captured at proposal time for conflict detection. Content stored in SQLite, not written to disk.

#### `list_proposals`
- **Purpose:** List pending or filtered proposals.
- **Inputs:** `project: str`, `status: str = "pending"`, `limit: int = 10`
- **Outputs:** `project`, `proposals: list[Proposal]`, `returned_count: int`
- **Safety:** Read-only operation. Only shows proposals for the specified project.

#### `approve_proposal`
- **Purpose:** Apply a pending proposal to disk.
- **Inputs:** `project: str`, `proposal_id: str`
- **Outputs:** `project`, `proposal_id`, `file_path`, `operation`, `status: str`, `written_at: str`, `file_size_bytes: int`
- **Safety:** Re-checks write guardrail. Compares current file hash against proposal's `old_hash` — rejects if file changed since proposal was created (stale proposal). Writes atomically (write to temp file, then rename).

---

## 10. Build vs. Use Existing Package Analysis

### Option A: Use the `mcp` Python SDK

**What you get:**
- Full MCP protocol implementation (JSON-RPC 2.0, capability negotiation, message framing)
- Transport layer (stdio, Streamable HTTP, SSE)
- FastMCP: tool registration via `@mcp.tool()` decorators with automatic schema generation from type hints
- Pydantic-based input/output validation
- Resource and prompt primitives (if needed later)
- Maintained by Anthropic, MIT license, active development

**What you still build:**
- All domain logic (vault access, config, guardrails, indexing, retrieval, proposals)
- Tool handler functions (thin adapters calling domain services)
- CLI commands (indexing, config validation)
- SQLite schema and FTS5 integration
- Token estimation (keep existing `tokens.py`)

**Cost:**
- ~15 transitive dependencies (anyio, httpx, pydantic, starlette, etc.)
- Learning curve for FastMCP patterns (low — decorator-based, well-documented)
- Pydantic replaces jsonschema for input validation

### Option B: Build custom MCP protocol layer

**What you get:**
- Full control over protocol implementation
- Minimal dependencies (just jsonschema, pyyaml, tiktoken)

**What you build:**
- JSON-RPC 2.0 message parsing and framing
- MCP capability negotiation
- Transport layer (stdio at minimum)
- Tool registration and dispatch
- Schema generation and validation
- Error serialization
- All domain logic (same as Option A)

**Cost:**
- Estimated 1000–3000 lines of protocol code
- Ongoing maintenance burden as MCP spec evolves
- Testing burden for protocol edge cases
- No benefit to users — the protocol layer is invisible to them

### Option C: Hybrid (build partial protocol, use SDK for some parts)

Not recommended. The SDK is all-or-nothing for the server layer. Mixing custom JSON-RPC handling with SDK transport creates friction and maintenance burden with no clear benefit.

### Recommendation: Option A — Use the `mcp` SDK

The protocol layer is commodity infrastructure. Every hour spent reimplementing JSON-RPC framing or transport negotiation is an hour not spent on the domain logic that makes this project valuable. The SDK is maintained by the same organization that defines the MCP spec, so compatibility is guaranteed.

The existing Phase 0–1 code is not wasted. The domain modules (config, guardrails, paths, tokens, errors) are independent of the protocol layer and plug directly into FastMCP tool handlers. The JSON schema files become reference documentation rather than runtime artifacts.

---

## 11. Migration Plan

### What to keep (no changes needed)

| Module | Reason |
|---|---|
| `config/loader.py` | Clean config loading with caching. Works as-is. |
| `config/model.py` | Immutable dataclasses for config. Used by all domain code. |
| `config/validator.py` | Thorough validation with good error messages. |
| `config/guardrails.py` | Glob-to-regex policy evaluator. Core safety feature. |
| `paths.py` | Path normalization with security hardening. Critical. |
| `tokens.py` | Token estimation. Used by context packs. |

### What to adapt (modify, don't rewrite)

| Module | Change | Reason |
|---|---|---|
| `errors.py` | Add `to_mcp_error()` method on `ErrorResponse` that returns a `CallToolResult(isError=True)` with serialized error details. Remove `http_status` from `ErrorDefinition` (MCP doesn't use HTTP status codes for tool errors). | Bridge between domain error model and MCP protocol. |
| `cli.py` | Add `mcp-memory serve` command that starts the FastMCP server. Keep existing `config validate`. | Entry point for the MCP server. |
| `pyproject.toml` | Add `mcp` to dependencies. Add `mcp-memory serve` script entry point. | SDK integration. |

### What to retire (stop using at runtime, keep as documentation)

| Module | Action | Reason |
|---|---|---|
| `validation.py` | Stop using `validate_tool_handler` decorator. Keep `validate_tool_payload` if useful for testing. | FastMCP + Pydantic handle input validation. Tool handler type hints define the schema. |
| `schemas/*.json` | Move to `docs/schemas/` as reference documentation. | FastMCP auto-generates schemas from type hints. Hand-maintained JSON schemas will drift. |
| `contracts.py` | Keep as documentation of tool contracts and expected errors. Do not use for runtime dispatch. | `TOOL_CONTRACTS` captures design intent (which errors each tool can return, example payloads). This is valuable documentation, but runtime tool registration happens via FastMCP decorators. |

### What to build next (Phase 2 + SDK integration)

Phase 2 (indexing) and SDK integration can proceed in parallel or sequentially:

**Step 1: SDK integration (1–2 hours)**
1. `uv add mcp` — add SDK dependency.
2. Create `src/obsidian_memory_mcp/server.py` with a FastMCP instance.
3. Register a single tool (`read_note`) as a proof of concept. The handler loads config, normalizes the path, checks guardrails, reads the file, and returns content.
4. Add `mcp-memory serve` CLI command that calls `mcp.run(transport="stdio")`.
5. Test with MCP Inspector or Claude Code.

**Step 2: Phase 2 — Indexing (6–8 hours, per existing PRD)**
1. Build `parser.py` (markdown parser).
2. Build `schema.py` (SQLite schema).
3. Build `indexer.py` (indexing service).
4. Add `mcp-memory index` CLI command.
5. Tests per Phase 2 PRD.

**Step 3: Phase 3 — Retrieval tools (6–8 hours)**
1. Implement `read_note`, `read_section`, `search_notes` as FastMCP tool handlers backed by domain services.
2. Each tool handler: validate project → load config → call service → catch errors → return result.

**Step 4–6:** Continue Phases 4–6 per existing PRDs, with all tools registered as FastMCP handlers.

### Migration validation

After Step 1, validate:
- [ ] `mcp-memory serve` starts a server that responds to MCP `initialize` handshake.
- [ ] `read_note` tool appears in the server's tool list.
- [ ] Calling `read_note` with a valid vault path returns file content.
- [ ] Calling `read_note` with a path traversal attempt returns an error.
- [ ] Existing tests still pass (`uv run pytest`).

---

## 12. Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **MCP SDK breaking changes** in future major versions | Medium | Medium | Pin to `mcp>=1.27,<2`. Domain logic is SDK-independent, so upgrading only affects `server.py` and tool handler signatures. |
| 2 | **FTS5 relevance is too low** for meaningful search | Medium | High | Measure against benchmark queries (Phase 6). If <80% top-3, add BM25 tuning or a simple re-ranker before considering embeddings. |
| 3 | **Stale index** leads to missing search results | High | Medium | CLI warns when index is older than most recent vault file modification. Document the re-index workflow clearly. |
| 4 | **Concurrent vault modification** (Obsidian + MCP server) | Medium | Medium | Hash-based conflict detection on proposals. Read operations are safe (worst case: read a partially-written file). Document that operators should not approve proposals while actively editing the same file in Obsidian. |
| 5 | **Scope creep** — adding features before validating the MVP | Medium | High | The 7-tool surface is fixed. No new tools until Phase 6 is complete and benchmark results are reviewed. Resist adding embeddings, file watching, or plugins. |
| 6 | **Over-specified, under-validated** — detailed PRDs but no running server | High | Medium | SDK integration (Step 1 of migration) should happen immediately. A working server with 1 tool validates more assumptions than 6 PRDs. |
| 7 | **Windows compatibility issues** with SQLite FTS5 or path handling | Low | Medium | Python's built-in sqlite3 module includes FTS5 on all platforms since Python 3.12. Path normalization already handles Windows (tested). Run CI on Windows, macOS, and Linux. |
| 8 | **Token estimation drift** if tiktoken encoding diverges from actual model tokenization | Low | Low | The ±5% accuracy target is generous. Context pack budgets are soft limits (the hard cap is configurable). |

---

## 13. Decision Log Update (2026-05-23)

The following decisions are now locked for implementation and PRD alignment:

1. **Project registry:** Use a server-level registry file mapping `project -> vault_root`.
2. **Server lifecycle:** MVP runs as a long-running stdio server (`mcp-memory serve`).
3. **Auto-approve policies:** Out of MVP scope; keep manual approval workflow only.
4. **Context pack token budget:** Default budget is 8000 tokens with per-pack override.
5. **Async vs. sync:** Start with sync domain/tool handlers; revisit async only after profiling.
6. **Multi-vault server:** One server process may handle multiple projects through registry mapping.
7. **Index location:** Keep configurable via per-vault config (`index_db_location`).

---

## 14. Suggested Next Implementation Steps

**Priority 1 — Phase 2A: Stand up a working MCP server (immediately)**

1. Add `mcp` SDK dependency: `uv add mcp`.
2. Create `src/obsidian_memory_mcp/server.py` with FastMCP instance and one tool (`read_note`).
3. Wire the tool handler through existing config → paths → guardrails → file read pipeline.
4. Add `mcp-memory serve` CLI command.
5. Test with MCP Inspector: verify tool listing, successful reads, and error cases (bad path, traversal, guardrail violation).
6. Validate that Claude Code or another MCP client can connect and call the tool.

**Priority 2 — Phase 2: Indexing (per existing PRD)**

7. Build markdown parser (`parser.py`).
8. Build SQLite schema and indexer (`schema.py`, `indexer.py`).
9. Add `mcp-memory index` CLI command.
10. Write unit and integration tests.

**Priority 3 — Phase 3: Retrieval tools**

11. Implement `read_section` tool handler.
12. Implement `search_notes` tool handler backed by FTS5.
13. Benchmark search relevance against a small question set (don't wait for Phase 6 to start measuring).

**Priority 4 — Phases 4–5: Context packs and proposals**

14. Implement `get_context_pack` with token budget enforcement (default 8000, pack-level override).
15. Implement proposal workflow (propose, list, approve).
16. Add audit logging.

**Priority 5 — Phase 6: Polish and release**

17. Full benchmark suite and relevance measurement.
18. CI/CD pipeline.
19. Documentation and packaging.

---

## Appendix: Dependency comparison

### Current (Phase 0–1)

```
jsonschema>=4.25.1
pyyaml>=6.0.3
tiktoken>=0.13.0
```

3 direct dependencies.

### After adopting `mcp` SDK

```
mcp>=1.27,<2
pyyaml>=6.0.3
tiktoken>=0.13.0
```

3 direct dependencies (jsonschema becomes optional — only needed if keeping schema files for testing). The `mcp` package pulls in ~12 transitive dependencies (anyio, httpx, pydantic, starlette, etc.). Total installed packages increases from ~8 to ~25.

This is an acceptable tradeoff. The transitive dependencies are well-maintained, widely-used packages. The alternative is writing thousands of lines of protocol code to avoid them.
