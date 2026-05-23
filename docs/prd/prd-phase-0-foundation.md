# PRD: Phase 0 - Foundation and Contracts

## Introduction

Establish the foundational architecture and contracts for the Obsidian Memory MCP system. This phase defines the tool API specifications, error handling model, request/response schemas, and validation strategy. A solid foundation ensures all downstream phases can be implemented reliably and consistently.

## Goals

- Define and specify all MCP tool contracts with precise payloads
- Establish a standardized error model with recoverable error codes
- Design schema validation strategy for deterministic token estimation
- Create acceptance tests proving tool specifications match implementation
- Set baseline for future tool additions

## User Stories

### US-001: Define MCP tool contract specifications
**Description:** As a developer, I need formal tool specifications so that implementation teams can build tools consistently.

**Acceptance Criteria:**
- [ ] Specification document lists all 7 tools: `read_note`, `read_section`, `search_notes`, `get_context_pack`, `propose_memory_update`, `list_proposals`, `approve_proposal`
- [ ] Each tool specifies: input parameters (with type, required/optional), output response structure, error cases
- [ ] Request/response schemas are JSON Schema compatible
- [ ] Example payloads provided for each tool (happy path + error case)
- [ ] Specification is valid YAML or JSON
- [ ] All tools can be invoked with the documented payloads

### US-002: Establish error model and codes
**Description:** As a developer, I need standardized error responses so client code can handle failures predictably.

**Acceptance Criteria:**
- [ ] Error code enumeration defined: `ERR_INVALID_PROJECT`, `ERR_MISSING_FILE`, `ERR_SECTION_NOT_FOUND`, `ERR_GUARDRAIL_VIOLATION`, `ERR_STALE_PROPOSAL`, plus any others identified
- [ ] Each error code has: short code, HTTP status, human-readable message template, recovery suggestion
- [ ] All 7 tools documented for which error codes they may return
- [ ] Error response schema: `{ "code": "ERR_...", "message": "...", "details": {...} }`
- [ ] Documentation shows how to handle each error type

### US-003: Design token estimation method for context budgets
**Description:** As a developer, I need a deterministic token counter so I can enforce the hard 1800-token cap for `get_context_pack`.

**Acceptance Criteria:**
- [ ] Decide on token estimation approach (e.g., fixed ratio like 1 token ≈ 4 characters, or BPE approximation)
- [ ] Estimate method is deterministic (same input always produces same count)
- [ ] Implement token counter function in codebase with clear docstring
- [ ] Provide utility for developers to test token count of strings/files
- [ ] Add test fixtures showing expected counts for known strings (5, 100, 1000 tokens)
- [ ] Confirm approach will not cause significant drift vs actual LLM tokenization

### US-004: Create schema validation test suite
**Description:** As a developer, I need automated validation of request/response payloads so malformed data fails fast and consistently.

**Acceptance Criteria:**
- [ ] JSON Schema files created for each tool request and response
- [ ] Test suite validates malformed inputs are rejected with clear error messages
- [ ] Test suite validates valid inputs pass validation
- [ ] Tests cover: missing required fields, wrong types, out-of-range values, invalid identifiers
- [ ] Validation error messages are developer-friendly (show expected schema, not just "validation failed")
- [ ] CI/CD integration: tests run on every commit

### US-005: Document error scenarios for each tool
**Description:** As a developer, I need clear examples of when and how each tool fails so I can write robust client code.

**Acceptance Criteria:**
- [ ] Documentation table: tool name → possible error codes → when it occurs → example response
- [ ] Covers both expected errors (missing file) and unexpected errors (DB connection failure)
- [ ] Include recovery suggestions (e.g., "retry with backoff", "check vault config", "contact operator")
- [ ] Examples are executable in MCP inspector

## Functional Requirements

- FR-1: Define input/output schema for all 7 MCP tools in JSON Schema format
- FR-2: Specify error code enum with HTTP status and message templates
- FR-3: Document which error codes each tool can return
- FR-4: Implement deterministic token counter (function signature: `estimate_tokens(text: str) -> int`)
- FR-5: Create validation layer that rejects non-conforming requests before tool execution
- FR-6: Provide clear, actionable error messages when validation fails
- FR-7: Ensure error responses include error code, message, and actionable details

## Non-Goals

- No implementation of actual tool logic (read files, search, etc.) — this is specification only
- No UI or client library for consuming errors (client side integration is Phase 6+)
- No performance optimization of token estimation beyond "deterministic"
- No semantic versioning or tool deprecation strategy (can be added in Phase 6)

## Technical Considerations

- **JSON Schema Approach:** Use `jsonschema` Python library for validation. Store schemas in YAML files in `src/obsidian_memory_mcp/schemas/`
- **Token Counter:** Use heuristic approach (1 token ≈ 4 characters for ASCII, adjust for special characters). Target ±5% accuracy vs GPT-3.5 tokenizer
- **Error Model:** Flat enum of error codes (no nested error types). Codes are string constants (e.g., `ERROR_INVALID_PROJECT = "ERR_INVALID_PROJECT"`)
- **Validation Location:** Implement as decorator on tool entry points so all tools validate before execution
- **Dependencies:** `jsonschema`, `pydantic` (optional, for typed validation), no new database dependencies

## Success Metrics

- [ ] All 7 tool specifications are unambiguous (can be handed to another developer with no questions)
- [ ] Token estimation tested on 50+ realistic markdown files, ±10% accuracy vs GPT-3.5
- [ ] 100% of invalid request payloads caught by validation (zero malformed requests reach tool code)
- [ ] Error messages are copy-pasted directly into documentation without rewording
- [ ] Test suite runs in <5 seconds, no flakiness across 10 consecutive runs

## Open Questions

- Should error codes be string enums or integer codes?
  A: String enums.
- Should token estimation account for markdown formatting (headings, links) or treat as plain text?
  A: Token estimation should account for markdown formatting.
- Is 1800-token hard cap per response, or per entire context pack retrieval?
  A: Token cap is per context pack.
- Should validation errors include suggested corrections (typo fixing)?
  A: Yes.

## Deliverables

- `src/obsidian_memory_mcp/schemas/` directory with tool `.json` schema files
- `src/obsidian_memory_mcp/errors.py` with error code enum and response class
- `src/obsidian_memory_mcp/tokens.py` with token estimation function
- `src/obsidian_memory_mcp/validation.py` with schema validation decorator
- `tests/unit/test_schemas.py` with comprehensive malformed/valid payload tests
- `docs/tool-specifications.md` with tool contracts, error codes, and examples
