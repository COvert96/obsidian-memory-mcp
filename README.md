# Obsidian Memory MCP

Obsidian Memory MCP is a local MCP server that gives AI clients guarded access to an Obsidian-style markdown vault. It provides deterministic retrieval with SQLite FTS5, token-budgeted context packs, and a proposal-based write workflow for memory updates.

Release status: MVP GitHub source release, version `0.1.0`. PyPI publication and hosted documentation are not part of this release.

## Features

- Read full notes and individual markdown sections from configured vaults.
- Search indexed markdown blocks with path, tag, and exclusion filters.
- Load curated context packs with strict or soft token budgets.
- Propose memory updates under `Memory/**` without writing immediately.
- List, approve, and reject proposals with audit trail support.
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

The live FastMCP server exposes 9 tools: `read_note`, `read_section`, `search_notes`, `get_context_pack`, `list_context_packs`, `propose_memory_update`, `list_proposals`, `approve_proposal`, and `reject_proposal`.

The canonical contract metadata lives in [src/obsidian_memory_mcp/contracts.py](src/obsidian_memory_mcp/contracts.py). See [docs/tool-reference.md](docs/tool-reference.md) and [docs/error-codes.md](docs/error-codes.md) for request fields, response fields, examples, error codes, and common workflows.

## Daily Operations

```powershell
uv run mcp-memory index C:\path\to\vault
uv run mcp-memory index status C:\path\to\vault
uv run mcp-memory debug search C:\path\to\vault "query terms" --limit 5
uv run mcp-memory proposals list C:\path\to\vault
uv run mcp-memory proposals show {proposal_id} C:\path\to\vault --diff
uv run mcp-memory proposals approve {proposal_id} C:\path\to\vault
uv run mcp-memory proposals reject {proposal_id} C:\path\to\vault --reason duplicate
uv run mcp-memory proposals cleanup C:\path\to\vault --retention-days 7 --yes
```

## Release Gates

```powershell
uv run ruff check
uv run mypy src
uv run pytest --cov=obsidian_memory_mcp --cov-report=term-missing --cov-report=xml --cov-fail-under=80 tests
uv run pytest tests/release
uv run mcp-memory benchmark relevance C:\path\to\fixture-vault --queries tests/benchmarks/benchmark-queries.yaml --min-accuracy 0.80
```

The benchmark command expects the vault to have a valid `memory-mcp.yaml` and a built index. The release test suite prepares an isolated copy of the fixture vault automatically.

## Safety Model

Reads and writes are constrained to the configured vault root. Path normalization blocks traversal and symlink escape attempts. Read and write guardrails use allow and deny glob patterns from `memory-mcp.yaml`; deny rules take precedence. MCP writes are proposal-based: a tool call can create a proposal, but content is not written until an approval step succeeds.

Do not share real private vault data, credentials, or personal data in public issues. See [SECURITY.md](SECURITY.md).

## Documentation

- [Vault setup](docs/vault-setup.md)
- [Indexing guide](docs/indexing-guide.md)
- [Retrieval guide](docs/retrieval-guide.md)
- [Context packs guide](docs/context-packs-guide.md)
- [Proposals guide](docs/proposals-guide.md)
- [Memory supersession guide](docs/memory-supersession-guide.md)
- [System architecture](docs/system-architecture.md)
- [Design history](docs/design-history.md)
- [Tool reference](docs/tool-reference.md)
- [Error codes](docs/error-codes.md)
- [Performance baseline](docs/performance-baseline.md)
- [Release checklist](docs/release-checklist.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).
