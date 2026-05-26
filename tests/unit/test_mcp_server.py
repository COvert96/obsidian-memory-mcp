"""Integration tests for the MCP server's read_note tool.

Tests use the module-level ``mcp`` instance directly.  The server registry is
pointed at the test vault via the ``OBSIDIAN_MEMORY_MCP_REGISTRY`` env var,
which ``monkeypatch`` restores after each test.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call(tool: str, arguments: dict) -> tuple:
    """Synchronously call *tool* via the module-level mcp instance."""
    return asyncio.run(mcp.call_tool(tool, arguments))


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


def test_server_exposes_read_note_tool() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == "read_note" for t in tools)


# ---------------------------------------------------------------------------
# read_note - success path
# ---------------------------------------------------------------------------


def test_read_note_returns_content_and_frontmatter(
    registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry_path))

    content_blocks, structured = _call(
        "read_note", {"project": "alpha", "note_path": "wiki/concept.md"}
    )

    payload = json.loads(content_blocks[0].text)
    assert payload["project"] == "alpha"
    assert payload["file_path"] == "wiki/concept.md"
    assert payload["frontmatter"] == {"type": "concept"}
    assert "# Concept" in payload["content"]
    assert payload["file_size_bytes"] > 0
    assert structured["file_path"] == "wiki/concept.md"


# ---------------------------------------------------------------------------
# read_note - error paths
# ---------------------------------------------------------------------------


def test_read_note_raises_for_unknown_project(
    registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry_path))

    with pytest.raises(ToolError) as exc_info:
        _call(
            "read_note", {"project": "no-such-project", "note_path": "wiki/concept.md"}
        )

    assert ErrorCode.ERR_INVALID_PROJECT.value in str(exc_info.value)


def test_read_note_raises_for_path_traversal(
    registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry_path))

    with pytest.raises(ToolError) as exc_info:
        _call("read_note", {"project": "alpha", "note_path": "../escape.md"})

    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(exc_info.value)


def test_read_note_raises_for_missing_file(
    registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry_path))

    with pytest.raises(ToolError) as exc_info:
        _call("read_note", {"project": "alpha", "note_path": "wiki/does-not-exist.md"})

    assert ErrorCode.ERR_MISSING_FILE.value in str(exc_info.value)


def test_read_note_raises_for_non_markdown_file(
    vault_root: Path, registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fixture vault allows reads only for **/*.md; a .txt file is denied.
    (vault_root / "secret.txt").write_text("hidden", encoding="utf-8")
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry_path))

    with pytest.raises(ToolError) as exc_info:
        _call("read_note", {"project": "alpha", "note_path": "secret.txt"})

    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(exc_info.value)
