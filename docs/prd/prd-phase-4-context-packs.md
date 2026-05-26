# PRD: Phase 4 - Context Packs with Token Budgets

## Introduction

Implement context packs: curated collections of files that can be loaded together with enforced token budgets. Context packs allow operators to pre-define reusable, coherent context bundles (e.g., "API documentation", "compliance policy", "architecture decisions") that tools can load in one operation while staying within a strict token cap (default 8000 tokens).

## Architecture Alignment Update (2026-05-23)

- `get_context_pack` must be exposed through a FastMCP thin handler adapter, following the same pattern as `read_note`, `read_section`, and `search_notes` in `server.py`.
- Project resolution must use the shared server registry from Phase 2A (`server_registry.py`).
- Default budget target for examples/specs is **8000 tokens**; per-pack `token_budget` overrides are supported.
- The `get_context_pack` tool contract already exists in `contracts.py` but is **not yet registered** in `server.py`. Phase 4 adds the runtime implementation and server registration. This transitional state is intentional and not a bug.

## Why Now

Build Phase 4 now because:
1. Operators repeatedly load the same document bundles across sessions via multiple `read_note` / `search_notes` calls, leading to inconsistent context assembly.
2. Multi-call retrieval latency and manual stitching are recurring friction points.
3. There is no current mechanism to enforce a token budget across a bundle of files — clients may silently exceed prompt budgets.

Defer if: current `read_note` + `search_notes` workflows are sufficient and budget overruns have not been observed in practice.

## Goals

- Extend config schema to support context pack definitions with file path patterns, optional section targeting, tag filtering, and nested pack inclusion
- Load and concatenate pack content deterministically, in config-declared order
- Enforce hard token limits per pack (default 8000 tokens), with soft-truncation mode
- Report missing/stale files with clear, actionable warnings
- Enable efficient bulk context retrieval for LLM use in a single tool call

## Config Schema

Context packs are defined in the `context_packs` array in `memory-mcp.yaml`. The schema below reflects the **actual implemented model** in `src/obsidian_memory_mcp/config/model.py`, extended with the new fields added in Phase 4.

### ContextPackConfig fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique identifier for the pack. Used as the `pack_name` argument in `get_context_pack`. |
| `paths` | list[string] | Yes | File path patterns to include. Supports explicit relative paths (`wiki/api.md`) and glob patterns (`wiki/architecture/**/*.md`). Evaluated in order; files are included in declaration order. |
| `description` | string | No | Human-readable summary of what this pack contains. Shown by `mcp-memory pack list`. |
| `sections` | list[string] | No | Section heading names to include from matched files. If empty or omitted, the entire file is included. If a named section is not found in a file, a warning is issued and the full file is included as a fallback. Matching is case-insensitive. |
| `tags_filter` | list[string] | No | If set, only files whose frontmatter tags contain **all** listed tags are included. Files without frontmatter tags are excluded. |
| `include_context_packs` | list[string] | No | Names of other packs whose resolved file lists are merged into this pack (after this pack's own `paths`). Circular references are detected at config validation time and reported as errors. Self-reference is also an error. |
| `token_budget` | integer | No | Per-pack token cap. Overrides the server default of 8000. Must be a positive integer. |

### Example config

```yaml
context_packs:
  - name: api-docs
    description: "Public API reference and usage examples"
    paths:
      - wiki/api/**/*.md
    token_budget: 6000

  - name: architecture
    description: "Architecture decisions and system overview"
    paths:
      - docs/architecture/overview.md
      - docs/adr/**/*.md
    sections:
      - Decision
      - Context

  - name: compliance-bundle
    description: "API docs plus compliance policy"
    paths:
      - docs/compliance/policy.md
    include_context_packs:
      - api-docs
    tags_filter:
      - compliance
```

## User Stories

### US-001: Design context pack configuration schema
**Description:** As an operator, I need a clear way to define context packs in config so I can curate reusable collections.

**Acceptance Criteria:**
- [x] Context pack defined in config under `context_packs` array
- [x] Each pack has: `name` (required), `description` (optional), `paths` (required), `sections` (optional), `tags_filter` (optional), `include_context_packs` (optional), `token_budget` (optional)
- [x] `paths` supports: explicit vault-relative paths and glob patterns; evaluated in declaration order
- [x] `sections` supports: list of case-insensitive heading names; if omitted, full file is included
- [x] `tags_filter` supports: list of tags that must all be present on each matched file
- [x] `include_context_packs` supports: named pack references that are merged after this pack's own paths, with cycle detection
- [x] Config validation catches: missing required fields, duplicate pack names, unknown pack references, circular `include_context_packs`, non-positive `token_budget`
- [x] Example config provided with 2-3 realistic packs in the documentation

### US-002: Implement context pack loader
**Description:** As a developer, I need a loader that reads config packs and returns their content deterministically.

**Acceptance Criteria:**
- [x] Loader takes `pack_name` and `ProjectConfig` and returns a structured result
- [x] Concatenation order: config declaration order; included packs appended after the including pack's own files
- [x] Each file prefixed with `<!-- From: {vault_relative_path} -->`
- [x] Markdown headings and content preserved exactly (no reformatting)
- [x] If `sections` is specified: only matching heading blocks are concatenated; full file used as fallback if no sections match
- [x] If `tags_filter` is specified: files not matching all tags are silently skipped (not counted as missing)
- [x] Returns: `{ content: str, token_count: int, files_included: list[str], missing_files: list[str], warnings: list[str] }`
- [x] `token_count` uses the Phase 0 token estimator (deterministic, no LLM calls)
- [x] Files not found in the vault are reported in `missing_files`, not `files_included`; pack loading continues with remaining files
- [x] Missing sections emit a warning and fall back to including the full file
- [x] Performance: load pack in <500ms on a 5000-file vault with packs referencing 100+ files

### US-003: Implement hard token cap enforcement
**Description:** As a developer, I need to enforce the configured token cap so packs stay within budget.

**Acceptance Criteria:**
- [x] Phase 0 token estimator used for all counts
- [x] `strict_budget=true` (default): if `token_count > configured_budget`, return error `ERR_CONTEXT_EXCEEDS_BUDGET`
- [x] Error response includes: `current_token_count`, `budget`, `excess_tokens` (how much must be removed), and a suggestion to use a smaller pack or `strict_budget=false`
- [x] `strict_budget=false`: truncate content at the last complete section boundary that fits within the budget; return truncated content with truncation details in the `warnings` array (never silent)
- [x] Truncation is relevance-prioritized: files are ordered by BM25 score from the pack's file set before truncation; highest-ranked content is preserved
- [x] Warning issued if `token_count > 90% of configured_budget` (i.e., > 7200 for the default 8000-token budget); also applies after truncation
- [x] Truncation never cuts mid-sentence or mid-section; always ends at a section boundary

### US-004: Implement get_context_pack MCP tool
**Description:** As a tool user, I want to load a context pack in one call so I receive curated, pre-sized context.

**Acceptance Criteria:**
- [x] Tool registered in `server.py` under the name `get_context_pack`, following the FastMCP pattern used by `read_note` / `read_section`
- [x] Parameters: `project` (required), `pack_name` (required), `strict_budget` (optional, default `true`)
- [x] Returns: `{ content: str, token_count: int, pack_name: str, files_included: list[str], missing_files: list[str], warnings: list[str] }`
- [x] `strict_budget=true`: returns `ERR_CONTEXT_EXCEEDS_BUDGET` if pack exceeds configured budget
- [x] `strict_budget=false`: returns truncated content; truncation details always present in `warnings`
- [x] Missing files reported in `missing_files` (not silent)
- [x] Stale files: if a file's `mtime_ns > indexed_at` in the index DB, a warning is added: `"File '{path}' has been modified since last index; content may be stale"`
- [x] `ERR_INVALID_PROJECT` returned if the `project` argument is not found in the registry, or if `pack_name` is not found in the project's config

### US-005: Handle missing and stale files gracefully
**Description:** As an operator, I need visibility into pack health so I know if included files are accessible and current.

**Acceptance Criteria:**
- [x] Pack loader detects files not in the vault and reports them in `missing_files` with the vault-relative path
- [x] Pack loader detects sections not found in a file; reports in `warnings`, includes the full file as fallback
- [x] Stale detection: compare `files.mtime_ns` (file system modification time, nanoseconds) with `files.indexed_at` (index timestamp) from the index DB. If `mtime_ns > indexed_at`, the file is considered stale.
- [x] No age-based stale threshold (e.g., "24 hours old") — stale means "changed since last index", not "indexed too long ago"
- [x] Stale warning message: `"File '{path}' has been modified since last index; content may be stale. Re-run indexing to refresh."`
- [x] Missing files do not abort pack loading; remaining matched files are returned
- [x] `mcp-memory pack validate {pack_name}` command checks all files/sections and reports missing, stale, and tag-filtered items

### US-006: Create validation and status CLI commands
**Description:** As an operator, I need CLI commands to validate packs and check their status.

**Acceptance Criteria:**
- [x] `mcp-memory pack list` — print a table of all configured packs showing: name, description, file-pattern count, estimated token count, any known issues
- [x] `mcp-memory pack validate {pack_name}` — resolve all paths, check section existence, report missing/stale files; exit code 0 (ok), 1 (errors), 2 (warnings only)
- [x] `mcp-memory pack load {pack_name}` — dry-run: print full concatenated content, token count, warnings, total duration; does not require `--dry-run` flag
- [x] All commands show: files included, token count, missing/stale files, total elapsed time
- [x] Exit codes: 0 = ok, 1 = missing files or config errors, 2 = warnings (stale files, near-budget)

## Functional Requirements

- FR-1: Context pack configuration stored in `context_packs` array in `memory-mcp.yaml`; schema validated by `ConfigValidator` in `config/validator.py`
- FR-2: Pack loader concatenates files/sections in deterministic, config-declaration order
- FR-3: Phase 0 token estimator used for all token counts; counts are deterministic (same pack = same count every time)
- FR-4: Hard cap: packs exceeding the configured budget (default 8000 tokens) fail with `ERR_CONTEXT_EXCEEDS_BUDGET` when `strict_budget=true`
- FR-5: Soft cap: packs truncated to budget at the last section boundary when `strict_budget=false`; truncation details always in `warnings`
- FR-6: Stale detection uses change-based comparison only: `mtime_ns > indexed_at`
- FR-7: Missing files, missing sections, and stale files all reported in the response; pack loading continues with available files
- FR-8: `get_context_pack` registered in `server.py` as a FastMCP tool
- FR-9: CLI commands `pack list`, `pack validate`, `pack load` added to `cli.py`
- FR-10: `include_context_packs` references are resolved transitively; circular references are rejected at config validation time

## Non-Goals

- No automatic pack optimization or compression
- No packing of binary files or assets
- No versioning or rollback of pack definitions
- No scheduled recompilation of packs
- No caching of pack content (generate on-demand for MVP)
- No age-based stale threshold ("indexed more than 24 hours ago" is not a staleness signal)

## Technical Considerations

- **Token Estimation:** Use Phase 0 estimator; document expected drift vs actual LLM tokenization in `docs/context-packs-guide.md`
- **File Ordering:** Maintain config declaration order for determinism; glob expansion within a pattern is sorted lexicographically for stability
- **Concatenation Format:** `<!-- From: {vault_relative_path} -->\n{content}\n\n` per file/section
- **Stale Detection:** Query `files` table: `SELECT vault_path, mtime_ns, indexed_at FROM files WHERE vault_path = ?`; warn if `mtime_ns > indexed_at`
- **Truncation:** When `strict_budget=false`, order files by BM25 relevance score (reuse existing `SearchService` ranking), then greedily include files until budget is reached; truncate at the last complete section boundary
- **Relevance Signal for Truncation:** Use pack `paths` patterns as the query scope for BM25 ranking. If no ranking signal is available (no FTS index), fall back to config declaration order
- **Error Reporting:** Collect all issues before returning; never stop at first error
- **Nested Packs:** `include_context_packs` is resolved recursively in topological order; files from included packs are appended after the including pack's own resolved files; duplicates (same vault path appearing via multiple include paths) are deduplicated, first occurrence wins
- **Transitional State:** `get_context_pack` already has a contract in `contracts.py` and an error code in `errors.py`. Phase 4 adds the runtime implementation in `context_packs.py` and the server registration in `server.py`. No contract changes are required.

## Success Metrics

- [ ] Token count accurate within ±5% of actual LLM tokenization on 10 test packs
- [ ] Hard cap enforced: 100% of packs stay ≤ configured budget with `strict_budget=true`
- [ ] Missing file detection catches all missing files (100% accuracy)
- [ ] Pack load time <500ms on 5000-file vault with packs referencing 100+ files
- [ ] Operator can validate a pack and see all issues in <1 second
- [ ] Truncation preserves readability: no mid-sentence cuts, no broken section headers

## Dependencies

- Phase 0 must be complete (token estimator, error codes) ✅
- Phase 1 must be complete (config loading) ✅
- Phase 2A must be complete (FastMCP server bootstrap and project registry) ✅
- Phase 2 must be complete (indexing, file access, stale detection via `mtime_ns` / `indexed_at`) ✅
- Phase 3 helpful but not required (retrieval tools are independent) ✅

## Deliverables

- `src/obsidian_memory_mcp/context_packs.py` — `ContextPackLoader` class and pack resolution logic
- `src/obsidian_memory_mcp/server.py` — add `get_context_pack` FastMCP tool registration
- `src/obsidian_memory_mcp/config/model.py` — extend `ContextPackConfig` with `description`, `sections`, `tags_filter` fields
- `src/obsidian_memory_mcp/config/validator.py` — extend `ConfigValidator._validate_context_packs` to validate new fields
- `src/obsidian_memory_mcp/cli.py` — add `pack list`, `pack validate`, `pack load` sub-commands
- `tests/unit/test_context_packs.py` — loader, token budget, and missing-file tests
- `tests/unit/test_context_pack_truncation.py` — truncation, section-boundary, and relevance-ordering tests
- `tests/integration/test_context_pack_tools.py` — end-to-end pack loading via the MCP tool
- `docs/context-packs-guide.md` — pack definition examples, token estimation notes, and best practices

## Open Questions

*(All resolved — recorded here for traceability.)*

- **Should packs support versioning (e.g., "api-v1.2")?**
  Resolved: No.

- **Should soft-cap truncation prioritize files at start/end of pack or by relevance?**
  Resolved: By relevance (BM25 ranking from the existing FTS index).

- **Should packs support nested pack inclusion (pack-in-pack)?**
  Resolved: Yes. `include_context_packs` is already implemented in `config/model.py` and `config/validator.py` with topological cycle detection. The feature is kept and supported in Phase 4.

- **Should missing sections be errors (fail pack) or warnings (partial file)?**
  Resolved: Warnings; full file included as fallback.

- **Should the operator be able to manually override token budget for specific packs?**
  Resolved: Yes, via `token_budget` on the pack.

- **Should staleness be age-based, change-based, or both?**
  Resolved: Change-based only — `mtime_ns > indexed_at`. Age-based thresholds are not used.

- **Should section-level targeting and relevance-prioritized truncation be Phase 4 MVP or deferred?**
  Resolved: Both are Phase 4 MVP.
