# Obsidian Memory MCP

Obsidian Memory MCP is a local MCP server that gives AI clients guarded access to an Obsidian-style markdown vault. It provides deterministic retrieval with SQLite FTS5, token-budgeted context packs, and direct atomic writes with audit logging for memory updates.

Release status: GitHub source release, version `0.2.0`. PyPI publication and hosted documentation are not part of this release.

## Features

- Read full notes and individual markdown sections from configured vaults.
- Search indexed markdown blocks with path, tag, and exclusion filters.
- Load curated context packs with strict or soft token budgets.
- Create and update memory files under `Memory/**` with guardrails and optimistic-lock hashes.
- Inspect the append-only `write_audit` log from the CLI.
- Run release gates, relevance benchmarks, and performance baseline checks from the repository.

## Requirements

- Python `>=3.12`
- `uv`
- Basic file system knowledge
- A local Obsidian-style markdown vault

## Quick Start

```powershell
git clone https://github.com/COvert96/obsidian-memory-mcp.git
cd obsidian-memory-mcp
uv sync --group dev
```

Create or choose a vault directory, then copy [config-example.yaml](config-example.yaml) to `{vault_root}/memory-mcp.yaml` and set `vault_path` to the absolute vault path.
Windows examples below use `C:\...`; on Linux/macOS use POSIX paths like `/home/user/vault`.

```powershell
uv run mcp-memory config validate C:\path\to\vault
uv run mcp-memory index --full --yes C:\path\to\vault
```

Create a server registry file named `memory-mcp-server.yaml` in this repository or pass it with `--registry-path`:

```yaml
projects:
  my-vault: "C:/path/to/vault"
```

Start the MCP server:

```powershell
uv run mcp-memory serve --registry-path memory-mcp-server.yaml
```

Verify the setup from an MCP client by calling `search_notes` with:

```json
{"project": "my-vault", "query": "architecture", "limit": 3}
```

## Tool Summary

The live FastMCP server exposes 9 tools: `read_note`, `read_section`, `search_notes`, `get_context_pack`, `list_context_packs`, `write_memory`, `update_memory`, `write_note`, and `update_note`.

The canonical contract metadata lives in [src/obsidian_memory_mcp/contracts/__init__.py](src/obsidian_memory_mcp/contracts/__init__.py). See [docs/tool-reference.md](docs/tool-reference.md) and [docs/error-codes.md](docs/error-codes.md) for request fields, response fields, examples, error codes, and common workflows.

## Daily Operations

```powershell
uv run mcp-memory index C:\path\to\vault
uv run mcp-memory index status C:\path\to\vault
uv run mcp-memory debug search C:\path\to\vault "query terms" --limit 5
uv run mcp-memory audit writes C:\path\to\vault --limit 50
```

## Release Gates

```powershell
uv run ruff check
uv run mypy --strict src
uv run python scripts/radon_gate.py
uv run pytest --cov=obsidian_memory_mcp --cov-report=term-missing --cov-report=xml --cov-fail-under=80 tests
uv run pytest tests/release
uv run mcp-memory benchmark relevance C:\path\to\fixture-vault --queries tests/benchmarks/benchmark-queries.yaml --min-accuracy 0.80
```

The benchmark command expects the vault to have a valid `memory-mcp.yaml` and a built index. The release test suite prepares an isolated copy of the fixture vault automatically.

## Python API

The supported integration surface is the **MCP server** (`uv run mcp-memory serve`) and **CLI** (`uv run mcp-memory`). Importing `obsidian_memory_mcp` is possible for tests and advanced embedding, but public symbols in `obsidian_memory_mcp.__all__` are not semver-guaranteed until a future library release is documented. See [docs/python-api.md](docs/python-api.md) for module boundaries and which `_`-prefixed files are internal.

## Safety Model

Reads and writes are constrained to the configured vault root. Path normalization blocks traversal and symlink escape attempts. Read and write guardrails use allow and deny glob patterns from `memory-mcp.yaml`; deny rules take precedence. MCP writes are direct and atomic: the CRUD write tools enforce the write guardrails, create-vs-update preconditions, and optimistic-lock hashes, and append every write to the `write_audit` log.

Do not share real private vault data, credentials, or personal data in public issues. See [SECURITY.md](SECURITY.md).

## Documentation

- [Vault setup](docs/vault-setup.md)
- [Indexing guide](docs/indexing-guide.md)
- [Retrieval guide](docs/retrieval-guide.md)
- [Context packs guide](docs/context-packs-guide.md)
- [Write tools guide](docs/write-tools-guide.md)
- [System architecture](docs/system-architecture.md)
- [Design history](docs/design-history.md)
- [Tool reference](docs/tool-reference.md)
- [Error codes](docs/error-codes.md)
- [Performance baseline](docs/performance-baseline.md)
- [Release checklist](docs/release-checklist.md)
- [Python API boundaries](docs/python-api.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).
