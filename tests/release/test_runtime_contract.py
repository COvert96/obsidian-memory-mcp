from __future__ import annotations

import anyio
import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.contracts import TOOL_CONTRACTS
from obsidian_memory_mcp.indexing import IndexMode, run_index
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


def _prepare_runtime_vault(tmp_path: Path) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.joinpath("wiki").mkdir(parents=True)
    vault.joinpath("Memory").mkdir()
    vault.joinpath(".mcp").mkdir()
    vault.joinpath("wiki", "concept.md").write_text(
        "---\ntags: [runtime]\n---\n# Runtime Concept\nLive MCP retrieval works.",
        encoding="utf-8",
    )
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["wiki/**/*.md"]
write_constraints:
  read:
    allow: ["wiki/**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(f'projects:\n  runtime: "{vault.as_posix()}"\n', encoding="utf-8")
    return vault, registry


def test_mcp_initialize_tool_discovery_and_runtime_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, registry = _prepare_runtime_vault(tmp_path)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    run_index(ConfigLoader(vault).load(), mode=IndexMode.FULL)

    async def exercise_server() -> None:
        async with create_connected_server_and_client_session(mcp) as client:
            tools = await client.list_tools()
            discovered_names = {tool.name for tool in tools.tools}

            assert discovered_names == set(TOOL_CONTRACTS)
            for tool in tools.tools:
                expected_request_fields = set(TOOL_CONTRACTS[tool.name].example_request)
                schema_fields = set(tool.inputSchema.get("properties", {}))
                assert expected_request_fields <= schema_fields

            result = await client.call_tool(
                "read_note",
                {"project": "runtime", "note_path": "wiki/concept.md"},
            )

            assert result.isError is False
            payload = json.loads(result.content[0].text)
            assert payload["project"] == "runtime"
            assert payload["file_path"] == "wiki/concept.md"
            assert "Live MCP retrieval works" in payload["content"]

    anyio.run(exercise_server)
