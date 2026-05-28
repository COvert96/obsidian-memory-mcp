"""Integration tests for write_memory and write_note MCP tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


def _write_config(vault: Path) -> None:
    vault.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{vault.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**", "wiki/**"]
""",
        encoding="utf-8",
    )


def _write_registry(tmp_path: Path, vault: Path) -> Path:
    registry = tmp_path / "memory-mcp-server.yaml"
    registry.write_text(
        f'projects:\n  sample: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    return registry


def _call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    content_blocks, _structured = cast(
        tuple[list[Any], dict[str, Any]],
        asyncio.run(mcp.call_tool(tool, arguments)),
    )
    return cast(dict[str, Any], json.loads(content_blocks[0].text))


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    (root / "Memory").mkdir(parents=True)
    (root / "wiki").mkdir(parents=True)
    (root / ".mcp").mkdir(parents=True)
    _write_config(root)
    registry = _write_registry(tmp_path, root)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))
    return root


# ---------------------------------------------------------------------------
# write_memory
# ---------------------------------------------------------------------------


def test_write_memory_creates_file_on_disk(vault: Path) -> None:
    content = "# Project Memory\nInitial state."
    result = _call(
        "write_memory",
        {
            "project": "sample",
            "file_path": "Memory/test-note.md",
            "content": content,
        },
    )

    target = vault / "Memory" / "test-note.md"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == content
    assert result["project"] == "sample"
    assert result["file_path"] == "Memory/test-note.md"
    assert result["operation"] == "create"
    assert isinstance(result["content_hash"], str) and len(result["content_hash"]) == 64
    assert result["file_size_bytes"] == len(content.encode("utf-8"))
    assert isinstance(result["written_at"], str)


def test_write_memory_creates_nested_directories(vault: Path) -> None:
    _call(
        "write_memory",
        {
            "project": "sample",
            "file_path": "Memory/deep/sub/note.md",
            "content": "nested",
        },
    )
    assert (vault / "Memory" / "deep" / "sub" / "note.md").is_file()


def test_write_memory_rejects_non_memory_path(vault: Path) -> None:
    with pytest.raises(ToolError) as exc_info:
        _call(
            "write_memory",
            {"project": "sample", "file_path": "wiki/note.md", "content": "content"},
        )
    assert ErrorCode.ERR_INVALID_REQUEST.value in str(exc_info.value)
    assert not (vault / "wiki" / "note.md").exists()


def test_write_memory_fails_when_file_already_exists(vault: Path) -> None:
    (vault / "Memory" / "existing.md").write_text("original", encoding="utf-8")

    with pytest.raises(ToolError) as exc_info:
        _call(
            "write_memory",
            {
                "project": "sample",
                "file_path": "Memory/existing.md",
                "content": "replacement",
            },
        )

    assert ErrorCode.ERR_FILE_EXISTS.value in str(exc_info.value)
    assert (vault / "Memory" / "existing.md").read_text(encoding="utf-8") == "original"


# ---------------------------------------------------------------------------
# write_note
# ---------------------------------------------------------------------------


def test_write_note_creates_file_on_disk(vault: Path) -> None:
    content = "# New Wiki Note\nSome content."
    result = _call(
        "write_note",
        {
            "project": "sample",
            "file_path": "wiki/concepts/new-note.md",
            "content": content,
        },
    )

    target = vault / "wiki" / "concepts" / "new-note.md"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == content
    assert result["project"] == "sample"
    assert result["file_path"] == "wiki/concepts/new-note.md"
    assert result["operation"] == "create"
    assert isinstance(result["content_hash"], str) and len(result["content_hash"]) == 64
    assert result["file_size_bytes"] == len(content.encode("utf-8"))


def test_write_note_rejects_memory_path_and_writes_nothing(vault: Path) -> None:
    with pytest.raises(ToolError) as exc_info:
        _call(
            "write_note",
            {
                "project": "sample",
                "file_path": "Memory/should-be-rejected.md",
                "content": "content",
            },
        )

    assert ErrorCode.ERR_INVALID_REQUEST.value in str(exc_info.value)
    assert not (vault / "Memory" / "should-be-rejected.md").exists()


def test_write_note_fails_when_file_already_exists(vault: Path) -> None:
    (vault / "wiki" / "existing.md").write_text("original", encoding="utf-8")

    with pytest.raises(ToolError) as exc_info:
        _call(
            "write_note",
            {
                "project": "sample",
                "file_path": "wiki/existing.md",
                "content": "replacement",
            },
        )

    assert ErrorCode.ERR_FILE_EXISTS.value in str(exc_info.value)
    assert (vault / "wiki" / "existing.md").read_text(encoding="utf-8") == "original"
