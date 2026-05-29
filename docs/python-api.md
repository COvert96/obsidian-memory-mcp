# Python module boundaries

The supported product surface is the **MCP server** (`uv run mcp-memory serve`) and
**CLI** (`uv run mcp-memory`). Importing `obsidian_memory_mcp` is allowed for tests
and advanced embedding, but only the symbols listed below are intended for external
use. Everything else may change without a semver notice until a library release is
announced.

## Package layout convention

Every bounded-context package follows the same rules (see also
[system-architecture.md](system-architecture.md)):

1. **`__init__.py` is the public API** — explicit `__all__`; import other packages
   only through their `__init__.py`.
2. **`_models.py` holds domain dataclasses** — plural filename, no I/O imports.
3. **Underscore-prefixed files are internal** — e.g. `_guardrails.py`, `_resolver.py`.
4. **`repository.py` is persistence** — may be imported directly in tests.
5. **`service.py` or `manager.py` for orchestration** — one style per package, not both.

## Stable for tooling and contract tests

| Package / module | Symbols | Role |
|------------------|---------|------|
| `obsidian_memory_mcp.contracts` | `TOOL_CONTRACTS`, `TOOL_ERROR_CODES`, `ToolContract` | MCP tool metadata |
| `obsidian_memory_mcp.errors` | `ErrorCode`, `ERROR_CATALOG`, `ToolExecutionError`, `build_error` | Structured errors |
| `obsidian_memory_mcp.config` | `ConfigLoader`, `ConfigValidator`, `ProjectConfig`, … | Vault configuration |
| `obsidian_memory_mcp.server_registry` | `load_project_registry`, `ProjectRegistry` | Multi-project registry |

## Entry points (scripts)

| Entry | Module | Role |
|-------|--------|------|
| `mcp-memory` | `obsidian_memory_mcp.cli:main` | Operator CLI |
| `obsidian-memory-tokens` | `obsidian_memory_mcp.tokens:main` | Token estimation utility |
| MCP runtime | `obsidian_memory_mcp.server:mcp` | FastMCP application object |

## Domain packages

Import from the package root, not from `_` modules:

- `obsidian_memory_mcp.indexing` — `run_index`, `discover_markdown_files`, `parse_markdown`, `ParsedNote`, …
- `obsidian_memory_mcp.retrieval` — `ReadNoteService`, `SearchService`, …
- `obsidian_memory_mcp.context_packs` — `ContextPackLoader`, `IndexQueries`, …
  (`SqliteIndexQueries` lives in `context_packs._index_queries` for tests only)
- `obsidian_memory_mcp.writes` — `WriteService`, `WriteAuditEntry`, …

## Shared utility packages

| Package | Role |
|---------|------|
| `obsidian_memory_mcp.markdown` | Frontmatter, fence/heading helpers for reads and context-pack slicing |
| `obsidian_memory_mcp.indexing.parser` | Indexing-only note parse (`parse_markdown`, blocks, sections, FTS targets) |
| `obsidian_memory_mcp.utils` | Globs, hashing, vault path guards, timing, wikilink tokenization |

## CLI / support modules (not library API)

Top-level modules such as `server.py`, `status.py`, `search_debug.py`,
`benchmarks.py`, `migrations.py`, and `tokens.py` are operator or adapter code,
not semver-guaranteed imports.

## Top-level `__init__.py`

`obsidian_memory_mcp.__all__` re-exports config, contracts, errors, registry, and
`mcp` for convenience in tests and embedding experiments. This root namespace is
**not** semver-guaranteed until a library/PyPI release is announced.

| Symbol group | Examples |
|--------------|----------|
| Config | `ProjectConfig`, `ConfigLoader`, `GuardrailEvaluator` |
| Contracts / errors | `TOOL_CONTRACTS`, `ToolExecutionError` |
| Registry | `load_project_registry`, `ProjectRegistry` |
| Runtime | `mcp` (FastMCP app) |
| Tokens | `estimate_tokens` |

Prefer explicit submodule imports for new code.
