from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


def _call(tool: str, arguments: dict) -> dict:
    content_blocks, _structured = asyncio.run(mcp.call_tool(tool, arguments))
    return json.loads(content_blocks[0].text)


def _prepare_vault(tmp_path: Path) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    (vault / "docs").mkdir(parents=True)
    (vault / "docs" / "guide.md").write_text("# Guide\nBody.", encoding="utf-8")
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: memory-index.sqlite3
context_packs:
  - name: docs
    description: "General project docs"
    paths: ["docs/*.md"]
  - name: tiny
    description: "Small budget test pack"
    paths: ["docs/*.md"]
    token_budget: 1
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**"]
""",
        encoding="utf-8",
    )
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(
        f'projects:\n  sample: "{vault.as_posix()}"\n', encoding="utf-8"
    )
    return vault, registry


def test_server_exposes_context_pack_tools() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert any(tool.name == "get_context_pack" for tool in tools)
    assert any(tool.name == "list_context_packs" for tool in tools)


def test_list_context_packs_returns_configured_pack_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _vault, registry = _prepare_vault(tmp_path)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    payload = _call("list_context_packs", {"project": "sample"})

    assert payload["project"] == "sample"
    assert payload["returned_count"] == 2
    names = [pack["pack_name"] for pack in payload["context_packs"]]
    assert names == ["docs", "tiny"]
    assert payload["context_packs"][0]["description"] == "General project docs"
    assert payload["context_packs"][0]["token_budget"] == 8000
    assert payload["context_packs"][1]["token_budget"] == 1


def test_get_context_pack_returns_pack_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _vault, registry = _prepare_vault(tmp_path)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    payload = _call("get_context_pack", {"project": "sample", "pack_name": "docs"})

    assert payload["project"] == "sample"
    assert payload["pack_name"] == "docs"
    assert payload["files_included"] == ["docs/guide.md"]
    assert payload["missing_files"] == []
    assert payload["warnings"] == []
    assert payload["content"].startswith("<!-- From: docs/guide.md -->")


def test_get_context_pack_surfaces_invalid_pack_and_budget_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _vault, registry = _prepare_vault(tmp_path)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    with pytest.raises(ToolError) as missing_pack:
        _call("get_context_pack", {"project": "sample", "pack_name": "missing"})
    with pytest.raises(ToolError) as budget_error:
        _call("get_context_pack", {"project": "sample", "pack_name": "tiny"})

    assert ErrorCode.ERR_INVALID_PROJECT.value in str(missing_pack.value)
    assert ErrorCode.ERR_CONTEXT_EXCEEDS_BUDGET.value in str(budget_error.value)
