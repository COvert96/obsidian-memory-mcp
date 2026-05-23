# PRD: Phase 4 - Context Packs with Token Budgets

## Introduction

Implement context packs: curated collections of files that can be loaded together with enforced token budgets. Context packs allow operators to pre-define reusable, coherent context bundles (e.g., "API documentation", "compliance policy", "architecture decisions") that tools can load in one operation while staying within a 1800-token hard cap.

## Goals

- Define context pack structure in config with file/section lists
- Load and concatenate pack content deterministically
- Enforce hard 1800-token limit per pack
- Report missing/stale files with clear warnings
- Enable efficient bulk context retrieval for LLM use

## User Stories

### US-001: Design context pack configuration schema
**Description:** As an operator, I need a clear way to define context packs in config so I can curate reusable collections.

**Acceptance Criteria:**
- [ ] Context pack defined in config under `context_packs` array
- [ ] Each pack has: `name` (required), `description`, `files` (required), `sections` (optional), `tags_filter` (optional)
- [ ] `files` supports: explicit paths (`wiki/api.md`), glob patterns (`wiki/architecture/**/*.md`), array of paths
- [ ] `sections` supports: specific section names to include (if empty, include whole file)
- [ ] Pack can mix whole files and specific sections
- [ ] Config validation catches: invalid paths, missing required fields, recursive packs
- [ ] Example config provided with 2-3 realistic packs

### US-002: Implement context pack loader
**Description:** As a developer, I need a loader that reads config packs and returns their content.

**Acceptance Criteria:**
- [ ] Loader takes pack name and returns concatenated markdown content
- [ ] Concatenation order matches config file order (deterministic)
- [ ] Each file/section prefixed with comment: `<!-- From: {file_path} -->`
- [ ] Headings preserved with context (no modification of markdown)
- [ ] Returns: `{ content: str, token_count: int, files_included: [str], missing_files: [str], warnings: [str] }`
- [ ] `token_count` uses estimator from Phase 0 (deterministic)
- [ ] Handles file not found without crashing (reports in missing_files list)
- [ ] Handles missing sections without crashing (reports in warnings, includes partial file)
- [ ] Performance: load pack in <500ms even for large packs

### US-003: Implement hard token cap enforcement
**Description:** As a developer, I need to enforce the 1800-token hard cap so packs don't exceed LLM context limits.

**Acceptance Criteria:**
- [ ] Token estimator from Phase 0 used to count tokens
- [ ] If `token_count > 1800`, error returned: `ERR_CONTEXT_EXCEEDS_BUDGET`
- [ ] Error includes: current token count, budget, how much must be removed, suggested smaller packs
- [ ] Option to load pack with soft truncation (warnings logged, content truncated to 1800 tokens)
- [ ] Truncation preserves file/section boundaries (doesn't cut mid-sentence)
- [ ] Warning logged if pack is >90% of budget (1620 tokens)

### US-004: Implement get_context_pack MCP tool
**Description:** As a tool user, I want to load a context pack in one call so I get curated, pre-sized context.

**Acceptance Criteria:**
- [ ] Tool parameter: `pack_name` (required), `strict_budget` (optional, default true)
- [ ] Returns: `{ content: str, token_count: int, pack_name: str, files_included: [str], missing_files: [str], warnings: [str] }`
- [ ] With `strict_budget=true`: returns error if pack exceeds 1800 tokens
- [ ] With `strict_budget=false`: truncates silently and returns with token_count <= 1800
- [ ] Missing files reported in response (not silent failure)
- [ ] Stale files detected: if `indexed_at` too old (e.g., >24 hours), warning issued
- [ ] Returns error `ERR_INVALID_PROJECT` if pack name not found in config

### US-005: Handle missing and stale files gracefully
**Description:** As an operator, I need visibility into pack health so I know if included files are accessible and current.

**Acceptance Criteria:**
- [ ] Pack loader detects files not in vault with clear message
- [ ] Pack loader detects sections not found in file with clear message
- [ ] Stale detection: compare file modification time with index time
- [ ] If file modified after indexing, warning: "File modified since last index; content may be stale"
- [ ] Tool response includes `warnings` array with actionable messages
- [ ] Missing files don't break pack loading (included files are returned with partial content)
- [ ] Operator can run `mcp-memory pack validate {pack_name}` to check all files/sections exist

### US-006: Create validation and status commands
**Description:** As an operator, I need CLI commands to validate packs and check their status.

**Acceptance Criteria:**
- [ ] Command: `mcp-memory pack list` — show all configured packs with name, description, file count, token estimate
- [ ] Command: `mcp-memory pack validate {pack_name}` — check all files/sections exist, show any missing/stale files
- [ ] Command: `mcp-memory pack load {pack_name}` — dry run to show content, token count, warnings
- [ ] Commands show: files included, token count estimate, any missing/stale files, total duration
- [ ] Exit code reflects health (0=ok, 1=errors, 2=warnings)

## Functional Requirements

- FR-1: Context pack configuration stored in `context_packs` array in config file
- FR-2: Pack loader concatenates files/sections in deterministic order
- FR-3: Token counter (from Phase 0) used for all token estimates
- FR-4: Hard cap: packs returning >1800 tokens fail with clear error
- FR-5: Missing/stale file detection with warnings in response
- FR-6: `get_context_pack` MCP tool implements pack loading
- FR-7: Token count always accurate and deterministic (same pack, same count every time)
- FR-8: CLI commands for pack validation and status

## Non-Goals

- No automatic pack optimization or compression
- No packing of binary files or assets
- No versioning or rollback of pack definitions
- No scheduled recompilation of packs
- No caching of pack content (generate on-demand for MVP)

## Technical Considerations

- **Token Estimation:** Use Phase 0 estimator; document expected drift vs actual LLM tokenization
- **File Ordering:** Maintain config file order for determinism; no alphabetical sorting
- **Concatenation Format:** Simple markdown with comment headers; no special formatting
- **Stale Detection:** Compare file `mtime` with index `indexed_at` timestamp
- **Truncation:** If soft cap enabled, truncate at last complete section boundary before 1800 tokens
- **Error Reporting:** Return all issues in response (don't stop at first error)

## Success Metrics

- [ ] Token count accurate within ±5% of actual LLM tokenization on 10 test packs
- [ ] Hard cap enforced: 100% of packs stay <=1800 tokens with strict_budget=true
- [ ] Missing file detection catches all missing files (100% accuracy)
- [ ] Pack load time <500ms on 5000-file vault with packs referencing 100+ files
- [ ] Operator can validate a pack and see all issues in <1 second
- [ ] Truncation preserves readability (no mid-sentence cuts, context preserved)

## Open Questions

- Should packs support versioning (e.g., "api-v1.2")?
  A: No.
- Should soft cap truncation prioritize files at start/end of pack or by relevance?
  A: By relevance.
- Should packs support nested pack inclusion (pack-in-pack)?
  A: No.
- Should missing sections be errors (fail pack) or warnings (partial file)?
  A: Warnings.
- Should operator be able to manually override token budget for specific packs?
  A: Yes.

## Dependencies

- Phase 0 must be complete (token estimator, error codes)
- Phase 1 must be complete (config loading)
- Phase 2 must be complete (indexing, file access, stale detection)
- Phase 3 helpful but not required (retrieve tools are independent)

## Deliverables

- `src/obsidian_memory_mcp/context_packs.py` with ContextPackLoader and pack validation
- `src/obsidian_memory_mcp/tools.py` — add MCP tool entry point for `get_context_pack`
- Updated `src/obsidian_memory_mcp/config.py` to support context_packs config schema
- `tests/unit/test_context_packs.py` with loader and token budget tests
- `tests/unit/test_context_pack_truncation.py` with truncation and boundary tests
- `tests/integration/test_context_pack_tools.py` with end-to-end pack loading
- CLI commands: `mcp-memory pack list`, `mcp-memory pack validate`, `mcp-memory pack load`
- `docs/context-packs-guide.md` with pack definition examples and best practices
