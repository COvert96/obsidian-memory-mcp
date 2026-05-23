# PRD: Phase 1 - Project Config Loading and Safety Boundaries

## Introduction

Implement per-project configuration discovery, validation, and enforcement. Each Obsidian vault acts as a self-contained project with its own config file, vault boundaries, and access constraints. This phase ensures the system can safely load configuration and prevent directory traversal attacks or out-of-bounds file access.

## Goals

- Load project configuration from vault root with required field validation
- Enforce vault path boundaries so tools cannot read/write outside their vault
- Normalize file paths and validate against traversal attacks
- Provide clear error messages when configuration is invalid or missing
- Enable multi-project deployments with isolated configurations

## User Stories

### US-001: Implement config loader from vault root
**Description:** As a developer, I need to discover and load project config from vault root so each project can configure itself independently.

**Acceptance Criteria:**
- [x] Config file location: `{vault_root}/memory-mcp.yaml` (single config per vault)
- [x] Config loader reads YAML file and parses into typed config object
- [x] Returns error with actionable message if config file not found
- [x] Returns error if YAML is malformed (invalid syntax)
- [x] Config object supports accessing required and optional fields
- [x] Loader caches config in memory after first load (reload on next request is acceptable for MVP)

### US-002: Define config schema and required fields
**Description:** As a developer, I need to know what fields are required and optional so I can validate user configs correctly.

**Acceptance Criteria:**
- [x] Config schema documented with all required fields:
  - `vault_path`: absolute path to vault root (required)
  - `index_db_location`: path to SQLite index database (required)
  - `context_packs`: array of context pack definitions (required)
  - `write_constraints`: object defining allowed/forbidden paths (required)
- [x] Optional fields defined (e.g., `tags_separator`, `max_proposal_ttl_hours`)
- [x] Schema example config created at `docs/config-example.yaml`
- [x] Validation catches missing required fields with clear error message
- [x] Type checking on all fields (string, array, object, etc.)

### US-003: Validate config fields and provide clear errors
**Description:** As a developer, I need validation errors to tell me exactly what is wrong and how to fix it.

**Acceptance Criteria:**
- [x] Validation function returns list of all validation errors (not just first one)
- [x] Error messages include: field name, expected type/format, actual value, suggestion
- [x] Example error: "Field 'vault_path' must be an absolute path. Got 'relative/path'. Use '/full/path' instead."
- [x] Validation handles: missing required fields, wrong types, invalid path formats, circular references in context packs
- [x] Validation rejects absolute paths that don't exist on disk (if they're meant to point to directories)
- [x] Tests cover 10+ validation scenarios

### US-004: Enforce vault boundary for path traversal prevention
**Description:** As a developer, I need path normalization and boundary checking so malicious or accidental `../` sequences don't escape the vault.

**Acceptance Criteria:**
- [x] Path resolver function: `normalize_vault_path(vault_root: str | Path, requested_path: str | Path) -> Path`
- [x] Function rejects paths containing `..`, absolute paths outside vault, symlinks to outside vault
- [x] Returns error: `ERR_GUARDRAIL_VIOLATION` if path escapes vault
- [x] Resolves `.` and handles trailing slashes correctly
- [x] Test suite verifies 15+ attempted traversals are blocked:
  - `../../etc/passwd`
  - `/etc/passwd` (absolute path outside vault)
  - Symlink to parent directory
  - `vault_root/../sibling_vault`
  - etc.
- [x] Legitimate paths within vault pass through correctly

### US-005: Create guardrail evaluator for write constraints
**Description:** As an operator, I need to configure which paths tools can read/write so I can protect sensitive vault files.

**Acceptance Criteria:**
- [x] Guardrail evaluator checks whether a path is allowed for read/write
- [x] Config supports patterns: explicit paths (`wiki/index.md`), glob patterns (`wiki/**/*.md`), directory patterns (`wiki/`)
- [x] Default-deny: paths not explicitly allowed are rejected
- [x] Supports separate allow lists for read vs write
- [x] Example config shows: allow read from entire wiki, allow write to `wiki/proposals/`, deny write to `wiki/log.md`
- [x] Error returned: `ERR_GUARDRAIL_VIOLATION` with clear message about which constraint was violated
- [x] Performance: guardrail check completes in <1ms

### US-006: Document vault setup workflow
**Description:** As an operator, I need step-by-step instructions so I can set up a new vault correctly.

**Acceptance Criteria:**
- [x] Vault setup guide in `docs/vault-setup.md` covering:
  - Creating vault directory structure
  - Generating memory-mcp.yaml config
  - Validating config with CLI tool
  - Understanding guardrails and write constraints
- [x] Includes example config for common scenarios (read-heavy wiki, writable memory vault)
- [x] Links to error reference for common mistakes
- [x] Walkthrough is doable in <10 minutes for operator with basic file system knowledge

## Functional Requirements

- FR-1: Config loader discovers and reads `{vault_root}/memory-mcp.yaml`
- FR-2: Implement schema validator with clear multi-error reporting
- FR-3: Path normalizer prevents directory traversal and symlink escapes
- FR-4: Guardrail evaluator enforces read/write constraints via pattern matching
- FR-5: All file operations in subsequent phases check guardrails before access
- FR-6: Config validation CLI tool: `mcp-memory config validate /path/to/vault`
- FR-7: Graceful error handling: invalid config fails fast with helpful message, doesn't proceed to other phases

## Non-Goals

- No dynamic config reloading during MCP server lifetime (reload on restart is acceptable)
- No support for environment variable interpolation in config (hardcoded paths only for MVP)
- No config encryption or secrets management (assume vault filesystem is protected)
- No automated config migration or version handling

## Technical Considerations

- **Config Storage:** YAML, simple flat structure, no nested includes
- **Path Handling:** Use Python `pathlib.Path` for normalization, `os.path.realpath()` for symlink resolution
- **Validation:** Custom validator class, not third-party schema language (keeps dependencies light)
- **Error Reporting:** Collect all validation errors before failing, return as list
- **Guardrail Matching:** Use `fnmatch` for glob patterns, explicit string matching for direct paths
- **Startup Order:** Config validation happens first; if invalid, MCP server does not start

## Success Metrics

- [ ] Operator can set up a new vault in <10 minutes following docs
- [ ] All 15+ path traversal tests pass; zero successful escapes
- [ ] Guardrail check latency <1ms (measured on path with 10+ rules)
- [ ] Invalid config produces <30 second startup time (fail fast)
- [ ] Validation errors are actionable (operator can fix without asking for help)

## Open Questions

- Should config support relative paths (relative to vault root)?
  A: Yes.
- Should context pack definitions be in same config file or separate `.yaml` files in `{vault}/.mcp/`?
  A: Same config file.
- Should write_constraints support inheritance or override behavior (e.g., deny all except list)?
  A: Unsure, you decide.
- Should we validate that index_db_location is writable, or just readable vault_path?
  A: Just readable vault_path.

## Dependencies

- Phase 0 must be complete (error codes `ERR_GUARDRAIL_VIOLATION`, `ERR_INVALID_PROJECT` are defined)
- No dependency on Phase 2 (ingestion) — config validation is standalone

## Deliverables

- `src/obsidian_memory_mcp/config.py` with ConfigLoader, ConfigValidator, GaudrailEvaluator
- `src/obsidian_memory_mcp/paths.py` with path normalization and symlink resolution
- `docs/config-example.yaml` with annotated example configuration
- `docs/vault-setup.md` with operator walkthrough
- `tests/unit/test_config_validation.py` with 20+ test cases
- `tests/unit/test_path_traversal.py` with 15+ traversal attack scenarios
- `tests/unit/test_guardrails.py` with pattern matching and constraint scenarios
- CLI command `mcp-memory config validate /path/to/vault`
