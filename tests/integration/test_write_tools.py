"""Integration tests for write_memory and write_note MCP tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from obsidian_memory_mcp.config import ConfigLoader
from obsidian_memory_mcp.errors import ErrorCode
from obsidian_memory_mcp.server import mcp
from obsidian_memory_mcp.server_registry import SERVER_REGISTRY_ENV_VAR
from obsidian_memory_mcp.writes import WriteAuditRepository


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
    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(exc_info.value)
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


def test_write_note_allows_file_directly_under_concepts_directory_allow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Directory-only allow entries (e.g. wiki/concepts/) match direct children only."""
    root = tmp_path / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    (root / "Memory").mkdir(parents=True)
    (root / ".mcp").mkdir(parents=True)
    root.joinpath("memory-mcp.yaml").write_text(
        f"""
vault_path: "{root.as_posix()}"
index_db_location: .mcp/memory-index.sqlite3
context_packs:
  - name: default
    paths: ["**/*.md"]
write_constraints:
  read:
    allow: ["**/*.md"]
  write:
    allow: ["Memory/**", "wiki/concepts/"]
""",
        encoding="utf-8",
    )
    registry = _write_registry(tmp_path, root)
    monkeypatch.setenv(SERVER_REGISTRY_ENV_VAR, str(registry))

    result = _call(
        "write_note",
        {
            "project": "sample",
            "file_path": "wiki/concepts/uat-direct.md",
            "content": "# Direct\nCreated under wiki/concepts/.\n",
        },
    )

    target = root / "wiki" / "concepts" / "uat-direct.md"
    assert target.is_file()
    assert result["file_path"] == "wiki/concepts/uat-direct.md"


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

    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(exc_info.value)
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


# ---------------------------------------------------------------------------
# update_memory
# ---------------------------------------------------------------------------


def test_update_memory_overwrites_without_expected_hash(vault: Path) -> None:
    target = vault / "Memory" / "summary.md"
    target.write_text("# Old", encoding="utf-8")

    result = _call(
        "update_memory",
        {"project": "sample", "file_path": "Memory/summary.md", "content": "# New"},
    )

    assert target.read_text(encoding="utf-8") == "# New"
    assert result["operation"] == "update"
    assert result["file_path"] == "Memory/summary.md"


def test_update_memory_accepts_matching_hash_from_read_note(vault: Path) -> None:
    target = vault / "Memory" / "summary.md"
    target.write_text("# Original\nbody", encoding="utf-8")

    read_back = _call(
        "read_note", {"project": "sample", "note_path": "Memory/summary.md"}
    )
    result = _call(
        "update_memory",
        {
            "project": "sample",
            "file_path": "Memory/summary.md",
            "content": "# Revised",
            "expected_hash": read_back["content_hash"],
        },
    )

    assert result["operation"] == "update"
    assert target.read_text(encoding="utf-8") == "# Revised"


def test_update_memory_rejects_stale_hash_after_disk_change(vault: Path) -> None:
    target = vault / "Memory" / "summary.md"
    target.write_text("# Original", encoding="utf-8")
    read_back = _call(
        "read_note", {"project": "sample", "note_path": "Memory/summary.md"}
    )
    # Mutate on disk after reading, so the captured hash is now stale.
    target.write_text("# Changed underneath", encoding="utf-8")

    with pytest.raises(ToolError) as exc_info:
        _call(
            "update_memory",
            {
                "project": "sample",
                "file_path": "Memory/summary.md",
                "content": "# Attempted",
                "expected_hash": read_back["content_hash"],
            },
        )

    assert ErrorCode.ERR_HASH_MISMATCH.value in str(exc_info.value)
    assert target.read_text(encoding="utf-8") == "# Changed underneath"


def test_update_memory_missing_file_raises(vault: Path) -> None:
    with pytest.raises(ToolError) as exc_info:
        _call(
            "update_memory",
            {
                "project": "sample",
                "file_path": "Memory/absent.md",
                "content": "content",
            },
        )

    assert ErrorCode.ERR_MISSING_FILE.value in str(exc_info.value)


# ---------------------------------------------------------------------------
# update_memory with supersedes
# ---------------------------------------------------------------------------


def test_update_memory_supersedes_archives_old_note_and_records_one_audit_row(
    vault: Path,
) -> None:
    (vault / "Memory" / "old.md").write_text(
        "---\ntopic: company\n---\n# Old\nOld truth.", encoding="utf-8"
    )
    (vault / "Memory" / "new.md").write_text("# stub", encoding="utf-8")

    result = _call(
        "update_memory",
        {
            "project": "sample",
            "file_path": "Memory/new.md",
            "content": "# New\nNew truth.",
            "supersedes": ["Memory/old.md"],
        },
    )

    # Old note archived with supersession frontmatter.
    assert not (vault / "Memory" / "old.md").exists()
    archived = vault / "Memory" / "archive" / "old.md"
    assert archived.is_file()
    archived_text = archived.read_text(encoding="utf-8")
    assert "superseded: true" in archived_text
    assert "superseded_by: Memory/new.md" in archived_text
    assert "Old truth." in archived_text

    # New note carries the supersedes back-reference.
    new_text = (vault / "Memory" / "new.md").read_text(encoding="utf-8")
    assert "supersedes:" in new_text
    assert "Memory/archive/old.md" in new_text
    assert "New truth." in new_text

    # Exactly one append-only audit row carries the archive paths.
    config = ConfigLoader(vault).load()
    entries = WriteAuditRepository(config).list(
        project="sample", file_path="Memory/new.md"
    )
    assert len(entries) == 1
    assert entries[0].operation == "update"
    assert json.loads(cast(str, entries[0].supersedes)) == ["Memory/archive/old.md"]
    assert result["supersedes"] == ["Memory/archive/old.md"]


def test_update_memory_without_supersedes_records_null_supersedes(vault: Path) -> None:
    (vault / "Memory" / "plain.md").write_text("# Old", encoding="utf-8")

    _call(
        "update_memory",
        {"project": "sample", "file_path": "Memory/plain.md", "content": "# New"},
    )

    config = ConfigLoader(vault).load()
    entries = WriteAuditRepository(config).list(
        project="sample", file_path="Memory/plain.md"
    )
    assert len(entries) == 1
    assert entries[0].supersedes is None


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------


def test_update_note_overwrites_existing_note_outside_memory(vault: Path) -> None:
    target = vault / "wiki" / "concept.md"
    target.write_text("# Concept v1", encoding="utf-8")

    result = _call(
        "update_note",
        {
            "project": "sample",
            "file_path": "wiki/concept.md",
            "content": "# Concept v2",
        },
    )

    assert target.read_text(encoding="utf-8") == "# Concept v2"
    assert result["operation"] == "update"


def test_update_note_rejects_memory_path(vault: Path) -> None:
    (vault / "Memory" / "note.md").write_text("x", encoding="utf-8")

    with pytest.raises(ToolError) as exc_info:
        _call(
            "update_note",
            {"project": "sample", "file_path": "Memory/note.md", "content": "y"},
        )

    assert ErrorCode.ERR_GUARDRAIL_VIOLATION.value in str(exc_info.value)


def test_read_note_hash_round_trips_through_update_for_crlf_file(vault: Path) -> None:
    """US-005 success metric: a CRLF file's read_note hash is accepted by update."""
    target = vault / "Memory" / "crlf.md"
    target.write_bytes(b"# Title\r\nbody line\r\n")

    read_back = _call("read_note", {"project": "sample", "note_path": "Memory/crlf.md"})
    result = _call(
        "update_memory",
        {
            "project": "sample",
            "file_path": "Memory/crlf.md",
            "content": "# Replaced",
            "expected_hash": read_back["content_hash"],
        },
    )

    assert result["operation"] == "update"
    assert target.read_text(encoding="utf-8") == "# Replaced"
